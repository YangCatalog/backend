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

import utility.log as log
from git import InvalidGitRepositoryError
from git.repo import Repo
from utility import repoutil
from utility.staticVariables import GITHUB_RAW, github_url
from utility.util import find_first_file
from utility.yangParser import ParseException

from parseAndPopulate.dir_paths import DirPaths
from parseAndPopulate.dumper import Dumper
from parseAndPopulate.fileHasher import FileHasher
from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.modules import SdoModule, VendorModule
from parseAndPopulate.schema_parts import SchemaParts


class ModuleGrouping:
    """Base class for a grouping of modules to be parsed togeather."""

    def __init__(self, directory: str, dumper: Dumper, file_hasher: FileHasher,
                 api: bool, dir_paths: DirPaths):
        """
        Arguments:
            :param directory            (str) the directory containing the files
            :param dumper               (Dumper) Dumper object
            :param filehasher           (FileHasher) FileHasher object
            :param api                  (bool) whether the request came from API or not
            :param dir_paths            (DirPaths) paths to various needed directories according to configuration
        """

        global LOGGER
        LOGGER = log.get_logger('capability', '{}/parseAndPopulate.log'.format(dir_paths['log']))
        LOGGER.debug('Running {} constructor'.format(self.__class__.__name__))
        self.logger = log.get_logger('repoutil', '{}/parseAndPopulate.log'.format(dir_paths['log']))
        self.dir_paths = dir_paths
        self.dumper = dumper
        self.api = api
        self.file_hasher = file_hasher
        self.directory = directory
        self._submodule_map = {}
        for submodule in Repo(dir_paths['yang_models']).submodules:
            url = submodule.url.replace(github_url, GITHUB_RAW).removesuffix('.git')
            self._submodule_map[url] = submodule.path

    def _load_yangmodels_repo(self):
        self.repo_owner = 'YangModels'
        self.repo_name = 'yang'
        repo_url = os.path.join(github_url, self.repo_owner, self.repo_name)
        try:
            repo = repoutil.load(self.dir_paths['yang_models'], repo_url)
        except InvalidGitRepositoryError:
            repo = repoutil.RepoUtil(repo_url, clone_options={'local_dir': self.dir_paths['yang_models']},
                                     logger=self.logger)
        self.repo = repo

    def _check_if_submodule(self) -> t.Optional[str]:
        submodule_name = None
        for submodule in self.repo.repo.submodules:
            if submodule.name in self.directory:
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
        pass

    def _construct_json_name(self, schema_base: str, directory: str) -> t.Optional[str]:
        # This function reimplements the name mangling from sdo_analysis/bin/runYANGgenericstats.sh
        # TODO: Support for repositories that use multiple branches. This includes OpenROADM,
        #      and ETSI when cloned independently of YangModels/yang
        alnum: t.Callable[[str], str] = lambda s: ''.join(c for c in s if c.isalnum())
        split_path = os.path.abspath(directory).split('/')
        if 'openconfig' in split_path:
            return 'Openconfig'
        elif 'OpenNetworkingFoundation' in schema_base or 'onf' in split_path:
            return 'ONFOpenTransport'
        elif 'sysrepo' in split_path:
            if 'internal' in split_path:
                return 'SysrepoInternal'
            elif 'applications' in split_path:
                return 'SysrepoApplication'
        if 'tmp' in split_path:
            if schema_base in self._submodule_map:
                split_path = self._submodule_map[schema_base].split('/') + split_path[4:]
        else:
            split_path = split_path[split_path.index('yang', 3) + 1:]
        module_category, organization, split_path = split_path[0], split_path[1], split_path[2:]
        if module_category == 'standard':
            if organization == 'ietf':
                module_type = split_path[0]
                if module_type == 'DRAFT':
                    return 'IETFDraft'
                elif module_type == 'RFC':
                    return 'IETFYANGRFC'
            elif organization == 'etsi':
                if split_path[0] == 'NFV-SOL006-v2.6.1':
                    return 'ETSI261'
                elif split_path[0] == 'NFV-SOL006-v2.7.1':
                    return 'ETSI271'
            elif organization == 'bff':
                return 'BFF'
            elif organization == 'mef':
                if 'standard' in split_path[-2:]:
                    return 'MEFStandard'
                elif 'draft' in split_path[-2:]:
                    return 'MEFExperimental'
            elif organization == 'ieee':
                module_status = split_path[0]
                if module_status == 'published':
                    return 'IEEEStandard'
                elif module_status == 'draft':
                    return 'IEEEStandardDraft'
            elif organization == 'iana':
                return 'IANAStandard'
        elif module_category == 'experimental':
            if organization == 'ieee':
                return 'IEEEExperimental'
        elif module_category == 'vendor':
            if organization == 'cisco':
                cisco_os, version = split_path[0], split_path[1]
                return 'Cisco{}{}'.format(cisco_os.upper(), alnum(version))
            elif organization == 'juniper':
                version = split_path[0]
                if version == '14.2':
                    return 'Juniper142'
                else:
                    version_detail = split_path[1]
                    return 'Juniper{}'.format(alnum(version_detail))
            elif organization == 'huawei':
                version = split_path[1]
                return 'NETWORKROUTER{}'.format(alnum(version))
            elif organization == 'ciena':
                return 'CIENA'
            elif organization == 'fujitsu':
                return 'Fujitsu{}{}'.format(alnum(split_path[1]), alnum(split_path[2]))
            elif organization == 'nokia':
                version = split_path[1].removeprefix('latest_sros_')
                return 'Nokia{}'.format(alnum(version))
        return None


