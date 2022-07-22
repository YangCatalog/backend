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

import json
import os
import unittest
from unittest import mock

from api.globalConfig import yc_gc
from parseAndPopulate.loadJsonFiles import LoadFiles


class TestRunCapabilitiesClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestRunCapabilitiesClass, self).__init__(*args, **kwargs)
        self.module_name = 'parseAndPopulate'
        self.script_name = 'runCapabilities'
        self.resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        self.test_private_dir = os.path.join(self.resources_path, 'html/private')

    #########################
    ### TESTS DEFINITIONS ###
    #########################

    @mock.patch('parseAndPopulate.groupings.LoadFiles')
    @mock.patch('parseAndPopulate.groupings.repoutil.RepoUtil.get_commit_hash')
    def test_runCapabilities_parse_and_dump_sdo(self, mock_hash: mock.MagicMock, mock_load_files: mock.MagicMock):
        """ Run runCapabilities.py script over SDO yang files in directory.
        For testing purposes there is only 1 yang file (ietf-yang-types@2013-07-15.yang) in directory.
        Compare content of prepare.json files.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        :param mock_load_files  (mock.MagicMock) LoadFiles is patched to load json files from test directory
        """
        mock_hash.return_value = 'master'
        mock_load_files.return_value = LoadFiles('IETFTEST', self.test_private_dir, yc_gc.logs_dir)
        path = '{}/test/YangModels/yang/standard/ietf/RFC'.format(yc_gc.temp_dir)
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

        desired_module_data = self.load_desired_prepare_json_data('dumped_module')
        dumped_module_data = self.load_dumped_prepare_json_data()

        self.compare_prepare_data(desired_module_data, dumped_module_data)

    @mock.patch('parseAndPopulate.groupings.LoadFiles')
    @mock.patch('parseAndPopulate.groupings.repoutil.RepoUtil.get_commit_hash')
    def test_runCapabilities_parse_and_dump_sdo_empty_dir(self, mock_hash: mock.MagicMock, mock_load_files: mock.MagicMock):
        """ Run runCapabilities.py script over empty directory - no yang files.
        Test whether prepare.json file contain only empty dictionary '{}'.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        :param mock_load_files  (mock.MagicMock) LoadFiles is patched to load json files from test directory
        """
        mock_hash.return_value = 'master'
        mock_load_files.return_value = LoadFiles('IETFYANGRFC', self.test_private_dir, yc_gc.logs_dir)
        path = '{}/temp/standard/ietf/RFC/empty'.format(yc_gc.temp_dir)
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

        # Load module data from dumped prepare.json file
        with open('{}/prepare.json'.format(yc_gc.temp_dir), 'r') as f:
            file_content = json.load(f)
        self.assertEqual(file_content, {})

    @mock.patch('parseAndPopulate.groupings.LoadFiles')
    @mock.patch('parseAndPopulate.groupings.repoutil.RepoUtil.get_commit_hash')
    def test_runCapabilities_parse_and_dump_vendor(self, mock_commit_hash: mock.MagicMock, mock_load_files: mock.MagicMock):
        """ Run runCapabilities.py script over vendor yang files in directory which also contains capability xml file.
        Compare content of normal.json and prepare.json files.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        :param mock_load_files  (mock.MagicMock) LoadFiles is patched to load json files from test directory
        """
        mock_commit_hash.return_value = 'master'
        mock_load_files.return_value = LoadFiles('IETFYANGRFC', self.test_private_dir, yc_gc.logs_dir)
        xml_path = '{}/test/YangModels/yang/vendor/cisco/xr/701'.format(yc_gc.temp_dir)
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

        desired_module_data = self.load_desired_prepare_json_data('ncs5k_prepare_json')
        dumped_module_data = self.load_dumped_prepare_json_data()

        self.compare_prepare_data(desired_module_data, dumped_module_data)

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

    @mock.patch('parseAndPopulate.groupings.LoadFiles')
    @mock.patch('parseAndPopulate.groupings.repoutil.RepoUtil.get_commit_hash')
    def test_runCapabilities_parse_and_dump_vendor_yang_lib(self, mock_hash: mock.MagicMock, mock_load_files: mock.MagicMock):
        """ Run runCapability script over yang_lib.xml. Compare content of normal.json and prepare.json files.

        Arguments:
        :param mock_hash        (mock.MagicMock) get_commit_hash() method is patched, to always return 'master'
        :param mock_load_files  (mock.MagicMock) LoadFiles is patched to load json files from test directory
        """
        mock_load_files.return_value = LoadFiles('IETFTEST', self.test_private_dir, yc_gc.logs_dir)
        mock_hash.return_value = 'master'
        xml_path = '{}/test/YangModels/yang/vendor/huawei/network-router/8.20.0/ne5000e'.format(yc_gc.temp_dir)
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

        def key(x): return x.get('name')
        dumped_module_data = sorted(self.load_dumped_prepare_json_data(), key=key)
        desired_module_data = sorted(self.load_desired_prepare_json_data('yang_lib_prepare_json'), key=key)

        self.compare_prepare_data(desired_module_data, dumped_module_data)

        # Load desired normal.json data from .json file
        with open(os.path.join(self.resources_path, 'parseAndPopulate_tests_data.json'), 'r') as f:
            file_content = json.load(f)
        desired_vendor_data = file_content['yang_lib_normal_json']['vendors']['vendor']

        # Load vendor module data from normal.json file
        with open(os.path.join(yc_gc.temp_dir, 'normal.json'), 'r') as f:
            file_content = json.load(f)
            self.assertIn('vendors', file_content)
            self.assertIn('vendor', file_content['vendors'])
            self.assertNotEqual(len(file_content['vendors']['vendor']), 0)
            dumped_vendor_data = file_content['vendors']['vendor']

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
        script_conf.args.__setattr__('result_html_dir', yc_gc.result_dir)
        script_conf.args.__setattr__('save_file_dir', yc_gc.save_file_dir)
        script_conf.args.__setattr__('json_dir', yc_gc.temp_dir)

        return script_conf

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

    def compare_prepare_data(self, desired_module_data, dumped_module_data):

        for desired_module in desired_module_data:
            name = desired_module.get('name')
            revision = desired_module.get('revision')
            for dumped_module in dumped_module_data:
                if name == dumped_module.get('name'):
                    fail_message = 'mismatch in {}'.format(name)
                    fail_message = '{} ' + fail_message
                    # Compare properties/keys of desired and dumped module data objects
                    for key in desired_module:
                        if name == 'ietf-yang-library':
                            # We have multiple slightly different versions of ietf-yang-library
                            # marked with the same revision
                            if key in ('description', 'contact'):
                                continue
                        if key == 'yang-tree':
                            # Compare only URL suffix (exclude domain)
                            desired_tree_suffix = '/api{}'.format(desired_module[key].split('/api')[1])
                            dumped_tree_suffix = '/api{}'.format(dumped_module[key].split('/api')[1])
                            self.assertEqual(desired_tree_suffix, dumped_tree_suffix,
                                             fail_message.format('tree suffix'))
                        elif key == 'compilation-result':
                            if dumped_module[key] != '' and desired_module[key] != '':
                                # Compare only URL suffix (exclude domain)
                                desired_compilation_result = '/results{}'.format(desired_module[key].split('/results')[-1])
                                dumped_compilation_result = '/results{}'.format(dumped_module[key].split('/results')[-1])
                                self.assertEqual(desired_compilation_result, dumped_compilation_result,
                                                 fail_message.format('compilation result'))
                        else:
                            if isinstance(desired_module[key], list):
                                # submodules or dependencies
                                for i in desired_module[key]:
                                    for j in dumped_module[key]:
                                        try:
                                            j.pop('schema')
                                        except KeyError:
                                            pass
                                    self.assertIn(i, dumped_module[key], fail_message.format(key))
                            else:
                                self.assertEqual(dumped_module[key], desired_module[key], fail_message.format(key))
                    break
            else:
                self.assertTrue(False, '{}@{} not found in dumped data'.format(name, revision))

if __name__ == '__main__':
    unittest.main()
