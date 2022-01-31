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

"""
Capability class will parse all the capability.xml files
and pulls all the information from platfom-metadata.json file
if it exist or it will parse ietf-yang-library.xml file if such
file exists, or it will start to parse all the files that are
in the directory if there is none xml or json files mentioned above
and it will store them as sdos since we don t have any vendor
information about them
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import fileinput
import json
import os
import re
import typing as t
import unicodedata
import xml.etree.ElementTree as ET

import utility.log as log
from utility import repoutil
from utility.staticVariables import github_raw, github_url
from utility.util import find_first_file

from parseAndPopulate.fileHasher import FileHasher
from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.modules import Modules
from parseAndPopulate.parseException import ParseException
from parseAndPopulate.prepare import Prepare


class Capability:

    def __init__(self, log_directory: str, hello_message_file: str, prepare: Prepare, integrity_checker,
                 api: bool, sdo: bool, json_dir: str, html_result_dir: str, save_file_to_dir: str, private_dir: str,
                 yang_models_dir: str, fileHasher: FileHasher):
        """
        Preset Capability class to get capabilities from directory passed as argument.
        Based on passed arguments, Capability object will:
        I. parse all the capability.xml files and pulls all the information from platfom-metadata.json file if it exists
        II. parse ietf-yang-library.xml file if such file exists
        III. start to parse all the yang files in the directory if there are none .xml or .json files mentioned above

        :param log_directory        (str) directory where the log file is saved
        :param hello_message_file   (str) path to hello_message .xml file or path to directory containing yang files
        :param prepare              (Prepare) prepare object
        :param integrity_checker:   (obj) integrity checker object
        :param api                  (bool) whether request came from API or not
        :param sdo                  (bool) whether processing sdo (= True) or vendor (= False) yang modules
        :param json_dir             (str) path to the directory where .json file to populate Confd will be stored
        :param html_result_dir      (str) path to the directory with HTML result files
        :param save_file_to_dir     (str) path to the directory where all the yang files will be saved
        :param private_dir          (str) path to the directory with private HTML result files
        :param yang_models_dir      (str) path to the directory where YangModels/yang repo is cloned
        :param filehasher           (FileHasher) fileHasher object
        """

        global LOGGER
        LOGGER = log.get_logger('capability', '{}/parseAndPopulate.log'.format(log_directory))
        LOGGER.debug('Running Capability constructor')
        self.logger = log.get_logger('repoutil', '{}/parseAndPopulate.log'.format(log_directory))
        self.log_directory = log_directory
        self.save_file_to_dir = save_file_to_dir
        self.html_result_dir = html_result_dir
        self.json_dir = json_dir
        self.prepare = prepare
        self.integrity_checker = integrity_checker
        self.api = api
        self.path = None
        self.yang_models_dir = yang_models_dir
        self.fileHasher = fileHasher
        # Get hello message root
        if hello_message_file.endswith('.xml'):
            try:
                LOGGER.debug('Checking for xml hello message file')
                self.root = ET.parse(hello_message_file).getroot()
            except:
                # try to change & to &amp
                hello_file = fileinput.FileInput(hello_message_file, inplace=True)
                for line in hello_file:
                    print(line.replace('&', '&amp;'), end='')
                hello_file.close()
                LOGGER.warning('Hello message file has & instead of &amp, automatically changing to &amp')
                self.root = ET.parse(hello_message_file).getroot()
        # Split path, so we can get vendor, os-type, os-version
        self.split = hello_message_file.split('/')
        self.hello_message_file = hello_message_file

        # Vendor modules send from API
        if self.api and not sdo:
            self.platform_data = []
            with open('{}.json'.format(hello_message_file.split('.xml')[0]), 'r') as f:
                impl = json.load(f)
            self.initialize(impl)
        # Vendor modules loaded from directory
        if not self.api and not sdo:
            path = '/'.join(self.split[:-1])
            if os.path.isfile('{}/platform-metadata.json'.format(path)):
                self.platform_data = []
                with open('{}/platform-metadata.json'.format(path), 'r') as f:
                    data = json.load(f)
                    platforms = data.get('platforms', {}).get('platform', [])
                for implementation in platforms:
                    self.initialize(implementation)
            else:
                self.platform_data = []
                LOGGER.debug('Setting metadata concerning whole directory')
                self.owner = 'YangModels'
                self.repo = 'yang'
                repo_url = '{}/{}/{}'.format(github_url, self.owner, self.repo)
                repo = repoutil.load(self.yang_models_dir, repo_url)
                if repo is None:
                    repo = repoutil.RepoUtil(repo_url, self.logger)
                    repo.clone()
                self.path = None
                self.branch = 'master'
                self.branch = repo.get_commit_hash(self.branch)
                repo.remove()
                # Solve for os-type
                if 'nx' in self.split:
                    platform_index = self.split.index('nx')
                    os_type = 'NX-OS'
                    platform = self.split[platform_index + 2].split('.xml')[0].split('-')[0]
                elif 'xe' in self.split:
                    platform_index = self.split.index('xe')
                    os_type = 'IOS-XE'
                    platform = self.split[platform_index + 2].split('.xml')[0].split('-')[0]
                elif 'xr' in self.split:
                    platform_index = self.split.index('xr')
                    os_type = 'IOS-XR'
                    platform = self.split[platform_index + 2].split('.xml')[0].split('-')[1]
                else:
                    platform_index = -3
                    os_type = 'Unknown'
                    platform = 'Unknown'
                self.platform_data.append(
                    {'software-flavor': 'ALL',
                     'platform': platform,
                     'software-version': self.split[platform_index + 1],
                     'os-version': self.split[platform_index + 1],
                     'feature-set': 'ALL',
                     'os': os_type,
                     'vendor': self.split[platform_index - 1]})
        self.parsed_jsons = LoadFiles(private_dir, log_directory)

    def initialize(self, impl: dict):
        if impl['module-list-file']['path'] in self.hello_message_file:
            LOGGER.info('Parsing a received platform-metadata.json file')
            self.owner = impl.get('module-list-file', {}).get('owner')
            self.repo = impl.get('module-list-file', {}).get('repository')
            if self.repo is not None:
                self.repo = self.repo.split('.')[0]
            self.path = impl.get('module-list-file', {}).get('path')
            self.branch = impl.get('module-list-file', {}).get('branch', '')
            repo_url = '{}/{}/{}'.format(github_url, self.owner, self.repo)
            repo = None
            if self.owner == 'YangModels' and self.repo == 'yang':
                repo = repoutil.load(self.yang_models_dir, repo_url)
            if repo is None:
                repo = repoutil.RepoUtil(repo_url, self.logger)
                repo.clone()
            if not self.branch:
                self.branch = 'master'
            self.branch = repo.get_commit_hash(self.branch)
            repo.remove()
            self.platform_data.append({'software-flavor': impl['software-flavor'],
                                       'platform': impl['name'],
                                       'os-version': impl['software-version'],
                                       'software-version': impl['software-version'],
                                       'feature-set': 'ALL',
                                       'vendor': impl['vendor'],
                                       'os': impl['os-type']})

    def parse_and_dump_sdo(self, repo: t.Optional[repoutil.RepoUtil] = None):
        """ If modules were sent via API, content of prepare-sdo.json file is parsed and modules are loaded from Git repository.
        Otherwise, all the .yang files in the directory are parsed.

        Argument:
            :param repo     Git repository which contains .yang files
        """
        branch = None
        if self.api:
            LOGGER.debug('Parsing sdo files sent via API')
            with open('{}/prepare-sdo.json'.format(self.json_dir), 'r') as f:
                sdos_json = json.load(f)
            sdos_list = sdos_json.get('modules', {}).get('module', [])
            sdos_count = len(sdos_list)
            for i, sdo in enumerate(sdos_list, start=1):
                file_name = unicodedata.normalize('NFKD', sdo.get('source-file', {}).get('path').split('/')[-1]) \
                    .encode('ascii', 'ignore')
                LOGGER.info('Parsing {} {} out of {}'.format(file_name.decode('utf-8', 'strict'), i, sdos_count))
                self.owner = sdo.get('source-file', {}).get('owner')
                repo_file_path = sdo.get('source-file', {}).get('path')
                self.repo = sdo.get('source-file', {}).get('repository', '').split('.')[0]
                if repo is None:
                    repo = repoutil.RepoUtil('{}/{}/{}'.format(github_url, self.owner, self.repo), self.logger)
                    repo.clone()
                self.branch = sdo.get('source-file', {}).get('branch', '')
                if not self.branch:
                    self.branch = 'master'
                if branch is None:
                    branch = repo.get_commit_hash('/'.join(repo_file_path.split('/')[:-1]), self.branch)
                root = '{}/{}/{}/{}'.format(self.owner, self.repo, branch, '/'.join(repo_file_path.split('/')[:-1]))
                root = '{}/temp/{}'.format(self.json_dir, root)
                file_name = file_name.decode()
                path = '{}/{}'.format(root, file_name)
                if not os.path.isfile(path):
                    LOGGER.error('File {} sent via API was not downloaded'.format(file_name))
                    continue
                if '[1]' not in file_name:
                    try:
                        yang = Modules(self.yang_models_dir, self.log_directory, path,
                                       self.html_result_dir, self.parsed_jsons, self.json_dir)
                    except ParseException:
                        LOGGER.exception('ParseException while parsing {}'.format(file_name))
                        continue
                    name = file_name.split('.')[0].split('@')[0]
                    schema = '{}/{}/{}/{}/{}'.format(github_raw, self.owner, self.repo, branch, repo_file_path)
                    yang.parse_all(branch, name,
                                   self.prepare.name_revision_organization,
                                   schema, self.path, self.save_file_to_dir, sdo)
                    self.prepare.add_key_sdo_module(yang)

        else:
            LOGGER.debug('Parsing sdo files from directory')
            # Load/clone YangModels/yang repo
            self.owner = 'YangModels'
            self.repo = 'yang'
            repo_url = '{}/{}/{}'.format(github_url, self.owner, self.repo)
            repo = repoutil.load(self.yang_models_dir, repo_url)
            if repo is None:
                repo = repoutil.RepoUtil(repo_url, self.logger)
                repo.clone()
            assert repo.repo is not None, 'Failed to initialize git repo'
            is_submodule = False
            # Check if repository submodule
            submodule_name = ''
            for submodule in repo.repo.submodules:
                if submodule.name in '/'.join(self.split):
                    is_submodule = True
                    submodule_name = submodule.name
                    repo_url = submodule.url
                    repo_dir = '{}/{}'.format(self.yang_models_dir, submodule_name)
                    repo = repoutil.load(repo_dir, repo_url)
                    assert repo is not None, 'Failed to initialize git repo'
                    self.owner = repo.get_repo_owner()
                    self.repo = repo.get_repo_dir().split('.git')[0]

            for root, _, sdos in os.walk('/'.join(self.split)):
                sdos_count = len(sdos)
                LOGGER.info('Searching {} files from directory {}'.format(sdos_count, root))
                for i, file_name in enumerate(sdos, start=1):
                    # Process only SDO .yang files
                    if '.yang' in file_name and ('vendor' not in root or 'odp' not in root):
                        path = '{}/{}'.format(root, file_name)
                        should_parse = self.fileHasher.should_parse_sdo_module(path)
                        if not should_parse:
                            continue
                        if '[1]' in file_name:
                            LOGGER.warning('File {} contains [1] it its file name'.format(file_name))
                        else:
                            LOGGER.info('Parsing {} {} out of {}'.format(file_name, i, sdos_count))
                            try:
                                yang = Modules(self.yang_models_dir, self.log_directory, path,
                                               self.html_result_dir, self.parsed_jsons, self.json_dir)
                            except ParseException:
                                LOGGER.exception('ParseException while parsing {}'.format(file_name))
                                continue
                            name = file_name.split('.')[0].split('@')[0]
                            # Check if not submodule
                            if is_submodule:
                                path = path.replace('{}/'.format(submodule_name), '')
                            self.branch = 'master'
                            abs_path = os.path.abspath(path)
                            if '/yangmodels/yang/' in abs_path:
                                path = abs_path.split('/yangmodels/yang/')[1]
                            else:
                                path = re.split(r'tmp\/\w*\/', abs_path)[1]
                            if branch is None:
                                branch = repo.get_commit_hash(path, self.branch)
                            schema = '{}/{}/{}/{}/{}'.format(github_raw, self.owner, self.repo, branch, path)
                            yang.parse_all(branch, name,
                                           self.prepare.name_revision_organization,
                                           schema, self.path, self.save_file_to_dir)
                            self.prepare.add_key_sdo_module(yang)
        if repo is not None:
            repo.remove()

    def parse_and_dump_yang_lib(self):
        """ Load implementation information which are stored platform-metadata.json file.
        Set this implementation information for each module parsed out from ietf-yang-library xml file.
        """
        LOGGER.debug('Starting to parse files from vendor')
        capabilities = []
        netconf_version = []
        LOGGER.debug('Getting capabilities out of api message')
        if self.api:
            with open('{}.json'.format(self.hello_message_file.split('.xml')[0])) as f:
                impl = json.load(f)
            caps = impl['platforms'].get('netconf-capabilities')
            if caps:
                for cap in caps:
                    capability = cap
                    # Parse netconf version
                    if ':netconf:base:' in capability:
                        netconf_version.append(capability)
                        LOGGER.debug('Getting netconf version')
                    # Parse capability together with version
                    elif ':capability:' in capability:
                        cap_with_version = capability
                        capabilities.append(cap_with_version.split('?')[0])
        else:
            path = '/'.join(self.split[:-1])
            if os.path.isfile('{}/platform-metadata.json'.format(path)):
                with open('{}/platform-metadata.json'.format(path), 'r') as f:
                    data = json.load(f)
                    platforms = data.get('platforms', {}).get('platform', [])
                for implementation in platforms:
                    if implementation['module-list-file']['path'] in self.hello_message_file:
                        caps = implementation.get('netconf-capabilities')
                        if caps:
                            for cap in caps:
                                capability = cap
                                # Parse netconf version
                                if ':netconf:base:' in capability:
                                    netconf_version.append(capability)
                                    LOGGER.debug('Getting netconf version')
                                # Parse capability together with version
                                elif ':capability:' in capability:
                                    cap_with_version = capability
                                    capabilities.append(
                                        cap_with_version.split('?')[0])

        # netconf capability parsing
        modules = self.root[0]
        set_of_names = set()
        keys = set()
        schema_part = '{}/{}/{}/{}/'.format(github_raw, self.owner, self.repo, self.branch)
        for module in modules:
            if 'module-set-id' in module.tag:
                continue
            LOGGER.debug('Getting capabilities out of yang-library xml message')
            module_name = ''

            for mod in module:
                if 'name' in mod.tag:
                    module_name = mod.text
                    if not module_name:
                        module_name = ''
                    break

            yang_lib_info = {}
            yang_lib_info['path'] = '/'.join(self.split[0:-1])
            yang_lib_info['name'] = module_name
            yang_lib_info['features'] = []
            yang_lib_info['deviations'] = []
            conformance_type = None
            for mod in module:
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

            try:
                try:
                    yang = Modules(self.yang_models_dir, self.log_directory,
                                   '/'.join(self.split), self.html_result_dir,
                                   self.parsed_jsons, self.json_dir, True, True,
                                   yang_lib_info)
                except ParseException:
                    LOGGER.exception('ParseException while parsing {}'.format(module_name))
                    continue

                yang.parse_all(self.branch, module_name,
                               self.prepare.name_revision_organization,
                               schema_part, self.path, self.save_file_to_dir)
                yang.add_vendor_information(self.platform_data,
                                            conformance_type,
                                            capabilities, netconf_version,
                                            self.integrity_checker,
                                            self.split)
                self.prepare.add_key_sdo_module(yang)
                keys.add('{}@{}/{}'.format(yang.name, yang.revision, yang.organization))
                set_of_names.add(yang.name)
            except FileNotFoundError:
                LOGGER.warning('File {} not found in the repository'.format(module_name))

            LOGGER.info('Starting to parse {}'.format(module_name))

        for key in keys:
            self.parse_imp_inc(self.prepare.yang_modules[key].submodule,
                               set_of_names, True, schema_part, capabilities,
                               netconf_version)
            self.parse_imp_inc(self.prepare.yang_modules[key].imports,
                               set_of_names, False, schema_part, capabilities,
                               netconf_version)

    def parse_and_dump_vendor(self):
        """ Load implementation information which are stored platform-metadata.json file.
        Set this implementation information for each module parsed out from capability xml file.
        """
        LOGGER.debug('Starting to parse files from vendor')
        capabilities = []
        netconf_version = []
        set_of_names = set()
        keys = set()
        tag = self.root.tag

        # netconf capability parsing
        modules = self.root.iter('{}capability'.format(tag.split('hello')[0]))
        capabilities_exist = False
        LOGGER.debug('Getting capabilities out of hello message')
        path = '/'.join(self.split[:-1])
        if os.path.isfile('{}/platform-metadata.json'.format(path)):
            with open('{}/platform-metadata.json'.format(path), 'r') as f:
                data = json.load(f)
                platforms = data.get('platforms', {}).get('platform', [])
            for implementation in platforms:
                if implementation['module-list-file']['path'] in self.hello_message_file:
                    caps = implementation.get('netconf-capabilities')
                    if caps:
                        capabilities_exist = True
                        for capability in caps:
                            # Parse netconf version
                            if ':netconf:base:' in capability:
                                netconf_version.append(capability)
                                LOGGER.debug('Getting netconf version')
                            # Parse capability together with version
                            elif ':capability:' in capability:
                                cap_with_version = capability
                                capabilities.append(cap_with_version.split('?')[0])

        LOGGER.debug('Getting capabilities out of hello message')
        if not capabilities_exist:
            for module in modules:
                # Parse netconf version
                if not module.text:
                    module.text = ''
                if ':netconf:base:' in module.text:
                    netconf_version.append(module.text)
                    LOGGER.debug('Getting netconf version')
                # Parse capability together with version
                if ':capability:' in module.text:
                    cap_with_version = module.text.split(':capability:')[1]
                    capabilities.append(cap_with_version.split('?')[0])
            modules = self.root.iter('{}capability'.format(tag.split('hello')[0]))

        try:
            schema_part = '{}/{}/{}/{}/'.format(github_raw, self.owner, self.repo, self.branch)
        except:
            LOGGER.exception('Missing attribute, likely caused by a broken path in {}/platform-metadata.json'
                             .format('/'.join(self.split[:-1])))
            raise

        platform_name = self.platform_data[0].get('platform', '')
        modules_count = len(list(modules))
        # Parse modules
        for i, module in enumerate(modules, start=1):
            if 'module=' in module.text:
                # Parse name of the module
                module_and_more = module.text.split('module=')[1]
                module_name = module_and_more.split('&')[0]

                path = '{}/{}.yang'.format('/'.join(self.split[:-1]), module_name)
                should_parse = False
                if os.path.exists(path):
                    should_parse = self.fileHasher.should_parse_vendor_module(path, platform_name)
                if not should_parse:
                    continue
                LOGGER.info('Parsing {} {} out of {}'.format(module_name, i, modules_count))
                try:
                    try:
                        yang = Modules(self.yang_models_dir, self.log_directory, '/'.join(self.split),
                                       self.html_result_dir, self.parsed_jsons,
                                       self.json_dir, True, data=module_and_more)
                    except ParseException:
                        LOGGER.exception('ParseException while parsing {}'.format(module_name))
                        continue
                    yang.parse_all(self.branch, module_name,
                                   self.prepare.name_revision_organization,
                                   schema_part, self.path, self.save_file_to_dir)
                    yang.add_vendor_information(self.platform_data,
                                                'implement',
                                                capabilities,
                                                netconf_version,
                                                self.integrity_checker,
                                                self.split)
                    self.prepare.add_key_sdo_module(yang)
                    key = '{}@{}/{}'.format(yang.name, yang.revision, yang.organization)
                    keys.add(key)
                    set_of_names.add(yang.name)
                except FileNotFoundError:
                    LOGGER.warning('File {} not found in the repository'.format(module_name))

        for key in keys:
            self.parse_imp_inc(self.prepare.yang_modules[key].submodule,
                               set_of_names, True, schema_part, capabilities,
                               netconf_version)
            self.parse_imp_inc(self.prepare.yang_modules[key].imports,
                               set_of_names, False, schema_part, capabilities,
                               netconf_version)

    def parse_and_dump_iana(self):
        """ List of modules to parse is defined in 'yang-parameters.xml' file.
        This method parse all available IANA-maintained .yang files in the directory.
        """
        tag = self.root.tag
        namespace = tag.split('registry')[0]
        modules = self.root.iter('{}record'.format(namespace))

        git_commit_hash = None
        for module in modules:
            additional_info = {}
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
                        additional_info['document-name'] = '{}-{}.txt'.format(name, version)
                        additional_info['reference'] = 'https://datatracker.ietf.org/doc/{}/{}'.format(name, version)
                    else:
                        additional_info['document-name'] = xref_info.get('data')
                        additional_info['reference'] = 'https://datatracker.ietf.org/doc/{}'.format(xref_info.get('data'))
                additional_info['organization'] = 'ietf'

            if data.get('iana') == 'Y' and data.get('file'):
                self.owner = 'YangModels'
                self.repo = 'yang'
                repo_url = '{}/{}/{}'.format(github_url, self.owner, self.repo)
                repo = repoutil.load(self.yang_models_dir, repo_url)
                if repo is None:
                    repo = repoutil.RepoUtil(repo_url, self.logger)
                    repo.clone()
                path = '{}/{}'.format('/'.join(self.split[:-1]), data['file'])
                should_parse = self.fileHasher.should_parse_sdo_module(path)
                if not should_parse:
                    continue
                module_name = data['file'].split('.yang')[0]
                LOGGER.info('Parsing module {}'.format(module_name))

                try:
                    yang = Modules(self.yang_models_dir, self.log_directory, path,
                                   self.html_result_dir, self.parsed_jsons, self.json_dir)
                except ParseException:
                    LOGGER.exception('ParseException while parsing {}'.format(module_name))
                    continue
                self.branch = 'master'
                abs_path = os.path.abspath(path)
                if '/yangmodels/yang/' in abs_path:
                    path = abs_path.split('/yangmodels/yang/')[1]
                else:
                    path = re.split(r'tmp\/\w*\/', abs_path)[1]
                if git_commit_hash is None:
                    git_commit_hash = repo.get_commit_hash(path, self.branch)

                schema = '{}/{}/{}/{}/{}'.format(github_raw, self.owner, self.repo, git_commit_hash, path)
                yang.parse_all(git_commit_hash, data['name'],
                               self.prepare.name_revision_organization,
                               schema, self.path, self.save_file_to_dir, additional_info)
                self.prepare.add_key_sdo_module(yang)

    def parse_imp_inc(self, modules: list, set_of_names: set, is_include: bool, schema_part: str,
                      capabilities: list, netconf_version: list):
        """
        Parse all yang modules which are either sumodules or imports of certain module.
        Submodule and import modules are also added to prepare object.
        This method is then recursively called for all found submodules and import modules.

        :param modules          (list) List of modules to check (either submodules or imports of module)
        :param set_of_name      (set) Set of all the modules parsed out from capability file
        :param is_include       (bool) Whether module is include or not
        :param schema_part      (str)  Part of Github schema URL
        :param capabilities     (list) List of capabilities parsed out from capability file
        :param netconf_version  (list) List of netconf versions parsed out from capability file
        """
        for module in modules:
            if is_include:
                name = module.name
                conformance_type = 'import'
            else:
                conformance_type = None
                name = module.arg

            # Skip if name of submodule/import is already in list of module names
            if name not in set_of_names:
                LOGGER.info('Parsing module {}'.format(name))
                set_of_names.add(name)
                path = '/'.join(self.split[0:-1])
                pattern = '{}.yang'.format(name)
                pattern_with_revision = '{}@*.yang'.format(name)
                yang_file = find_first_file(path, pattern, pattern_with_revision, self.yang_models_dir)

                if yang_file is None:
                    # TODO add integrity that this file is missing
                    return
                try:
                    try:
                        yang = Modules(self.yang_models_dir, self.log_directory,
                                       yang_file, self.html_result_dir,
                                       self.parsed_jsons, self.json_dir,
                                       is_vendor_imp_inc=True)
                    except ParseException:
                        LOGGER.exception('ParseException while parsing {}'.format(name))
                        continue
                    yang.parse_all(self.branch, name,
                                   self.prepare.name_revision_organization,
                                   schema_part, self.path, self.save_file_to_dir)
                    yang.add_vendor_information(self.platform_data,
                                                conformance_type, capabilities,
                                                netconf_version,
                                                self.integrity_checker,
                                                self.split)
                    self.prepare.add_key_sdo_module(yang)
                    self.parse_imp_inc(yang.submodule, set_of_names, True,
                                       schema_part, capabilities, netconf_version)
                    self.parse_imp_inc(yang.imports, set_of_names, False,
                                       schema_part, capabilities, netconf_version)
                except FileNotFoundError:
                    LOGGER.warning('File {} not found in the repository'.format(name))