class SdoDirectory(ModuleGrouping):
    """Regular SDO directory containing yang modules."""

    def parse_and_load(self, repo: t.Optional[repoutil.RepoUtil] = None):
        """
        If modules were sent via the API, the contents of the request-data.json file are parsed
        and modules are loaded from Git repository.
        Otherwise, all the .yang files in the directory are parsed.

        Argument:
            :param repo     Git repository which contains .yang files
        """
        if self.api:
            self._parse_and_load_api()
        else:
            self._parse_and_load_not_api()

    def _parse_and_load_api(self):
        LOGGER.debug('Parsing sdo files sent via API')
        commit_hash = None
        with open(os.path.join(self.dir_paths['json'], 'request-data.json'), 'r') as f:
            sdos_json = json.load(f)
        sdos_list: t.List[dict] = sdos_json['modules']['module']
        sdos_count = len(sdos_list)
        for i, sdo in enumerate(sdos_list, start=1):
            # remove diacritics
            file_name = unicodedata.normalize('NFKD', os.path.basename(sdo['source-file']['path'])) \
                .encode('ascii', 'ignore').decode()
            LOGGER.info('Parsing {} {} out of {}'.format(file_name, i, sdos_count))
            self.repo_owner = sdo['source-file']['owner']
            repo_file_path = sdo['source-file']['path']
            self.repo_name = sdo['source-file']['repository'].split('.')[0]
            commit_hash = sdo['source-file']['commit-hash']
            root = os.path.join(self.repo_owner, self.repo_name, os.path.dirname(repo_file_path))
            root = os.path.join(self.dir_paths['json'], root)
            path = os.path.join(root, file_name)
            if not os.path.isfile(path):
                LOGGER.error('File {} sent via API was not downloaded'.format(file_name))
                continue
            if '[1]' in file_name:
                LOGGER.warning('File {} contains [1] it its file name'.format(file_name))
                continue
            # Openconfig modules are sent via API daily; see openconfigPullLocal.py script
            if '/openconfig/public/' in path:
                should_parse = self.file_hasher.should_parse_openconfig_module(path)
                if not should_parse:
                    continue
            name = file_name.split('.')[0].split('@')[0]
            schema_parts = SchemaParts(
                repo_owner=self.repo_owner, repo_name=self.repo_name, commit_hash=commit_hash)
            schema_base = schema_parts.schema_base
            self.parsed_jsons = LoadFiles(self._construct_json_name(schema_base, self.directory),
                                          self.dir_paths['private'], self.dir_paths['log'])
            try:
                yang = SdoModule(name, path, self.parsed_jsons, self.dir_paths, self.dumper.yang_modules,
                                 schema_parts, aditional_info=sdo)
            except ParseException:
                LOGGER.exception('ParseException while parsing {}'.format(file_name))
                continue
            self.dumper.add_module(yang)

    def _parse_and_load_not_api(self):
        LOGGER.debug('Parsing sdo files from directory')
        commit_hash = None
        self._load_yangmodels_repo()
        # Check if repository submodule
        submodule_name = self._check_if_submodule()

        for root, _, sdos in os.walk(self.directory):
            sdos_count = len(sdos)
            LOGGER.info('Searching {} files from directory {}'.format(sdos_count, root))
            commit_hash = self.repo.get_commit_hash(root, 'main')
            schema_parts = SchemaParts(
                repo_owner=self.repo_owner, repo_name=self.repo_name,
                commit_hash=commit_hash, submodule_name=submodule_name)
            schema_base = schema_parts.schema_base
            for i, file_name in enumerate(sdos, start=1):
                # Process only SDO .yang files
                if '.yang' not in file_name or any(word in root for word in ['vendor', 'odp']):
                    continue
                path = os.path.join(root, file_name)
                should_parse = self.file_hasher.should_parse_sdo_module(path)
                if not should_parse:
                    continue
                if '[1]' in file_name:
                    LOGGER.warning('File {} contains [1] it its file name'.format(file_name))
                    continue
                LOGGER.info('Parsing {} {} out of {}'.format(file_name, i, sdos_count))
                name = file_name.split('.')[0].split('@')[0]
                self.parsed_jsons = \
                    LoadFiles(self._construct_json_name(schema_base, os.path.join(self.directory, root)),
                              self.dir_paths['private'], self.dir_paths['log'])
                try:
                    yang = SdoModule(name, path, self.parsed_jsons, self.dir_paths,
                                     self.dumper.yang_modules, schema_parts)
                except ParseException:
                    LOGGER.exception('ParseException while parsing {}'.format(file_name))
                    continue
                self.dumper.add_module(yang)


