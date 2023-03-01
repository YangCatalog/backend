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

import utility.log as log
from parseAndPopulate.dumper import Dumper
from parseAndPopulate.file_hasher import FileHasher
from parseAndPopulate.models.directory_paths import DirPaths
from parseAndPopulate.models.vendor_modules import VendorInfo, VendorPlatformData
from parseAndPopulate.modules import Module, SdoModule, VendorModule
from redisConnections.redisConnection import RedisConnection
from utility.create_config import create_config
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
        self.logger = log.get_logger('groupings', f'{dir_paths["log"]}/parseAndPopulate.log')
        self.logger.debug(f'Running {self.__class__.__name__} constructor')
        self.config = config
        self.dir_paths = dir_paths
        self.dumper = dumper
        self.api = api
        self.file_hasher = file_hasher
        self.directory = directory
        self.parsed = 0
        self.skipped = 0

    def parse_and_load(self):
        """Parse the modules and load the extracted data into the dumper."""

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
        file_mapping: dict[str, str],
        config: ConfigParser = create_config(),
    ):
        self.file_mapping = file_mapping
        super().__init__(directory, dumper, file_hasher, api, dir_paths, config=config)

    def parse_and_load(self) -> tuple[int, int]:
        """
        If modules were sent via the API, the contents of the request-data.json file are parsed
        and modules are loaded from Git repository.
        Otherwise, all the .yang files in the directory are parsed.

        Argument:
            :return     (tuple[int, int]) The number of moudles parsed and skipped respectively
        """
        if self.api:
            ret = self._parse_and_load_api()
        else:
            ret = self._parse_and_load_not_api()
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
            repo_owner = sdo['source-file']['owner']
            repo_file_path = sdo['source-file']['path']
            repo_name = sdo['source-file']['repository'].split('.')[0]
            root = os.path.join(repo_owner, repo_name, os.path.dirname(repo_file_path))
            root = os.path.join(self.dir_paths['json'], root)
            path = os.path.join(root, file_name)
            if not os.path.isfile(path):
                self.logger.error(f'File {file_name} sent via API was not downloaded')
                continue
            if '[1]' in file_name:
                self.logger.warning(f'File {file_name} contains [1] it its file name')
                continue
            # Openconfig modules are sent via API daily; see openconfigPullLocal.py script
            if '/openconfig/public/' in path:
                all_modules_path = self.file_mapping[path]
                should_parse = self.file_hasher.should_parse_sdo_module(all_modules_path)
                if not should_parse:
                    self.skipped += 1
                    continue
            try:
                yang = SdoModule(
                    path,
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

        for root, _, sdos in os.walk(self.directory):
            sdos_count = len(sdos)
            self.logger.info(f'Searching {sdos_count} files from directory {root}')
            for i, file_name in enumerate(sdos, start=1):
                # Process only SDO .yang files
                if '.yang' not in file_name or any(word in root for word in ['vendor', 'odp']):
                    continue
                path = os.path.join(root, file_name)
                all_modules_path = self.file_mapping[path]
                should_parse = self.file_hasher.should_parse_sdo_module(all_modules_path)
                if not should_parse:
                    self.skipped += 1
                    continue
                if '[1]' in file_name:
                    self.logger.warning(f'File {file_name} contains [1] it its file name')
                    continue
                self.logger.info(f'Parsing {file_name} {i} out of {sdos_count}')
                try:
                    yang = SdoModule(
                        path,
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
        file_mapping: dict[str, str],
        config: ConfigParser = create_config(),
    ):
        super().__init__(directory, dumper, file_hasher, api, dir_paths, file_mapping, config=config)
        iana_exceptions = config.get('Directory-Section', 'iana-exceptions')
        try:
            with open(iana_exceptions, 'r') as exceptions_file:
                self.iana_skip = exceptions_file.read().split('\n')
        except FileNotFoundError:
            open(iana_exceptions, 'w').close()
            os.chmod(iana_exceptions, 0o664)
            self.iana_skip = []
        self.root = ET.parse(os.path.join(directory, 'yang-parameters.xml')).getroot()

    def parse_and_load(self) -> tuple[int, int]:
        """Parse all IANA-maintained modules listed in the yang-parameters.xml file."""
        tag = self.root.tag
        namespace = tag.split('registry')[0]
        modules = self.root.iter(f'{namespace}record')

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

            if data.get('iana') != 'Y' or 'file' not in data:
                continue
            name = data.get('name')
            path = os.path.join(self.directory, data['file'])
            if os.path.basename(path) in self.iana_skip:
                self.logger.debug(f'skipping {path}: found in iana-exceptions.dat')
                continue
            self.logger.debug(f'parsing {path}')
            all_modules_path = self.file_mapping.get(path)
            if not all_modules_path:
                self.logger.warning(f'File {name} not found in the repository')
                continue
            should_parse = self.file_hasher.should_parse_sdo_module(all_modules_path)
            if not should_parse:
                self.skipped += 1
                continue

            self.logger.info(f'Parsing module {name}')
            try:
                yang = SdoModule(
                    path,
                    self.dir_paths,
                    self.dumper.yang_modules,
                    additional_info,
                    config=self.config,
                )
            except (ParseException, FileNotFoundError) as e:
                self.log_module_creation_exception(e)
                continue
            self.dumper.add_module(yang)
            self.parsed += 1
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
        config: ConfigParser = create_config(),
        redis_connection: t.Optional[RedisConnection] = None,
    ):
        super().__init__(directory, dumper, file_hasher, api, dir_paths, config=config)
        self.redis_connection = redis_connection or RedisConnection(config=config)
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

    def _parse_raw_capability(self, raw_capability: str):
        # Parse netconf version
        if ':netconf:base:' in raw_capability:
            self.logger.debug('Getting netconf version')
            self.netconf_versions.append(raw_capability)
        # Parse capability together with version
        elif ':capability:' in raw_capability:
            self.capabilities.append(raw_capability.split('?')[0])

    def _parse_imp_inc(self, modules: list, set_of_names: set, is_include: bool):
        """
        Parse all yang modules which are either submodules or imports of a certain module.
        Submodules and import modules are also added to the dumper object.
        This method is then recursively called for all found submodules and imported modules.

        Arguments:
            :param modules          (list) List of modules to check (either submodules or imports of module)
            :param set_of_names     (set) Set of all the modules parsed out from the capability file
            :param is_include       (bool) Whether module is included or not
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
            vendor_info = VendorInfo(
                platform_data=self.platform_data,
                conformance_type=conformance_type,
                capabilities=self.capabilities,
                netconf_versions=self.netconf_versions,
            )
            try:
                yang = VendorModule(
                    path,
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
            self._parse_imp_inc(self.dumper.yang_modules[key].submodule, set_of_names, True)
            self._parse_imp_inc(self.dumper.yang_modules[key].imports, set_of_names, False)


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
            vendor_info = VendorInfo(
                platform_data=self.platform_data,
                conformance_type='implement',
                capabilities=self.capabilities,
                netconf_versions=self.netconf_versions,
            )
            try:
                yang = VendorModule(
                    path,
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
            self._parse_imp_inc(self.dumper.yang_modules[key].submodule, set_of_names, True)
            self._parse_imp_inc(self.dumper.yang_modules[key].imports, set_of_names, False)
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
            vendor_info = VendorInfo(
                platform_data=self.platform_data,
                conformance_type=conformance_type,
                capabilities=self.capabilities,
                netconf_versions=self.netconf_versions,
            )
            try:
                yang = VendorModule(
                    path,
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
            self._parse_imp_inc(self.dumper.yang_modules[key].submodule, set_of_names, True)
            self._parse_imp_inc(self.dumper.yang_modules[key].imports, set_of_names, False)
        return self.parsed, self.skipped
