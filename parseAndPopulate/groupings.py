# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import fileinput
import json
import os
import typing as t
import unicodedata
import xml.etree.ElementTree as ET
from configparser import ConfigParser

import requests
from git import InvalidGitRepositoryError
from git.repo import Repo

import utility.log as log
from parseAndPopulate.dumper import Dumper
from parseAndPopulate.file_hasher import FileHasher
from parseAndPopulate.models.directory_paths import DirPaths
from parseAndPopulate.models.schema_parts import SchemaParts
from parseAndPopulate.models.vendor_modules import VendorInfo, VendorPlatformData
from parseAndPopulate.modules import Module, SdoModule, VendorModule
from redisConnections.redisConnection import RedisConnection
from utility import repoutil
from utility.create_config import create_config
from utility.staticVariables import GITHUB_RAW, github_url
from utility.util import get_yang
from utility.yangParser import ParseException


class ModuleGrouping:
    """Base class for a grouping of modules to be parsed together."""

    def __init__(
        self,
        directory: str,
        dumper: Dumper,
        file_hasher: FileHasher,
        api: bool,
        dir_paths: DirPaths,
        config: ConfigParser = create_config(),
    ):
        """
        Arguments:
            :param directory            (str) the directory containing the files
            :param dumper               (Dumper) Dumper object
            :param file_hasher          (FileHasher) FileHasher object
            :param api                  (bool) whether the request came from API or not
            :param dir_paths            (DirPaths) paths to various needed directories according to configuration
        """
        self.logger = log.get_logger('repoutil', f'{dir_paths["log"]}/parseAndPopulate.log')
        self.logger.debug(f'Running {self.__class__.__name__} constructor')
        self.config = config
        self.dir_paths = dir_paths
        self.dumper = dumper
        self.api = api
        self.file_hasher = file_hasher
        self.directory = directory
        self._submodule_map = {}
        for submodule in Repo(dir_paths['yang_models']).submodules:
            url = submodule.url.replace(github_url, GITHUB_RAW).removesuffix('.git')
            self._submodule_map[url] = submodule.path
        try:
            with open(os.path.join(dir_paths['cache'], 'schema_dict.json')) as f:
                self._schemas = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._schemas = {}
        self.parsed = 0
        self.skipped = 0

    def _dump_schema_cache(self):
        try:
            with open(os.path.join(self.dir_paths['cache'], 'schema_dict.json'), 'w') as f:
                json.dump(self._schemas, f)
        except (FileNotFoundError, PermissionError):
            self.logger.error('Could not update the schema url cache')

    def _load_yangmodels_repo(self):
        self.repo_owner = 'YangModels'
        self.repo_name = 'yang'
        repo_url = os.path.join(github_url, self.repo_owner, self.repo_name)
        try:
            repo = repoutil.load(self.dir_paths['yang_models'], repo_url)
        except InvalidGitRepositoryError:
            repo = repoutil.RepoUtil(
                repo_url,
                clone_options={'local_dir': self.dir_paths['yang_models']},
                logger=self.logger,
            )
        self.repo = repo

    def _check_if_submodule(self) -> t.Optional[str]:
        submodule_name = None
        for submodule in self.repo.repo.submodules:
            if submodule.name not in self.directory:
                continue
            submodule_name = submodule.name
            repo_url = submodule.url.lower()
            repo_dir = os.path.join(self.dir_paths['yang_models'], submodule_name)
            repo = repoutil.load(repo_dir, repo_url)
            self.repo = repo
            self.repo_owner = self.repo.get_repo_owner()
            self.repo_name = self.repo.get_repo_dir().split('.git')[0]
            break
        return submodule_name

    def parse_and_load(self):
        """Parse the modules and load the extracted data into the dumper."""

    def _update_schema_urls(self, name: str, revision: str, path: str, schema_parts: SchemaParts):
        name_revision = f'{name}@{revision}'
        if name_revision in self._schemas:
            return
        schema = self._construct_schema_url(path, schema_parts)
        if schema and requests.head(schema).status_code == 200:
            self._schemas[name_revision] = schema
        self.logger.error(f'Broken schema generated: {schema}')

    def _construct_schema_url(self, path: str, schema_parts: SchemaParts) -> t.Optional[str]:
        self.logger.debug('Resolving schema')
        if 'SOL006-' in path:
            suffix = path.split('SOL006-')[-1]
            return f'https://forge.etsi.org/rep/nfv/SOL006/raw/{suffix}'
        if not schema_parts.schema_base:
            return None
        schema_base_hash = schema_parts.schema_base_hash
        if 'openconfig/public' in path:
            suffix = os.path.abspath(path).split('/openconfig/public/')[-1]
            return os.path.join(schema_base_hash, suffix)
        if 'draftpulllocal' in path:
            suffix = os.path.abspath(path).split('draftpulllocal/')[-1]
            return os.path.join(schema_base_hash, suffix)
        if 'yangmodels/yang' in path:
            suffix = os.path.abspath(path).split('/yangmodels/yang/')[-1]
        elif '/tmp/' in path:
            suffix = os.path.abspath(path).split('/tmp/')[1]
            # remove directory_number/owner/repo prefix
            suffix = '/'.join(suffix.split('/')[3:])
        else:
            self.logger.warning('Cannot resolve schema')
            return
        if schema_parts.submodule_name:
            suffix = suffix.replace(f'{schema_parts.submodule_name}/', '')
        return os.path.join(schema_base_hash, suffix)

    def log_module_creation_exception(self, exception: t.Union[FileNotFoundError, ParseException]):
        path = exception.args[0]
        if isinstance(exception, FileExistsError):
            self.logger.error(f'File {path} not found in the repository')
        elif isinstance(exception, ParseException):
            self.logger.warning(f'ParseException while parsing {path}')