class IanaDirectory(SdoDirectory):
    """Directory containing IANA modules."""

    def __init__(self, directory: str, dumper: Dumper, file_hasher: FileHasher,
                 api: bool, dir_paths: DirPaths):
        super().__init__(directory, dumper, file_hasher, api, dir_paths)
        self.root = ET.parse(os.path.join(directory, 'yang-parameters.xml')).getroot()

    def parse_and_load(self):
        """Parse all IANA-maintained modules listed in the yang-parameters.xml file."""
        tag = self.root.tag
        namespace = tag.split('registry')[0]
        modules = self.root.iter('{}record'.format(namespace))

        self._load_yangmodels_repo()
        commit_hash = self.repo.get_commit_hash(self.directory, 'main')
        schema_parts = SchemaParts(
            repo_owner=self.repo_owner, repo_name=self.repo_name, commit_hash=commit_hash)

        for yang in modules:
            additional_info = {}
            data = yang.attrib
            for attributes in yang:
                prop = attributes.tag.split(namespace)[-1]
                data[prop] = attributes.text if attributes.text else ''
                if prop == 'xref':
                    xref_info = attributes.attrib
                    if xref_info.get('type') == 'draft':
                        document_split = xref_info['data'].replace('RFC', 'draft').split('-')
                        version = document_split[-1]
                        name = '-'.join(document_split[:-1])
                        additional_info['document-name'] = '{}-{}.txt'.format(name, version)
                        additional_info['reference'] = 'https://datatracker.ietf.org/doc/{}/{}'.format(name, version)
                    else:
                        additional_info['document-name'] = xref_info.get('data')
                        additional_info['reference'] = 'https://datatracker.ietf.org/doc/{}'.format(xref_info.get('data'))
                additional_info['organization'] = 'ietf'

            if data.get('iana') == 'Y' and data.get('file'):
                path = os.path.join(self.directory, data['file'])
                should_parse = self.file_hasher.should_parse_sdo_module(path)
                if not should_parse:
                    continue
                module_name = data['file'].split('.yang')[0]

                LOGGER.info('Parsing module {}'.format(module_name))
                self.parsed_jsons = LoadFiles('IANAStandard', self.dir_paths['private'], self.dir_paths['log'])
                try:
                    yang = SdoModule(data['name'], path, self.parsed_jsons, self.dir_paths,
                                     self.dumper.yang_modules, schema_parts, additional_info)
                except ParseException:
                    LOGGER.exception('ParseException while parsing {}'.format(module_name))
                    continue
                self.dumper.add_module(yang)


