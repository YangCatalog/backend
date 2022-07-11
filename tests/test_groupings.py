# Copyright The IETF Trust 2021, All Rights Reserved
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

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

import fileinput
import json
import os
import unittest
from unittest import mock

from api.globalConfig import yc_gc
from parseAndPopulate.dir_paths import DirPaths
from parseAndPopulate.dumper import Dumper
from parseAndPopulate.fileHasher import FileHasher
from parseAndPopulate.groupings import (SdoDirectory, VendorCapabilities,
                                        VendorYangLibrary)
from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.modules import SdoModule
from parseAndPopulate.models.schema_parts import SchemaParts
from utility import repoutil
from utility.staticVariables import github_url


class TestGroupingsClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestGroupingsClass, self).__init__(*args, **kwargs)

        # Declare variables
        self.prepare_output_filename = 'prepare'
        self.hello_message_filename = 'capabilities-ncs5k.xml'
        self.platform_name = 'ncs5k'
        self.resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        self.test_private_dir = os.path.join(self.resources_path, 'html/private')
        self.fileHasher = FileHasher('test_modules_hashes', yc_gc.cache_dir, False, yc_gc.logs_dir)
        self.dir_paths: DirPaths = {
            'cache': '',
            'json': os.path.join(yc_gc.temp_dir, 'groupings-tests'),
            'log': yc_gc.logs_dir,
            'private': self.test_private_dir,
            'result': yc_gc.result_dir,
            'save': yc_gc.save_file_dir,
            'yang_models': yc_gc.yang_models
        }
        self.test_repo = os.path.join(yc_gc.temp_dir, 'test/YangModels/yang')

    #########################
    ### TESTS DEFINITIONS ###
    #########################

    @mock.patch('parseAndPopulate.groupings.repoutil.RepoUtil.get_commit_hash')
    def test_sdo_directory_parse_and_load(self, mock_hash: mock.MagicMock):
        """
        Test whether keys were created and prepare object values were set correctly
        from all the .yang files which are located in 'path' directory.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        """
        mock_hash.return_value = 'master'
        repo = self.get_yangmodels_repository()
        path = '{}/standard/ieee/published/802.3'.format(yc_gc.yang_models)
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        sdo_directory = SdoDirectory(path, dumper, self.fileHasher, api, self.dir_paths)

        sdo_directory.parse_and_load(repo)

        for root, _, sdos in os.walk(path):
            for file_name in sdos:
                if '.yang' in file_name and ('vendor' not in root or 'odp' not in root):
                    path_to_yang = os.path.join(path, file_name)
                    yang = self.declare_sdo_module(path_to_yang)
                    key = '{}@{}/{}'.format(yang.name, yang.revision, yang.organization)
                    self.assertIn(key, sdo_directory.dumper.yang_modules)

    @mock.patch('parseAndPopulate.groupings.repoutil.RepoUtil.get_commit_hash')
    def test_sdo_directory_parse_and_load_api(self, mock_hash: mock.MagicMock):
        """
        Test whether key was created and prepare object value was set correctly
        from all modules loaded from request-data.json file.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        """
        mock_hash.return_value = 'master'
        repo = self.get_yangmodels_repository()
        path = os.path.join(yc_gc.temp_dir, 'groupings-tests')
        api = True
        sdo = True

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        sdo_directory = SdoDirectory(path, dumper, self.fileHasher, api, self.dir_paths)

        sdo_directory.parse_and_load(repo)
        with open(os.path.join(self.dir_paths['json'], 'request-data.json'), 'r') as f:
            sdos_json = json.load(f)

        sdos_list = sdos_json.get('modules', {}).get('module', [])
        self.assertNotEqual(len(sdos_list), 0)
        for sdo in sdos_list:
            key = '{}@{}/{}'.format(sdo.get('name'), sdo.get('revision'), sdo.get('organization'))
            self.assertIn(key, sdo_directory.dumper.yang_modules)

    @mock.patch('parseAndPopulate.groupings.repoutil.RepoUtil.get_commit_hash')
    def test_sdo_directory_parse_and_load_submodule(self, mock_hash: mock.MagicMock):
        """
        Test whether keys were created and dumper object values were set correctly
        from all the .yang files which are located in 'path' directory. Created 'path' is submodule of git repository.

        Arguments:
        :param mock_hash            (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        """
        mock_hash.return_value = 'master'
        path = os.path.join(self.test_repo, 'vendor/huawei/network-router/8.20.0/ne5000e')
        xml_file = os.path.join(path, 'ietf-yang-library.xml')
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_yang_lib = VendorYangLibrary(path, xml_file, dumper, self.fileHasher, api, self.dir_paths)

        with mock.patch.object(vendor_yang_lib, '_construct_json_name', lambda x, y: 'IETFTEST'):
            vendor_yang_lib.parse_and_load()
        vendor_yang_lib.dumper.dump_modules(yc_gc.temp_dir)

        desired_module_data = self.load_desired_prepare_json_data('git_submodule_huawei')
        dumped_module_data = self.load_dumped_prepare_json_data()

        # Compare desired output with output of prepare.json
        for dumped_module in dumped_module_data:
            for desired_module in desired_module_data:
                if desired_module.get('name') == dumped_module.get('name'):
                    # Compare properties/keys of desired and dumped module data objects
                    for key in desired_module:
                        if key == 'yang-tree':
                            # Compare only URL suffix (exclude domain)
                            desired_tree_suffix = '/api{}'.format(desired_module[key].split('/api')[1])
                            dumped_tree_suffix = '/api{}'.format(dumped_module[key].split('/api')[1])
                            self.assertEqual(desired_tree_suffix, dumped_tree_suffix)
                        elif key == 'compilation-result':
                            if dumped_module[key] != '' and desired_module[key] != '':
                                # Compare only URL suffix (exclude domain)
                                desired_compilation_result = '/results{}'.format(desired_module[key].split('/results')[-1])
                                dumped_compilation_result = '/results{}'.format(dumped_module[key].split('/results')[-1])
                                self.assertEqual(desired_compilation_result, dumped_compilation_result)
                        else:
                            if isinstance(desired_module[key], list):
                                for i in desired_module[key]:
                                    self.assertIn(i, dumped_module[key])
                            else:
                                self.assertEqual(dumped_module[key], desired_module[key])

    @mock.patch('parseAndPopulate.groupings.repoutil.RepoUtil.get_commit_hash')
    def test_vendor_capabilities_parse_and_load(self, mock_hash: mock.MagicMock):
        """ Test if all the modules from capability file (with their submodules) have correctly set information
        about implementaton from platform_metadata.json file.
        Parsed modules are dumped to prepare.json file, then loaded and implementation information is chcecked.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        """
        mock_hash.return_value = 'master'
        directory = os.path.join(self.test_repo, 'vendor/cisco/xr/701')
        xml_file = os.path.join(directory, self.hello_message_filename)
        platform_json_path = os.path.join(self.test_repo, 'vendor/cisco/xr/701/platform-metadata.json')
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_capabilities = VendorCapabilities(directory, xml_file, dumper, self.fileHasher, api, self.dir_paths)

        vendor_capabilities.parse_and_load()
        vendor_capabilities.dumper.dump_modules(yc_gc.temp_dir)

        dumped_modules_data = self.load_dumped_prepare_json_data()
        self.assertNotEqual(len(dumped_modules_data), 0)

        platform_data = self.get_platform_data(platform_json_path, self.platform_name)

        for yang_module in dumped_modules_data:
            self.assertIn('implementations', yang_module)
            implementations = yang_module.get('implementations', {}).get('implementation', [])
            self.assertNotEqual(len(implementations), 0)
            for implementation in implementations:
                if implementation.get('platform') == self.platform_name:
                    self.assertEqual(implementation.get('vendor'), platform_data.get('vendor'))
                    self.assertEqual(implementation.get('platform'), platform_data.get('name'))
                    self.assertEqual(implementation.get('software-version'), platform_data.get('software-version'))
                    self.assertEqual(implementation.get('software-flavor'), platform_data.get('software-flavor'))
                    self.assertEqual(implementation.get('os-version'), platform_data.get('software-version'))
                    self.assertEqual(implementation.get('feature-set'), 'ALL')
                    self.assertEqual(implementation.get('os-type'), platform_data.get('os-type'))

    def test_vendor_capabilities_ampersand_exception(self):
        """ Test if ampersand character will be replaced in .xml file if occurs.
        If ampersand character occurs, exception is raised, and character is replaced.
        """
        directory = os.path.join(self.test_repo, 'vendor/cisco/xr/701')
        xml_file = os.path.join(directory, self.hello_message_filename)
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        # Change to achieve Exception will be raised
        hello_file = fileinput.FileInput(xml_file, inplace=True)
        for line in hello_file:
            print(line.replace('&amp;', '&'), end='')
        hello_file.close()

        vendor_capabilities = VendorCapabilities(directory, xml_file, dumper, self.fileHasher, api, self.dir_paths)

        self.assertEqual(vendor_capabilities.root.tag, '{urn:ietf:params:xml:ns:netconf:base:1.0}hello')

    def test_vendor_capabilities_solve_xr_os_type(self):
        """ Test if platform_data are set correctly when platform_metadata.json file is not present in the folder.
        """
        directory = os.path.join(self.test_repo, 'vendor/cisco/xr/702')
        xml_file = os.path.join(directory, 'capabilities-ncs5k.xml')
        api = False

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_capabilities = VendorCapabilities(directory, xml_file, dumper, self.fileHasher, api, self.dir_paths)
        vendor_capabilities._parse_platform_metadata()

        platform_data = vendor_capabilities.platform_data
        # Load desired module data from .json file
        with open(os.path.join(self.resources_path, 'parseAndPopulate_tests_data.json'), 'r') as f:
            file_content = json.load(f)
            desired_platform_data = file_content.get('xr_platform_data', {})

        self.assertNotEqual(len(platform_data), 0)
        self.assertEqual(desired_platform_data, platform_data[0])

    def test_vendor_capabilities_solve_nx_os_type(self):
        """ Test if platform_data are set correctly when platform_metadata.json file is not present in the folder.
        """
        directory = os.path.join(self.test_repo, 'vendor/cisco/nx/9.2-1')
        xml_file = os.path.join(directory, 'netconf-capabilities.xml')
        api = False

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_capabilities = VendorCapabilities(directory, xml_file, dumper, self.fileHasher, api, self.dir_paths)
        vendor_capabilities._parse_platform_metadata()

        platform_data = vendor_capabilities.platform_data
        # Load desired module data from .json file
        with open(os.path.join(self.resources_path, 'parseAndPopulate_tests_data.json'), 'r') as f:
            file_content = json.load(f)
            desired_platform_data = file_content.get('nx_platform_data', {})

        self.assertNotEqual(len(platform_data), 0)
        self.assertEqual(desired_platform_data, platform_data[0])

    def test_vendor_capabilities_solve_xe_os_type(self):
        """ Test if platform_data are set correctly when platform_metadata.json file is not present in the folder.
        """
        directory = os.path.join(self.test_repo, 'vendor/cisco/xe/16101')
        xml_file = os.path.join(directory, 'capability-asr1k.xml')
        api = False

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_capabilities = VendorCapabilities(directory, xml_file, dumper, self.fileHasher, api, self.dir_paths)
        vendor_capabilities._parse_platform_metadata()

        platform_data = vendor_capabilities.platform_data
        # Load desired module data from .json file
        with open(os.path.join(self.resources_path, 'parseAndPopulate_tests_data.json'), 'r') as f:
            file_content = json.load(f)
            desired_platform_data = file_content.get('xe_platform_data', {})

        self.assertNotEqual(len(platform_data), 0)
        self.assertEqual(desired_platform_data, platform_data[0])

    @mock.patch('parseAndPopulate.groupings.repoutil.RepoUtil.get_commit_hash')
    def test_vendor_yang_lib_parse_and_dump(self, mock_hash: mock.MagicMock):
        """ Test if all the modules from ietf-yang-library xml file (with their submodules) have correctly set information
        about implementaton from platform_metadata.json file.
        Parsed modules are dumped to prepare.json file, then loaded and implementation information is checked.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        """
        mock_hash.return_value = 'master'
        directory = os.path.join(self.test_repo, 'vendor/huawei/network-router/8.20.0/ne5000e')
        xml_file = os.path.join(directory, 'ietf-yang-library.xml')
        platform_json_path = os.path.join(self.test_repo,
                                          'vendor/huawei/network-router/8.20.0/ne5000e/platform-metadata.json')
        platform_name = 'ne5000e'
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_yang_lib = VendorYangLibrary(directory, xml_file, dumper, self.fileHasher, api, self.dir_paths)

        vendor_yang_lib.parse_and_load()
        vendor_yang_lib.dumper.dump_modules(yc_gc.temp_dir)

        dumped_modules_data = self.load_dumped_prepare_json_data()

        platform_data = self.get_platform_data(platform_json_path, platform_name)

        self.assertNotEqual(len(platform_data), 0)
        self.assertNotEqual(len(dumped_modules_data), 0)
        for yang_module in dumped_modules_data:
            self.assertIn('implementations', yang_module)
            implementations = yang_module.get('implementations', {}).get('implementation', [])
            self.assertNotEqual(len(implementations), 0)
            for implementation in implementations:
                if implementation.get('platform') == platform_name:
                    self.assertEqual(implementation.get('vendor'), platform_data.get('vendor'))
                    self.assertEqual(implementation.get('platform'), platform_data.get('name'))
                    self.assertEqual(implementation.get('software-version'), platform_data.get('software-version'))
                    self.assertEqual(implementation.get('software-flavor'), platform_data.get('software-flavor'))
                    self.assertEqual(implementation.get('os-version'), platform_data.get('software-version'))
                    self.assertEqual(implementation.get('feature-set'), 'ALL')
                    self.assertEqual(implementation.get('os-type'), platform_data.get('os-type'))

    ##########################
    ### HELPER DEFINITIONS ###
    ##########################

    def declare_sdo_module(self, path_to_yang: str):
        """
        Initialize Modules object for SDO (ietf) module.

        :param path_to_yang     (str) path to yang file
        :returns:               Created instance of Modules object of SDO (ietf) module
        :rtype: Modules
        """
        parsed_jsons = LoadFiles('IETFYANGRFC', self.test_private_dir, yc_gc.logs_dir)
        module_name = path_to_yang.split('/')[-1].split('.yang')[0]
        if '@' in module_name:
            module_name = module_name.split('@')[0]
        schema_parts = SchemaParts(repo_owner='YangModels', repo_name='yang', commit_hash='master')
        yang = SdoModule(module_name, path_to_yang, parsed_jsons, self.dir_paths, {}, schema_parts)

        return yang

    def get_yangmodels_repository(self):
        """ Load existing cloned Github repository from directory instead.

        :returns:       Loaded Github repository
        :rtype:         repoutil.Repo
        """
        repo_url = os.path.join(github_url, 'YangModels', 'yang')
        repo = repoutil.load(yc_gc.yang_models, repo_url)

        return repo

    def get_platform_data(self, path: str, platform_name: str):
        """ Load information of given platform from platform-metadata.json

        :param path              (str) Directory where platform-metadata.json file is stored
        :param platform_name     (str) Name of platform to find
        :returns:                Platform information loaded from platform-metadata.json
        :rtype: dict
        """
        with open(path, 'r') as f:
            file_content = json.load(f)
            platforms = file_content.get('platforms', {}).get('platform', [])
        platform_data = {}
        for platform in platforms:
            if platform.get('name') == platform_name:
                platform_data = platform

        return platform_data

    def load_desired_prepare_json_data(self, key: str):
        """ Load desired prepare.json data from parseAndPopulate_tests_data.json file
        """
        with open(os.path.join(self.resources_path, 'parseAndPopulate_tests_data.json'), 'r') as f:
            file_content = json.load(f)
            desired_module_data = file_content.get(key, {}).get('module', [])
        return desired_module_data

    def load_dumped_prepare_json_data(self):
        """ Load module data from dumped prepare.json file
        """
        with open(os.path.join(yc_gc.temp_dir, 'prepare.json'), 'r') as f:
            file_content = json.load(f)
            self.assertIn('module', file_content)
            self.assertNotEqual(len(file_content['module']), 0)
        dumped_module_data = file_content['module']
        return dumped_module_data


if __name__ == '__main__':
    unittest.main()