class SdoDirectory(ModuleGrouping):
    """Regular SDO directory containing yang modules."""

    def __init__(
        self,
        directory: str,
        dumper: Dumper,
        file_hasher: FileHasher,
        api: bool,
        dir_paths: DirPaths,
        path_to_name_rev: dict,
        config: ConfigParser = create_config(),
    ):
        self.path_to_name_rev = path_to_name_rev
        super().__init__(directory, dumper, file_hasher, api, dir_paths, config=config)

    def parse_and_load(self, repo: t.Optional[repoutil.RepoUtil] = None) -> tuple[int, int]:
        """
        If modules were sent via the API, the contents of the request-data.json file are parsed
        and modules are loaded from Git repository.
        Otherwise, all the .yang files in the directory are parsed.

        Argument:
            :param repo     Git repository which contains .yang files
        """
        if self.api:
            ret = self._parse_and_load_api()
        else:
            ret = self._parse_and_load_not_api()
        self._dump_schema_cache()
        return ret

    def _parse_and_load_api(self) -> tuple[int, int]:
        self.logger.debug('Parsing sdo files sent via API')
        with open(os.path.join(self.dir_paths['json'], 'request-data.json'), 'r') as f:
            sdos_json = json.load(f)
        sdos_list: t.List[dict] = sdos_json['modules']['module']
        sdos_count = len(sdos_list)
        for i, sdo in enumerate(sdos_list, start=1):
            # remove diacritics
            file_name = (
                unicodedata.normalize('NFKD', os.path.basename(sdo['source-file']['path']))
                .encode('ascii', 'ignore')
                .decode()
            )
            self.logger.info(f'Parsing {file_name} {i} out of {sdos_count}')
            self.repo_owner = sdo['source-file']['owner']
            repo_file_path = sdo['source-file']['path']
            self.repo_name = sdo['source-file']['repository'].split('.')[0]
            commit_hash = sdo['source-file']['commit-hash']
            root = os.path.join(self.repo_owner, self.repo_name, os.path.dirname(repo_file_path))
            root = os.path.join(self.dir_paths['json'], root)
            path = os.path.join(root, file_name)
            if not os.path.isfile(path):
                self.logger.error(f'File {file_name} sent via API was not downloaded')
                continue
            if '[1]' in file_name:
                self.logger.warning(f'File {file_name} contains [1] it its file name')
                continue
            name, revision = self.path_to_name_rev[path]
            # Openconfig modules are sent via API daily; see openconfigPullLocal.py script
            if '/openconfig/public/' in path:
                all_modules_path = get_yang(name, revision, config=self.config)
                if not all_modules_path:
                    self.logger.warning(f'File {name} not found in the repository')
                    continue
                should_parse = self.file_hasher.should_parse_sdo_module(all_modules_path)
                if not should_parse:
                    self.skipped += 1
                    continue
            schema_parts = SchemaParts(repo_owner=self.repo_owner, repo_name=self.repo_name, commit_hash=commit_hash)
            self._update_schema_urls(name, revision, path, schema_parts)
            try:
                yang = SdoModule(
                    name,
                    path,
                    self._schemas,
                    self.dir_paths,
                    self.dumper.yang_modules,
                    additional_info=sdo,
                    config=self.config,
                )
            except (ParseException, FileNotFoundError) as e:
                self.log_module_creation_exception(e)
                continue
            self.dumper.add_module(yang)
            self.parsed += 1
        return self.parsed, self.skipped

    def _parse_and_load_not_api(self) -> tuple[int, int]:
        self.logger.debug('Parsing sdo files from directory')
        self._load_yangmodels_repo()
        # Check if repository submodule
        submodule_name = self._check_if_submodule()

        for root, _, sdos in os.walk(self.directory):
            sdos_count = len(sdos)
            self.logger.info(f'Searching {sdos_count} files from directory {root}')
            commit_hash = self.repo.get_commit_hash(root, 'main')
            schema_parts = SchemaParts(
                repo_owner=self.repo_owner,
                repo_name=self.repo_name,
                commit_hash=commit_hash,
                submodule_name=submodule_name,
            )
            for i, file_name in enumerate(sdos, start=1):
                # Process only SDO .yang files
                if '.yang' not in file_name or any(word in root for word in ['vendor', 'odp']):
                    continue
                path = os.path.join(root, file_name)
                name, revision = self.path_to_name_rev[path]
                all_modules_path = get_yang(name, revision, config=self.config)
                if not all_modules_path:
                    self.logger.warning(f'File {name} not found in the repository')
                    continue
                should_parse = self.file_hasher.should_parse_sdo_module(all_modules_path)
                if not should_parse:
                    self.skipped += 1
                    continue
                if '[1]' in file_name:
                    self.logger.warning(f'File {file_name} contains [1] it its file name')
                    continue
                self.logger.info(f'Parsing {file_name} {i} out of {sdos_count}')
                self._update_schema_urls(name, revision, path, schema_parts)
                try:
                    yang = SdoModule(
                        name,
                        path,
                        self._schemas,
                        self.dir_paths,
                        self.dumper.yang_modules,
                        config=self.config,
                    )
                except (ParseException, FileNotFoundError) as e:
                    self.log_module_creation_exception(e)
                    continue
                self.dumper.add_module(yang)
                self.parsed += 1
        return self.parsed, self.skipped