class VendorGrouping(ModuleGrouping):

    parsed_jsons: LoadFiles

    def __init__(self, directory: str, xml_file: str, dumper: Dumper,
                 file_hasher: FileHasher, api: bool, dir_paths: DirPaths):
        super().__init__(directory, dumper, file_hasher, api, dir_paths)

        self.submodule_name = None
        self.found_capabilities = False
        self.capabilities = []
        self.netconf_versions = []
        self.platform_data = []
        self.xml_file = xml_file
        # Split path, so we can get vendor, os-type, os-version
        self.split = directory.split('/')
        # Get hello message root
        try:
            LOGGER.debug('Checking for xml hello message file')
            self.root = ET.parse(xml_file).getroot()
        except:
            # try to change & to &amp
            hello_file = fileinput.FileInput(xml_file, inplace=True)
            for line in hello_file:
                print(line.replace('&', '&amp;'), end='')
            hello_file.close()
            LOGGER.warning('Hello message file has & instead of &amp, automatically changing to &amp')
            self.root = ET.parse(xml_file).getroot()

    def _parse_platform_metadata(self):
        # Vendor modules send from API
        if self.api:
            with open('{}.json'.format(self.xml_file.removesuffix('.xml')), 'r') as f:
                implementation = json.load(f)
            LOGGER.debug('Getting capabilities out of api message')
            self._parse_implementation(implementation)
        # Vendor modules loaded from directory
        if not self.api:
            self._load_yangmodels_repo()
            self.submodule_name = self._check_if_submodule()
            branch = 'main'
            if self.submodule_name:
                branch = 'master'
            self.commit_hash = self.repo.get_commit_hash(branch=branch)
            metadata_path = os.path.join(self.directory, 'platform-metadata.json')
            if os.path.isfile(metadata_path):
                LOGGER.info('Parsing a platform-metadata.json file')
                with open(metadata_path, 'r') as f:
                    data = json.load(f)
                    platforms = data.get('platforms', {}).get('platform', [])
                for implementation in platforms:
                    self._parse_implementation(implementation)
            else:
                LOGGER.debug('Setting metadata concerning whole directory')
                # Solve for os-type
                base = os.path.basename(self.xml_file).removesuffix('.xml')
                if 'nx' in self.split:
                    platform_index = self.split.index('nx')
                    os_type = 'NX-OS'
                    platform = base.split('-')[0]
                elif 'xe' in self.split:
                    platform_index = self.split.index('xe')
                    os_type = 'IOS-XE'
                    platform = base.split('-')[0]
                elif 'xr' in self.split:
                    platform_index = self.split.index('xr')
                    os_type = 'IOS-XR'
                    platform = base.split('-')[1]
                else:
                    platform_index = -3
                    os_type = 'Unknown'
                    platform = 'Unknown'
                self.platform_data.append({
                    'software-flavor': 'ALL',
                    'platform': platform,
                    'software-version': self.split[platform_index + 1],
                    'os-version': self.split[platform_index + 1],
                    'feature-set': 'ALL',
                    'os': os_type,
                    'vendor': self.split[platform_index - 1]})

    def _parse_implementation(self, implementation: dict):
        if implementation['module-list-file']['path'] in self.xml_file:
            self._initialize_repo(implementation)
            self.platform_data.append({'software-flavor': implementation['software-flavor'],
                                       'platform': implementation['name'],
                                       'os-version': implementation['software-version'],
                                       'software-version': implementation['software-version'],
                                       'feature-set': 'ALL',
                                       'vendor': implementation['vendor'],
                                       'os': implementation['os-type']})
            raw_capabilities = implementation.get('netconf-capabilities')
            if raw_capabilities:
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
            LOGGER.debug('Getting netconf version')
            self.netconf_versions.append(raw_capability)
        # Parse capability together with version
        elif ':capability:' in raw_capability:
            self.capabilities.append(raw_capability.split('?')[0])

    def _parse_imp_inc(self, modules: list, set_of_names: set, is_include: bool, schema_parts: SchemaParts):
        """
        Parse all yang modules which are either sumodules or imports of a certain module.
        Submodules and import modules are also added to the dumper object.
        This method is then recursively called for all found submodules and imported modules.

        Arguments:
            :param modules          (list) List of modules to check (either submodules or imports of module)
            :param set_of_namea     (set) Set of all the modules parsed out from the capability file
            :param is_include       (bool) Whether module is include or not
            :param schema_parts     (SchemaParts) Parts of the URL to a raw module on Github
        """
        for module in modules:
            if not is_include:
                name = module.arg
                conformance_type = 'import'
            else:
                name = module.name
                conformance_type = None

            # Skip if name of submodule/import is already in list of module names
            if name not in set_of_names:
                LOGGER.info('Parsing module {}'.format(name))
                set_of_names.add(name)
                pattern = '{}.yang'.format(name)
                pattern_with_revision = '{}@*.yang'.format(name)
                yang_file = find_first_file(os.path.dirname(self.xml_file), pattern, pattern_with_revision)
                if yang_file is None:
                    return
                try:
                    try:
                        yang = VendorModule(name, yang_file, self.parsed_jsons, self.dir_paths,
                                            self.dumper.yang_modules, schema_parts)
                    except ParseException:
                        LOGGER.exception('ParseException while parsing {}'.format(name))
                        continue
                    yang.add_vendor_information(self.platform_data, conformance_type,
                                                self.capabilities, self.netconf_versions)
                    self.dumper.add_module(yang)
                    key = '{}@{}/{}'.format(yang.name, yang.revision, yang.organization)
                    set_of_names.add(yang.name)
                    self._parse_imp_inc(self.dumper.yang_modules[key].submodule, set_of_names, True, schema_parts)
                    self._parse_imp_inc(self.dumper.yang_modules[key].imports, set_of_names, False, schema_parts)
                except FileNotFoundError:
                    LOGGER.warning('File {} not found in the repository'.format(name))


