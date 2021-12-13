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

__author__ = "Slavomir Mazur"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "slavomir.mazur@pantheon.tech"

import fileinput
import json
import os
import unittest
from unittest import mock

from api.globalConfig import yc_gc
from parseAndPopulate.capability import Capability
from parseAndPopulate.fileHasher import FileHasher
from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.modules import Modules
from parseAndPopulate.prepare import Prepare
from utility import repoutil
from utility.staticVariables import github_raw, github_url


class TestCapabilityClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestCapabilityClass, self).__init__(*args, **kwargs)

        # Declare variables
        self.tmp_dir = '{}/'.format(yc_gc.temp_dir)
        self.yangcatalog_api_prefix = '{}/api/'.format(yc_gc.my_uri)
        self.prepare_output_filename = 'prepare'
        self.hello_message_filename = 'capabilities-ncs5k.xml'
        self.platform_name = 'ncs5k'
        self.resources_path = '{}/resources'.format(os.path.dirname(os.path.abspath(__file__)))
        self.test_private_dir = 'tests/resources/html/private'
        self.fileHasher = FileHasher('test_modules_hashes', yc_gc.cache_dir, False, yc_gc.logs_dir)

    #########################
    ### TESTS DEFINITIONS ###
    #########################

    @mock.patch('parseAndPopulate.capability.repoutil.RepoUtil.get_commit_hash')
    def test_capability_parse_and_dump_sdo(self, mock_hash: mock.MagicMock):
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
        sdo = True
        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)

        capability = Capability(yc_gc.logs_dir, path, prepare,
                                None, api, sdo, self.tmp_dir, yc_gc.result_dir,
                                yc_gc.save_file_dir, self.test_private_dir, yc_gc.yang_models, self.fileHasher)

        capability.parse_and_dump_sdo(repo)

        for root, _, sdos in os.walk(path):
            for file_name in sdos:
                if '.yang' in file_name and ('vendor' not in root or 'odp' not in root):
                    path_to_yang = '{}/{}'.format(path, file_name)
                    yang = self.declare_sdo_module(path_to_yang)
                    key = '{}@{}/{}'.format(yang.name, yang.revision, yang.organization)
                    self.assertIn(key, capability.prepare.yang_modules)

    @mock.patch('parseAndPopulate.capability.repoutil.RepoUtil.get_commit_hash')
    def test_capability_parse_and_dump_sdo_api(self, mock_hash: mock.MagicMock):
        """
        Test whether key was created and prepare object value was set correctly
        from all modules loaded from prepare-sdo.json file.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        """
        mock_hash.return_value = 'master'
        repo = self.get_yangmodels_repository()

        path = '{}/capability-tests/temp'.format(yc_gc.temp_dir)
        json_dir = '{}/capability-tests'.format(yc_gc.temp_dir)
        api = True
        sdo = True

        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)

        capability = Capability(yc_gc.logs_dir, path, prepare,
                                None, api, sdo, json_dir, yc_gc.result_dir,
                                yc_gc.save_file_dir, self.test_private_dir, yc_gc.yang_models, self.fileHasher)

        capability.parse_and_dump_sdo(repo)

        with open('{}/prepare-sdo.json'.format(json_dir), 'r') as f:
            sdos_json = json.load(f)

        sdos_list = sdos_json.get('modules', {}).get('module', [])
        self.assertNotEqual(len(sdos_list), 0)
        for sdo in sdos_list:
            key = '{}@{}/{}'.format(sdo.get('name'), sdo.get('revision'), sdo.get('organization'))
            self.assertIn(key, capability.prepare.yang_modules)

    @mock.patch('parseAndPopulate.capability.repoutil.RepoUtil.get_commit_hash')
    @mock.patch('parseAndPopulate.prepare.requests.get')
    def test_capability_parse_and_dump_sdo_submodule(self, mock_requests_get: mock.MagicMock, mock_hash: mock.MagicMock):
        """
        Test whether keys were created and prepare object values were set correctly
        from all the .yang files which are located in 'path' directory. Created 'path' is submodule of git repository.

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return only the necessary modules
        :param mock_hash            (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        """
        mock_requests_get.return_value.json = {}
        mock_hash.return_value = 'master'
        path = '{}/master/vendor/huawei/network-router/8.20.0/ne5000e'.format(yc_gc.temp_dir)
        repo = self.get_yangmodels_repository()
        api = False
        sdo = True
        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)

        capability = Capability(yc_gc.logs_dir, path, prepare,
                                None, api, sdo, self.tmp_dir, yc_gc.result_dir,
                                yc_gc.save_file_dir, self.test_private_dir, yc_gc.yang_models, self.fileHasher)

        capability.parse_and_dump_sdo(repo)
        capability.prepare.dump_modules(self.tmp_dir)

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
                            self.assertEqual(dumped_module[key], desired_module[key])

    @mock.patch('parseAndPopulate.capability.repoutil.RepoUtil.get_commit_hash')
    def test_capability_parse_and_dump_vendor(self, mock_hash: mock.MagicMock):
        """ Test if all the modules from capability file (with their submodules) have correctly set information
        about implementaton from platform_metadata.json file.
        Parsed modules are dumped to prepare.json file, then loaded and implementation information is chcecked.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        """
        mock_hash.return_value = 'master'
        xml_path = '{}/master/vendor/cisco/xr/701/{}'.format(yc_gc.temp_dir, self.hello_message_filename)
        platform_json_path = '{}/master/vendor/cisco/xr/701/platform-metadata.json'.format(yc_gc.temp_dir)
        api = False
        sdo = False
        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)

        capability = Capability(yc_gc.logs_dir, xml_path, prepare,
                                None, api, sdo, self.tmp_dir, yc_gc.result_dir,
                                yc_gc.save_file_dir, self.test_private_dir, yc_gc.yang_models, self.fileHasher)

        capability.parse_and_dump_vendor()
        capability.prepare.dump_modules(self.tmp_dir)

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

    def test_capability_ampersand_exception(self):
        """ Test if ampersand character will be replaced in .xml file if occurs.
        If ampersand character occurs, exception is raised, and character is replaced.
        """
        xml_path = '{}/master/vendor/cisco/xr/701/{}'.format(yc_gc.temp_dir, self.hello_message_filename)
        api = False
        sdo = False
        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)

        # Change to achieve Exception will be raised
        hello_file = fileinput.FileInput(xml_path, inplace=True)
        for line in hello_file:
            print(line.replace('&amp;', '&'), end='')
        hello_file.close()

        capability = Capability(yc_gc.logs_dir, xml_path, prepare,
                                None, api, sdo, self.tmp_dir, yc_gc.result_dir,
                                yc_gc.save_file_dir, self.test_private_dir, yc_gc.yang_models, self.fileHasher)

        self.assertEqual(capability.root.tag, '{urn:ietf:params:xml:ns:netconf:base:1.0}hello')

    def test_capability_solve_xr_os_type(self):
        """ Test if platform_data are set correctly when platform_metadata.json file is not present in the folder.
        """
        xml_path = '{}/master/vendor/cisco/xr/702/capabilities-ncs5k.xml'.format(yc_gc.temp_dir)
        api = False
        sdo = False

        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)

        capability = Capability(yc_gc.logs_dir, xml_path, prepare,
                                None, api, sdo, self.tmp_dir, yc_gc.result_dir,
                                yc_gc.save_file_dir, self.test_private_dir, yc_gc.yang_models, self.fileHasher)

        platform_data = capability.platform_data
        # Load desired module data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            desired_platform_data = file_content.get('xr_platform_data', {})

        self.assertNotEqual(len(platform_data), 0)
        self.assertNotEqual(len(desired_platform_data), 0)
        self.assertEqual(desired_platform_data, platform_data[0])

    def test_capability_solve_nx_os_type(self):
        """ Test if platform_data are set correctly when platform_metadata.json file is not present in the folder.
        """
        xml_path = '{}/master/vendor/cisco/nx/9.2-1/netconf-capabilities.xml'.format(yc_gc.temp_dir)
        api = False
        sdo = False

        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)

        capability = Capability(yc_gc.logs_dir, xml_path, prepare,
                                None, api, sdo, self.tmp_dir, yc_gc.result_dir,
                                yc_gc.save_file_dir, self.test_private_dir, yc_gc.yang_models, self.fileHasher)

        platform_data = capability.platform_data
        # Load desired module data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            desired_platform_data = file_content.get('nx_platform_data', {})

        self.assertNotEqual(len(platform_data), 0)
        self.assertNotEqual(len(desired_platform_data), 0)
        self.assertEqual(desired_platform_data, platform_data[0])

    def test_capability_solve_xe_os_type(self):
        """ Test if platform_data are set correctly when platform_metadata.json file is not present in the folder.
        """
        xml_path = '{}/master/vendor/cisco/xe/16101/capability-asr1k.xml'.format(yc_gc.temp_dir)
        api = False
        sdo = False

        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)

        capability = Capability(yc_gc.logs_dir, xml_path, prepare,
                                None, api, sdo, self.tmp_dir, yc_gc.result_dir,
                                yc_gc.save_file_dir, self.test_private_dir, yc_gc.yang_models, self.fileHasher)

        platform_data = capability.platform_data
        # Load desired module data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            desired_platform_data = file_content.get('xe_platform_data', {})

        self.assertNotEqual(len(platform_data), 0)
        self.assertNotEqual(len(desired_platform_data), 0)
        self.assertEqual(desired_platform_data, platform_data[0])

    @mock.patch('parseAndPopulate.capability.repoutil.RepoUtil.get_commit_hash')
    def test_capability_parse_and_dump_yang_lib(self, mock_hash: mock.MagicMock):
        """ Test if all the modules from ietf-yang-library xml file (with their submodules) have correctly set information
        about implementaton from platform_metadata.json file.
        Parsed modules are dumped to prepare.json file, then loaded and implementation information is checked.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        """
        mock_hash.return_value = 'master'
        xml_path = '{}/master/vendor/huawei/network-router/8.20.0/ne5000e/ietf-yang-library.xml'.format(yc_gc.temp_dir)
        platform_json_path = '{}/master/vendor/huawei/network-router/8.20.0/ne5000e/platform-metadata.json'.format(yc_gc.temp_dir)
        platform_name = 'ne5000e'
        api = False
        sdo = False
        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)

        capability = Capability(yc_gc.logs_dir, xml_path, prepare,
                                None, api, sdo, self.tmp_dir, yc_gc.result_dir,
                                yc_gc.save_file_dir, self.test_private_dir, yc_gc.yang_models, self.fileHasher)

        capability.parse_and_dump_yang_lib()
        capability.prepare.dump_modules(self.tmp_dir)

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
        parsed_jsons = LoadFiles(self.test_private_dir, yc_gc.logs_dir)
        module_name = path_to_yang.split('/')[-1].split('.yang')[0]
        schema = '{}/YangModels/yang/master/standard/ietf/RFC/{}.yang'.format(github_raw, module_name)
        if '@' in module_name:
            module_name = module_name.split('@')[0]

        yang = Modules(yc_gc.yang_models, yc_gc.logs_dir, path_to_yang,
                       yc_gc.result_dir, parsed_jsons, self.tmp_dir)
        yang.parse_all('master', module_name, {}, schema,
                       None, yc_gc.save_file_dir)

        return yang

    def get_yangmodels_repository(self):
        """ Load existing cloned Github repository from directory instead.

        :returns:       Loaded Github repository
        :rtype:         repoutil.Repo
        """
        repo_url = '{}/{}/{}'.format(github_url, 'YangModels', 'yang')
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
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            desired_module_data = file_content.get(key, {}).get('module', [])
        return desired_module_data

    def load_dumped_prepare_json_data(self):
        """ Load module data from dumped prepare.json file
        """
        with open('{}/prepare.json'.format(yc_gc.temp_dir), 'r') as f:
            file_content = json.load(f)
            self.assertIn('module', file_content)
            self.assertNotEqual(len(file_content['module']), 0)
        dumped_module_data = file_content['module']
        return dumped_module_data


if __name__ == "__main__":
    unittest.main()