class IanaDirectory(SdoDirectory):
    """Directory containing IANA modules."""

    def __init__(
        self,
        directory: str,
        dumper: Dumper,
        file_hasher: FileHasher,
        api: bool,
        dir_paths: DirPaths,
        path_to_name_rev: dict,
        config: ConfigParser = create_config(),
    ):
        super().__init__(directory, dumper, file_hasher, api, dir_paths, path_to_name_rev, config=config)
        iana_exceptions = config.get('Directory-Section', 'iana-exceptions')
        try:
            with open(iana_exceptions, 'r') as exceptions_file:
                self.iana_skip = exceptions_file.read().split('\n')
        except FileNotFoundError:
            open(iana_exceptions, 'w').close()
            os.chmod(iana_exceptions, 0o664)
            self.iana_skip = []
        self.root = ET.parse(os.path.join(directory, 'yang-parameters.xml')).getroot()

    def parse_and_load(self, **kwargs) -> tuple[int, int]:
        """Parse all IANA-maintained modules listed in the yang-parameters.xml file."""
        tag = self.root.tag
        namespace = tag.split('registry')[0]
        modules = self.root.iter(f'{namespace}record')

        self._load_yangmodels_repo()
        commit_hash = self.repo.get_commit_hash(self.directory, 'main')
        schema_parts = SchemaParts(repo_owner=self.repo_owner, repo_name=self.repo_name, commit_hash=commit_hash)

        for module in modules:
            additional_info = Module.AdditionalModuleInfo(organization='ietf')
            data = module.attrib
            for attributes in module:
                prop = attributes.tag.split(namespace)[-1]
                data[prop] = attributes.text if attributes.text else ''
                if prop == 'xref':
                    xref_info = attributes.attrib
                    if xref_info.get('type') == 'draft':
                        document_split = xref_info['data'].replace('RFC', 'draft').split('-')
                        version = document_split[-1]
                        name = '-'.join(document_split[:-1])
                        additional_info['document-name'] = f'{name}-{version}.txt'
                        additional_info['reference'] = f'https://datatracker.ietf.org/doc/{name}/{version}'
                    else:
                        additional_info['document-name'] = xref_info.get('data')
                        additional_info['reference'] = f'https://datatracker.ietf.org/doc/{xref_info.get("data")}'

            if data.get('iana') == 'Y' and data.get('file'):
                path = os.path.join(self.directory, data['file'])
                if os.path.basename(path) in self.iana_skip:
                    self.logger.debug(f'skipping {path}: found in iana-exceptions.dat')
                    continue
                self.logger.debug(f'parsing {path}')
                try:
                    name, revision = self.path_to_name_rev[path]
                except KeyError:
                    self.logger.exception('Couldn\'t resolve name and revision')
                    continue
                all_modules_path = get_yang(name, revision, config=self.config)
                if not all_modules_path:
                    self.logger.warning(f'File {name} not found in the repository')
                    continue
                should_parse = self.file_hasher.should_parse_sdo_module(all_modules_path)
                if not should_parse:
                    self.skipped += 1
                    continue

                self.logger.info(f'Parsing module {name}')
                self._update_schema_urls(name, revision, path, schema_parts)
                try:
                    yang = SdoModule(
                        data['name'],
                        path,
                        self._schemas,
                        self.dir_paths,
                        self.dumper.yang_modules,
                        additional_info=additional_info,
                        config=self.config,
                    )
                except (ParseException, FileNotFoundError) as e:
                    self.log_module_creation_exception(e)
                    continue
                self.dumper.add_module(yang)
                self.parsed += 1
        self._dump_schema_cache()
        return self.parsed, self.skipped