class VendorCapabilities(VendorGrouping):
    """Modules listed in a capabilities xml file."""

    def parse_and_load(self):
        """
        Parse and load all information from the capabilities xml file and
        implementation data from a platform-metadata json file if present.
        """

        LOGGER.debug('Starting to parse files from vendor')
        set_of_names = set()
        keys = set()
        tag = self.root.tag

        self._parse_platform_metadata()

        # netconf capability parsing
        modules = self.root.iter('{}capability'.format(tag.split('hello')[0]))

        if not self.found_capabilities:
            LOGGER.debug('Getting capabilities out of hello message')
            for module in modules:
                # Parse netconf version
                if not module.text:
                    module.text = ''
                self._parse_raw_capability(module.text)
            modules = self.root.iter('{}capability'.format(tag.split('hello')[0]))

        try:
            schema_parts = SchemaParts(
                repo_owner=self.repo_owner, repo_name=self.repo_name,
                commit_hash=self.commit_hash, submodule_name=self.submodule_name)
            schema_base = schema_parts.schema_base
        except:
            LOGGER.exception('Missing attribute, likely caused by a broken path in {}/platform-metadata.json'
                             .format(self.directory))
            raise
        self.parsed_jsons = \
            LoadFiles(self._construct_json_name(schema_base, self.directory),
                      self.dir_paths['private'], self.dir_paths['log'])

        platform_name = self.platform_data[0].get('platform', '')
        # Parse modules
        for module in modules:
            module.text = module.text or ''
            if 'module=' not in module.text:
                continue
            # Parse name of the module
            module_and_more = module.text.split('module=')[1]
            module_name = module_and_more.split('&')[0]

            path = '{}/{}.yang'.format(self.directory, module_name)
            should_parse = False
            if os.path.exists(path):
                should_parse = self.file_hasher.should_parse_vendor_module(path, platform_name)
            if not should_parse:
                continue
            LOGGER.info('Parsing module {}'.format(module_name))
            try:
                try:
                    yang = VendorModule(module_name, path, self.parsed_jsons, self.dir_paths,
                                        self.dumper.yang_modules, schema_parts, data=module_and_more)
                except ParseException:
                    LOGGER.exception('ParseException while parsing {}'.format(module_name))
                    continue
                yang.add_vendor_information(self.platform_data, 'implement',
                                            self.capabilities, self.netconf_versions)
                self.dumper.add_module(yang)
                key = '{}@{}/{}'.format(yang.name, yang.revision, yang.organization)
                keys.add(key)
                set_of_names.add(yang.name)
            except FileNotFoundError:
                LOGGER.warning('File {} not found in the repository'.format(module_name))

        for key in keys:
            self._parse_imp_inc(self.dumper.yang_modules[key].submodule, set_of_names, True, schema_parts)
            self._parse_imp_inc(self.dumper.yang_modules[key].imports, set_of_names, False, schema_parts)


