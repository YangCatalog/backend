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

import json
import os
import time
import unittest
from unittest import mock

from api.globalConfig import yc_gc
from parseAndPopulate.loadJsonFiles import LoadFiles
from utility import repoutil
from utility.util import hash_file


class TestRunCapabilitiesClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestRunCapabilitiesClass, self).__init__(*args, **kwargs)
        self.module_name = 'parseAndPopulate'
        self.script_name = 'runCapabilities'
        self.resources_path = '{}/resources'.format(os.path.dirname(os.path.abspath(__file__)))
        self.test_result_html_dir = 'tests/resources/html/results'
        self.test_private_dir = 'tests/resources/html/private'

    #########################
    ### TESTS DEFINITIONS ###
    #########################

    @mock.patch('parseAndPopulate.capability.LoadFiles')
    @mock.patch('parseAndPopulate.capability.repoutil.RepoUtil.get_commit_hash')
    def test_runCapabilities_parse_and_dump_sdo(self, mock_hash: mock.MagicMock, mock_load_files: mock.MagicMock):
        """ Run runCapability script over yang files in directory. Compare content of normal.json and prepare.json files.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        :param mock_load_files  (mock.MagicMock) LoadFiles is patched to load json files from test directory
        """
        mock_hash.return_value = 'master'
        mock_load_files.return_value = LoadFiles(self.test_private_dir, yc_gc.logs_dir)
        path = '{}/tmp/temp/standard/ietf/RFC'.format(self.resources_path)
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()
        # Set script arguments
        script_conf.args.__setattr__('sdo', True)
        script_conf.args.__setattr__('dir', path)
        script_conf = self.set_script_conf_arguments(script_conf)

        # Run runCapabilities.py script with corresponding configuration
        submodule.main(scriptConf=script_conf)

        # Load desired module data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            desired_module_data = file_content.get('dumped_module', {}).get('module', [])[0]

        # Load module data from dumped prepare.json file
        with open('{}/prepare.json'.format(yc_gc.temp_dir), 'r') as f:
            file_content = json.load(f)
            self.assertIn('module', file_content)
            self.assertNotEqual(len(file_content['module']), 0)
        dumped_module_data = file_content['module'][0]

        # Compare properties/keys of desired and dumped module data objects
        for key in desired_module_data:
            if key == 'yang-tree':
                # Compare only URL suffix (exclude domain)
                desired_tree_suffix = '/api{}'.format(desired_module_data[key].split('/api')[1])
                dumped_tree_suffix = '/api{}'.format(dumped_module_data[key].split('/api')[1])
                self.assertEqual(desired_tree_suffix, dumped_tree_suffix)
            elif key == 'compilation-result':
                if dumped_module_data[key] != '' and desired_module_data[key] != '':
                    # Compare only URL suffix (exclude domain)
                    desired_compilation_result = '/results{}'.format(desired_module_data[key].split('/results')[1])
                    dumped_compilation_result = '/results{}'.format(dumped_module_data[key].split('/results')[1])
                    self.assertEqual(desired_compilation_result, dumped_compilation_result)
            else:
                self.assertEqual(dumped_module_data[key], desired_module_data[key])

    @mock.patch('parseAndPopulate.capability.LoadFiles')
    @mock.patch('parseAndPopulate.capability.repoutil.RepoUtil.get_commit_hash')
    def test_runCapabilities_parse_and_dump_vendor(self, mock_commit_hash: mock.MagicMock, mock_load_files: mock.MagicMock):
        """ Run runCapability script over capability xml. Compare content of normal.json and prepare.json files.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        :param mock_load_files  (mock.MagicMock) LoadFiles is patched to load json files from test directory
        """
        mock_commit_hash.return_value = 'master'
        mock_load_files.return_value = LoadFiles(self.test_private_dir, yc_gc.logs_dir)
        xml_path = '{}/tmp/master/vendor/cisco/xr/701'.format(self.resources_path)
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()
        # Set arguments
        script_conf.args.__setattr__('sdo', False)
        script_conf.args.__setattr__('dir', xml_path)
        script_conf = self.set_script_conf_arguments(script_conf)

        # Run runCapabilities.py script with corresponding configuration
        submodule.main(scriptConf=script_conf)

        # Load desired prepare.json data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            desired_module_data = file_content.get('ncs5k_prepare_json', {}).get('module', [])

        # Load module data from dumped prepare.json file
        with open('{}/prepare.json'.format(yc_gc.temp_dir), 'r') as f:
            file_content = json.load(f)
            self.assertIn('module', file_content)
            self.assertNotEqual(len(file_content['module']), 0)
        dumped_module_data = file_content['module']

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
                                desired_compilation_result = '/results{}'.format(desired_module[key].split('/results')[1])
                                dumped_compilation_result = '/results{}'.format(dumped_module[key].split('/results')[1])
                                self.assertEqual(desired_compilation_result, dumped_compilation_result)
                        else:
                            self.assertEqual(dumped_module[key], desired_module[key])

        # Load desired normal.json data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            desired_vendor_data = file_content.get('ncs5k_normal_json', {}).get('vendors', {}). get('vendor', [])
            self.assertNotEqual(len(desired_vendor_data), 0)

        # Load vendor module data from normal.json file
        with open('{}/normal.json'.format(yc_gc.temp_dir), 'r') as f:
            file_content = json.load(f)
            self.assertIn('vendors', file_content)
            self.assertIn('vendor', file_content.get('vendors', []))
            self.assertNotEqual(len(file_content['vendors']['vendor']), 0)
            dumped_vendor_data = file_content.get('vendors', {}).get('vendor', [])

        for dumped_vendor in dumped_vendor_data:
            self.assertIn(dumped_vendor, desired_vendor_data)

    def test_runCapabilities_parse_and_dump_vendor_save_modification_date(self):
        """ Run runCapability script over capability xml. Set save_modification_date argument to True, so value from
        filesModifications.json will be compared with actual values.
        Set value before runCapability script to be sure that value will be stored in filesModifications.json file.
        """
        xml_path = '{}/tmp/master/vendor/cisco/xr/701'.format(self.resources_path)
        capability_xml_path = '{}/capabilities-ncs5k.xml'.format(xml_path)
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()
        # Set arguments
        script_conf.args.__setattr__('sdo', False)
        script_conf.args.__setattr__('dir', xml_path)
        script_conf.args.__setattr__('save_modification_date', True)
        script_conf = self.set_script_conf_arguments(script_conf)

        # Set value of hash for xml file before running runCapability.py script
        file_hash = hash_file(capability_xml_path)
        files_modifications = self.get_file_modification_date()
        files_modifications[capability_xml_path] = file_hash
        path = '{}/filesModifications.json'.format(yc_gc.temp_dir)
        with open(path, 'w') as file_modification:
            json.dump(files_modifications, file_modification)

        # Run runCapabilities.py script with corresponding configuration
        submodule.main(scriptConf=script_conf)

        path = '{}/filesModifications.json'.format(yc_gc.temp_dir)
        with open(path, 'r') as file_modification:
            files_modifications = json.load(file_modification)

        self.assertIn(capability_xml_path, files_modifications)
        self.assertEqual(files_modifications[capability_xml_path], file_hash)

    @mock.patch('parseAndPopulate.runCapabilities.Capability')
    @mock.patch('parseAndPopulate.runCapabilities.Capability.parse_and_dump')
    def test_runCapabilities_parse_and_dump_vendor_save_modification_date_changed_date(
            self, mock_capability_method: mock.MagicMock, mock_capability: mock.MagicMock):
        """ Run runCapability script over capability xml. Set save_modification_date argument to True, so value from
        filesModifications.json will be compared with actual values.
        Set value of hash to random value before runCapability script to be sure that value will be stored in filesModifications.json file
        and also it will be overwritten.

        Arguments:
        :param mock_capability          (mock.MagicMock) Capability object is patched - does not need to be executed for this test
        :param mock_capability_method   (mock.MagicMock) parse_and_dump() method is patched - does not need to be executed for this test
        """
        xml_path = '{}/tmp/master/vendor/cisco/xr/701'.format(self.resources_path)
        capability_xml_path = '{}/capabilities-ncs5k.xml'.format(xml_path)
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()
        # Set arguments
        script_conf.args.__setattr__('sdo', False)
        script_conf.args.__setattr__('dir', xml_path)
        script_conf.args.__setattr__('save_modification_date', True)
        script_conf = self.set_script_conf_arguments(script_conf)

        # Set value of hash for xml file before running runCapability.py script
        files_modifications = self.get_file_modification_date()
        files_modifications[capability_xml_path] = 'Random-hash-value'
        path = '{}/filesModifications.json'.format(yc_gc.temp_dir)
        with open(path, 'w') as file_modification:
            json.dump(files_modifications, file_modification)

        # Run runCapabilities.py script with corresponding configuration
        submodule.main(scriptConf=script_conf)

        files_modifications = self.get_file_modification_date()
        file_hash = hash_file(capability_xml_path)

        self.assertIn(capability_xml_path, files_modifications)
        self.assertEqual(files_modifications[capability_xml_path], file_hash)

    def test_runCapabilities_parse_and_dump_vendor_non_existing_xml(self):
        """ Non-existing path is passed as 'dir' argument to the capability.py script which means
        that no capability xml file is found inside this directory.
        Test whether both prepare.json and normal.json files contain only empty dictionary '{}'.
        """
        xml_path = 'non/existing/path'
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()
        # Set arguments
        script_conf.args.__setattr__('sdo', False)
        script_conf.args.__setattr__('dir', xml_path)
        script_conf = self.set_script_conf_arguments(script_conf)

        # Run runCapabilities.py script with corresponding configuration
        submodule.main(scriptConf=script_conf)

        # Load module data from dumped prepare.json file
        with open('{}/prepare.json'.format(yc_gc.temp_dir), 'r') as f:
            file_content = json.load(f)
        self.assertEqual(file_content, {})

        # Load vendor module data from normal.json file
        with open('{}/normal.json'.format(yc_gc.temp_dir), 'r') as f:
            file_content = json.load(f)
        self.assertEqual(file_content, {})

    @mock.patch('parseAndPopulate.capability.LoadFiles')
    @mock.patch('parseAndPopulate.capability.repoutil.RepoUtil.get_commit_hash')
    def test_runCapabilities_parse_and_dump_vendor_yang_lib(self, mock_hash: mock.MagicMock, mock_load_files: mock.MagicMock):
        """ Run runCapability script over yang_lib.xml. Compare content of normal.json and prepare.json files.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        :param mock_load_files  (mock.MagicMock) LoadFiles is patched to load json files from test directory
        """
        mock_load_files.return_value = LoadFiles(self.test_private_dir, yc_gc.logs_dir)
        mock_hash.return_value = 'master'
        xml_path = '{}/tmp/master/vendor/huawei/network-router/8.9.10'.format(self.resources_path)
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()
        # Set arguments
        script_conf.args.__setattr__('sdo', False)
        script_conf.args.__setattr__('dir', xml_path)
        script_conf = self.set_script_conf_arguments(script_conf)

        # Run runCapabilities.py script with corresponding configuration
        submodule.main(scriptConf=script_conf)

        # Load desired prepare.json data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            desired_module_data = file_content.get('yang_lib_prepare_json', {}).get('module', [])

        # Load module data from dumped prepare.json file
        with open('{}/prepare.json'.format(yc_gc.temp_dir), 'r') as f:
            file_content = json.load(f)
            self.assertIn('module', file_content)
            self.assertNotEqual(len(file_content['module']), 0)
        dumped_module_data = file_content['module']

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
                                desired_compilation_result = '/results{}'.format(desired_module[key].split('/results')[1])
                                dumped_compilation_result = '/results{}'.format(dumped_module[key].split('/results')[1])
                                self.assertEqual(desired_compilation_result, dumped_compilation_result)
                        else:
                            self.assertEqual(dumped_module[key], desired_module[key])

        # Load desired normal.json data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            desired_vendor_data = file_content.get('yang_lib_normal_json', {}).get('vendors', {}). get('vendor', [])
            self.assertNotEqual(len(desired_vendor_data), 0)

        # Load vendor module data from normal.json file
        with open('{}/normal.json'.format(yc_gc.temp_dir), 'r') as f:
            file_content = json.load(f)
            self.assertIn('vendors', file_content)
            self.assertIn('vendor', file_content.get('vendors', []))
            self.assertNotEqual(len(file_content['vendors']['vendor']), 0)
            dumped_vendor_data = file_content.get('vendors', {}).get('vendor', [])

        for dumped_vendor in dumped_vendor_data:
            self.assertIn(dumped_vendor, desired_vendor_data)

    def test_runCapabilities_get_help(self):
        """ Test whether script help has the correct structure (check only structure not content).
        """
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()

        script_help = script_conf.get_help()

        self.assertIn('help', script_help)
        self.assertIn('options', script_help)
        self.assertNotEqual(script_help.get('options'), {})

    def test_runCapabilities_get_args_list(self):
        """ Test whether script default arguments has the correct structure (check only structure not content).
        """
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()

        script_args_list = script_conf.get_args_list()

        self.assertNotEqual(script_args_list, {})
        for key in script_args_list:
            self.assertIn('type', script_args_list.get(key))
            self.assertIn('default', script_args_list.get(key))

        ##########################
        ### HELPER DEFINITIONS ###
        ##########################

    def set_script_conf_arguments(self, script_conf):
        """ Set values to ScriptConfig arguments to be able to run in test environment.

        :returns        ScriptConfig with arguments set.
        """
        script_conf.args.__setattr__('api_protocol', 'http')
        script_conf.args.__setattr__('api_ip', 'non-existing-site.com')  # requests.get() will fail
        script_conf.args.__setattr__('result_html_dir', yc_gc.result_dir)
        script_conf.args.__setattr__('save_file_dir', yc_gc.save_file_dir)
        script_conf.args.__setattr__('json_dir', yc_gc.temp_dir)

        return script_conf

    def get_file_modification_date(self):
        """ Load file modification dates from json file.

        :returns    Loaded data from json as dictionary
        :rtype      Dict
        """
        path = '{}/filesModifications.json'.format(yc_gc.temp_dir)
        try:
            with open(path, 'r') as file_modification:
                file_modification_dates = json.load(file_modification)
        except:
            file_modification_dates = {}
        return file_modification_dates


if __name__ == "__main__":
    unittest.main()