class VendorGrouping(ModuleGrouping):
    def __init__(
        self,
        directory: str,
        xml_file: str,
        dumper: Dumper,
        file_hasher: FileHasher,
        api: bool,
        dir_paths: DirPaths,
        name_rev_to_path: dict,
        config: ConfigParser = create_config(),
        redis_connection: t.Optional[RedisConnection] = None,
    ):
        self.name_rev_to_path = name_rev_to_path
        super().__init__(directory, dumper, file_hasher, api, dir_paths, config=config)
        self.redis_connection = redis_connection or RedisConnection(config=config)
        self.submodule_name = None
        self.found_capabilities = False
        self.capabilities = []
        self.netconf_versions = []
        self.platform_data: list[VendorPlatformData] = []
        self.implementation_keys = []
        self.xml_file = xml_file
        # Get hello message root
        try:
            self.logger.debug('Checking for xml hello message file')
            self.root = ET.parse(xml_file).getroot()
        except Exception:
            # try to change & to &amp
            hello_file = fileinput.FileInput(xml_file, inplace=True)
            for line in hello_file:
                print(line.replace('&', '&amp;'), end='')
            hello_file.close()
            self.logger.warning('Hello message file has & instead of &amp, automatically changing to &amp')
            self.root = ET.parse(xml_file).getroot()

    def _parse_platform_metadata(self):
        # Vendor modules send from API
        if self.api:
            with open(f'{self.xml_file.removesuffix(".xml")}.json', 'r') as f:
                implementation = json.load(f)
            self.logger.debug('Getting capabilities out of api message')
            self._parse_implementation(implementation)
            return
        # Vendor modules loaded from directory
        self._load_yangmodels_repo()
        self.submodule_name = self._check_if_submodule()
        branch = 'main'
        if self.submodule_name:
            branch = 'master'
        self.commit_hash = self.repo.get_commit_hash(branch=branch)
        metadata_path = os.path.join(self.directory, 'platform-metadata.json')
        if os.path.isfile(metadata_path):
            self.logger.info('Parsing a platform-metadata.json file')
            with open(metadata_path, 'r') as f:
                data = json.load(f)
            platforms = data.get('platforms', {}).get('platform', [])
            for implementation in platforms:
                self._parse_implementation(implementation)
        else:
            self.logger.debug('Deriving platform metadata from paths')
            self.platform_data.append(self._path_to_platform_data())

    def _path_to_platform_data(self) -> VendorPlatformData:
        """Try to derive platform data from the directory path and xml name."""
        base = os.path.basename(self.xml_file).removesuffix('.xml')
        base = base.replace('capabilities', '').replace('capability', '').replace('netconf', '').strip('-')
        platform = base or 'Unknown'
        split_path = self.directory.split('/')
        if 'nx' in split_path:
            platform_index = split_path.index('nx')
            os_type = 'NX-OS'
        elif 'xe' in split_path:
            platform_index = split_path.index('xe')
            os_type = 'IOS-XE'
        elif 'xr' in split_path:
            platform_index = split_path.index('xr')
            os_type = 'IOS-XR'
        else:
            platform_index = -3
            os_type = 'Unknown'
            platform = 'Unknown'
        return {
            'software-flavor': 'ALL',
            'platform': platform,
            'software-version': split_path[platform_index + 1],
            'os-version': split_path[platform_index + 1],
            'feature-set': 'ALL',
            'os': os_type,
            'vendor': split_path[platform_index - 1],
        }

    def _parse_implementation(self, implementation: dict):
        if implementation['module-list-file']['path'] not in self.xml_file:
            return
        self._initialize_repo(implementation)
        self.platform_data.append(
            {
                'software-flavor': implementation['software-flavor'],
                'platform': implementation['name'],
                'os-version': implementation['software-version'],
                'software-version': implementation['software-version'],
                'feature-set': 'ALL',
                'vendor': implementation['vendor'],
                'os': implementation['os-type'],
            },
        )
        self.implementation_keys.append(f'{implementation["name"]}/{implementation["software-version"]}')
        raw_capabilities = implementation.get('netconf-capabilities')
        if not raw_capabilities:
            return
        self.found_capabilities = True
        for raw_capability in raw_capabilities:
            self._parse_raw_capability(raw_capability)

    def _initialize_repo(self, implementation: dict):
        self.repo_owner = implementation['module-list-file']['owner']
        self.repo_name = implementation['module-list-file']['repository']
        if self.repo_name is not None:
            self.repo_name = self.repo_name.split('.')[0]
        if self.api:
            self.commit_hash = implementation['module-list-file']['commit-hash']

    def _parse_raw_capability(self, raw_capability: str):
        # Parse netconf version
        if ':netconf:base:' in raw_capability:
            self.logger.debug('Getting netconf version')
            self.netconf_versions.append(raw_capability)
        # Parse capability together with version
        elif ':capability:' in raw_capability:
            self.capabilities.append(raw_capability.split('?')[0])

    def _parse_imp_inc(self, modules: list, set_of_names: set, is_include: bool, schema_parts: SchemaParts):
        """
        Parse all yang modules which are either submodules or imports of a certain module.
        Submodules and import modules are also added to the dumper object.
        This method is then recursively called for all found submodules and imported modules.

        Arguments:
            :param modules          (list) List of modules to check (either submodules or imports of module)
            :param set_of_names     (set) Set of all the modules parsed out from the capability file
            :param is_include       (bool) Whether module is included or not
            :param schema_parts     (SchemaParts) Parts of the URL to a raw module on GitHub
        """
        for module in modules:
            name = module.name
            conformance_type = None if is_include else 'import'

            # Skip if name of submodule/import is already in list of module names
            if name in set_of_names:
                continue
            self.logger.info(f'Parsing module {name}')
            path = get_yang(name, config=self.config)
            if path is None:
                return
            module_hash_info = self.file_hasher.check_vendor_module_hash_for_parsing(path, self.implementation_keys)
            if not module_hash_info.module_should_be_parsed:
                self.skipped += 1
                continue
            revision = path.split('@')[-1].removesuffix('.yang')
            if (name, revision) in self.name_rev_to_path:
                path = self.name_rev_to_path[name, revision]
            self._update_schema_urls(name, revision, path, schema_parts)
            vendor_info = VendorInfo(
                platform_data=self.platform_data,
                conformance_type=conformance_type,
                capabilities=self.capabilities,
                netconf_versions=self.netconf_versions,
            )
            try:
                yang = VendorModule(
                    name,
                    path,
                    self._schemas,
                    self.dir_paths,
                    self.dumper.yang_modules,
                    vendor_info,
                    config=self.config,
                    redis_connection=self.redis_connection,
                    can_be_already_stored_in_db=module_hash_info.file_hash_exists,
                )
            except (ParseException, FileNotFoundError) as e:
                self.log_module_creation_exception(e)
                continue
            self.dumper.add_module(yang)
            self.parsed += 1
            key = f'{yang.name}@{yang.revision}/{yang.organization}'
            set_of_names.add(yang.name)
            self._parse_imp_inc(self.dumper.yang_modules[key].submodule, set_of_names, True, schema_parts)
            self._parse_imp_inc(self.dumper.yang_modules[key].imports, set_of_names, False, schema_parts)