class VendorYangLibrary(VendorGrouping):

    def parse_and_load(self):
        """ Load implementation information which are stored platform-metadata.json file.
        Set this implementation information for each module parsed out from ietf-yang-library xml file.
        """

        LOGGER.debug('Starting to parse files from vendor')

        self._parse_platform_metadata()

        # netconf capability parsing
        modules = self.root[0]
        set_of_names = set()
        keys = set()
        schema_parts = SchemaParts(
            repo_owner=self.repo_owner, repo_name=self.repo_name,
            commit_hash=self.commit_hash, submodule_name=self.submodule_name)
        schema_base = schema_parts.schema_base
        self.parsed_jsons = \
            LoadFiles(self._construct_json_name(schema_base, self.directory),
                      self.dir_paths['private'], self.dir_paths['log'])
        for yang in modules:
            if 'module-set-id' in yang.tag:
                continue
            module_name = ''

            for mod in yang:
                if 'name' in mod.tag:
                    module_name = mod.text
                    if not module_name:
                        module_name = ''
                    break

            yang_lib_info = {}
            yang_lib_info['path'] = self.directory
            yang_lib_info['name'] = module_name
            yang_lib_info['features'] = []
            yang_lib_info['deviations'] = []
            conformance_type = None
            for mod in yang:
                if 'revision' in mod.tag:
                    yang_lib_info['revision'] = mod.text
                elif 'conformance-type' in mod.tag:
                    conformance_type = mod.text
                elif 'feature' in mod.tag:
                    yang_lib_info['features'].append(mod.text)
                elif 'deviation' in mod.tag:
                    deviation = {}
                    deviation['name'] = mod[0].text
                    deviation['revision'] = mod[1].text
                    yang_lib_info['deviations'].append(deviation)

            LOGGER.info('Starting to parse {}'.format(module_name))
            try:
                try:
                    yang = VendorModule(module_name, self.xml_file, self.parsed_jsons, self.dir_paths,
                                        self.dumper.yang_modules, schema_parts, data=yang_lib_info)
                except ParseException:
                    LOGGER.exception('ParseException while parsing {}'.format(module_name))
                    continue

                yang.add_vendor_information(self.platform_data, conformance_type,
                                            self.capabilities, self.netconf_versions)
                self.dumper.add_module(yang)
                keys.add('{}@{}/{}'.format(yang.name, yang.revision, yang.organization))
                set_of_names.add(yang.name)
            except FileNotFoundError:
                LOGGER.warning('File {} not found in the repository'.format(module_name))

        for key in keys:
            self._parse_imp_inc(self.dumper.yang_modules[key].submodule, set_of_names, True, schema_parts)
            self._parse_imp_inc(self.dumper.yang_modules[key].imports, set_of_names, False, schema_parts)