class VendorCapabilities(VendorGrouping):
    """Modules listed in a capabilities xml file."""

    def parse_and_load(self) -> tuple[int, int]:
        """
        Parse and load all information from the capabilities xml file and
        implementation data from a platform-metadata json file if present.
        """
        self.logger.debug('Starting to parse files from vendor')
        set_of_names = set()
        keys = set()
        tag = self.root.tag

        self._parse_platform_metadata()

        # netconf capability parsing
        modules = self.root.iter(f'{tag.split("hello")[0]}capability')

        if not self.found_capabilities:
            self.logger.debug('Getting capabilities out of hello message')
            for module in modules:
                # Parse netconf version
                if not module.text:
                    module.text = ''
                self._parse_raw_capability(module.text)
                modules = self.root.iter(f'{tag.split("hello")[0]}capability')

        try:
            schema_parts = SchemaParts(
                repo_owner=self.repo_owner,
                repo_name=self.repo_name,
                commit_hash=self.commit_hash,
                submodule_name=self.submodule_name,
            )
        except AttributeError as e:
            self.logger.exception(
                f'Missing attribute, likely caused by a broken path in {self.directory}/platform-metadata.json',
            )
            raise e

        # Parse modules
        for module in modules:
            module.text = module.text or ''
            if 'module=' not in module.text:
                continue
            # Parse name of the module
            module_and_more = module.text.split('module=')[1]
            name = module_and_more.split('&')[0]
            revision = None
            if 'revision' in module.text:
                revision_and_more = module.text.split('revision=')[1]
                revision = revision_and_more.split('&')[0]
            path = get_yang(name, revision, config=self.config)
            if not path:
                self.logger.warning(f'File {name} not found in the repository')
                continue
            module_hash_info = self.file_hasher.check_vendor_module_hash_for_parsing(path, self.implementation_keys)
            if not module_hash_info.module_should_be_parsed:
                self.skipped += 1
                continue
            self.logger.info(f'Parsing module {name}')
            revision = revision or path.split('@')[-1].removesuffix('.yang')
            if (name, revision) in self.name_rev_to_path:
                path = self.name_rev_to_path[name, revision]
            self._update_schema_urls(name, revision, path, schema_parts)
            vendor_info = VendorInfo(
                platform_data=self.platform_data,
                conformance_type='implement',
                capabilities=self.capabilities,
                netconf_versions=self.netconf_versions,
            )
            try:
                yang = VendorModule(
                    name,
                    path,
                    self._schemas,
                    self.dir_paths,
                    self.dumper.yang_modules,
                    vendor_info,
                    data=module_and_more,
                    config=self.config,
                    redis_connection=self.redis_connection,
                    can_be_already_stored_in_db=module_hash_info.file_hash_exists,
                )
            except (ParseException, FileNotFoundError) as e:
                self.log_module_creation_exception(e)
                continue
            self.dumper.add_module(yang)
            self.parsed += 1
            key = f'{yang.name}@{yang.revision}/{yang.organization}'
            keys.add(key)
            set_of_names.add(yang.name)

        for key in keys:
            self._parse_imp_inc(self.dumper.yang_modules[key].submodule, set_of_names, True, schema_parts)
            self._parse_imp_inc(self.dumper.yang_modules[key].imports, set_of_names, False, schema_parts)
        self._dump_schema_cache()
        return self.parsed, self.skipped


class VendorYangLibrary(VendorGrouping):
    def parse_and_load(self) -> tuple[int, int]:
        """Load implementation information which are stored platform-metadata.json file.
        Set this implementation information for each module parsed out from ietf-yang-library xml file.
        """

        self.logger.debug('Starting to parse files from vendor')

        self._parse_platform_metadata()

        # netconf capability parsing
        modules = self.root[0]
        set_of_names = set()
        keys = set()
        schema_parts = SchemaParts(
            repo_owner=self.repo_owner,
            repo_name=self.repo_name,
            commit_hash=self.commit_hash,
            submodule_name=self.submodule_name,
        )
        for yang in modules:
            if 'module-set-id' in yang.tag:
                continue
            name = ''
            yang_lib_info = {'path': self.directory, 'name': name, 'features': [], 'deviations': []}
            conformance_type = None
            for mod in yang:
                mod_tag = mod.tag
                if 'name' in mod_tag and not name:
                    name = mod_text if (mod_text := mod.text) else name
                    yang_lib_info['name'] = name
                if 'revision' in mod_tag:
                    yang_lib_info['revision'] = mod.text
                elif 'conformance-type' in mod_tag:
                    conformance_type = mod.text
                elif 'feature' in mod_tag:
                    yang_lib_info['features'].append(mod.text)
                elif 'deviation' in mod_tag:
                    deviation = {'name': mod[0].text, 'revision': mod[1].text}
                    yang_lib_info['deviations'].append(deviation)

            self.logger.info(f'Starting to parse {name}')
            revision = yang_lib_info.get('revision')
            path = get_yang(name, revision, config=self.config)
            if not path:
                self.logger.warning(f'File {name} not found in the repository')
                continue
            module_hash_info = self.file_hasher.check_vendor_module_hash_for_parsing(path, self.implementation_keys)
            if not module_hash_info.module_should_be_parsed:
                self.skipped += 1
                continue
            revision = revision or path.split('@')[-1].removesuffix('.yang')
            if (name, revision) in self.name_rev_to_path:
                path = self.name_rev_to_path[name, revision]
            self._update_schema_urls(name, revision, path, schema_parts)
            vendor_info = VendorInfo(
                platform_data=self.platform_data,
                conformance_type=conformance_type,
                capabilities=self.capabilities,
                netconf_versions=self.netconf_versions,
            )
            try:
                yang = VendorModule(
                    name,
                    path,
                    self._schemas,
                    self.dir_paths,
                    self.dumper.yang_modules,
                    vendor_info,
                    data=yang_lib_info,
                    config=self.config,
                    redis_connection=self.redis_connection,
                    can_be_already_stored_in_db=module_hash_info.file_hash_exists,
                )
            except (ParseException, FileNotFoundError) as e:
                self.log_module_creation_exception(e)
                continue
            self.dumper.add_module(yang)
            self.parsed += 1
            keys.add(f'{yang.name}@{yang.revision}/{yang.organization}')
            set_of_names.add(yang.name)

        for key in keys:
            self._parse_imp_inc(self.dumper.yang_modules[key].submodule, set_of_names, True, schema_parts)
            self._parse_imp_inc(self.dumper.yang_modules[key].imports, set_of_names, False, schema_parts)
        self._dump_schema_cache()
        return self.parsed, self.skipped
