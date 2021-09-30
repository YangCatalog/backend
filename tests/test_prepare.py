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
import unittest
from unittest import mock

from api.globalConfig import yc_gc
from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.modules import Modules
from parseAndPopulate.prepare import Prepare
from utility.staticVariables import github_raw


class TestPrepareClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestPrepareClass, self).__init__(*args, **kwargs)

        # Declare variables
        self.schema = '{}/YangModels/yang/master/standard/ietf/RFC/ietf-yang-types@2013-07-15.yang'.format(github_raw)
        self.tmp_dir = '{}/'.format(yc_gc.temp_dir)
        self.yangcatalog_api_prefix = '{}/api/'.format(yc_gc.my_uri)
        self.prepare_output_filename = 'prepare'
        self.sdo_module_filename = 'ietf-yang-types@2013-07-15.yang'
        self.sdo_module_name = 'ietf-yang-types'
        self.hello_message_filename = 'capabilities-ncs5k.xml'
        self.platform_name = 'ncs5k'
        self.resources_path = '{}/resources'.format(os.path.dirname(os.path.abspath(__file__)))
        self.test_private_dir = 'tests/resources/html/private'

    #########################
    ### TESTS DEFINITIONS ###
    #########################

    def test_prepare_add_key_sdo_module(self):
        """
        Prepare object is initialized and key of one Modules object is added to 'yang_modules' dictionary.
        Created key is then retreived from 'yang_modules' dictionary and compared with desired format of key.
        """
        desired_key = 'ietf-yang-types@2013-07-15/ietf'

        yang = self.declare_sdo_module()

        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)
        prepare.add_key_sdo_module(yang)

        created_key = list(prepare.yang_modules.keys())[0]

        self.assertEqual(created_key, desired_key)
        self.assertIn(desired_key, prepare.yang_modules)

    def test_prepare_add_key_sdo_modules_no_compilation_status(self):
        """
        Prepare object is initialized and key of one Modules object is added to 'yang_modules' dictionary.
        Created key is then retreived from 'yang_modules' dictionary and compared with desired format of key.
        Check if 'compilation_status' is  property set, after setting to None (value should be requested).
        """
        desired_key = 'ietf-yang-types@2013-07-15/ietf'

        yang = self.declare_sdo_module()

        # Clear compilation status to test functionality of requesting compilation_status
        yang.compilation_status = None

        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)
        prepare.add_key_sdo_module(yang)

        created_key = list(prepare.yang_modules.keys())[0]

        self.assertEqual(created_key, desired_key)
        self.assertIn(desired_key, prepare.yang_modules)

        yang_module = prepare.yang_modules[desired_key]
        # Check if object contains 'compilation_status' property
        self.assertIn('compilation_status', yang_module.__dict__)

    @mock.patch('parseAndPopulate.prepare.requests.get')
    def test_prepare_add_key_sdo_modules_no_compilation_status_exception(self, mock_requests_get: mock.MagicMock):
        """
        Prepare object is initialized and key of one Modules object is added to 'yang_modules' dictionary.
        Created key is then retreived from 'yang_modules' dictionary and compared with desired format of key.
        Check if 'compilation_status' is  property set, after setting to None (value should be requested).

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return None, so exception is raised.
        """
        mock_requests_get.return_value = None
        desired_key = 'ietf-yang-types@2013-07-15/ietf'

        yang = self.declare_sdo_module()

        # Clear compilation status to test functionality of requesting compilation_status
        yang.compilation_status = None

        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)
        prepare.add_key_sdo_module(yang)

        created_key = list(prepare.yang_modules.keys())[0]

        self.assertEqual(created_key, desired_key)
        self.assertIn(desired_key, prepare.yang_modules)

        yang_module = prepare.yang_modules[desired_key]

        # Check if 'compilation_status' property is set correctly to value 'unknown'
        self.assertIn('compilation_status', yang_module.__dict__)
        self.assertEqual(yang_module.__getattribute__('compilation_status'), 'unknown')

    def test_prepare_dump_modules(self):
        """
        Prepare object is created and one SDO module is added.
        Modules are then dumped into prepare.json file using dump_modules() method.
        Content of prepare.json file is then checked, data from file are compared with Modules object properties.
        """
        yang = self.declare_sdo_module()

        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)
        prepare.add_key_sdo_module(yang)
        prepare.dump_modules(yc_gc.temp_dir)

        # Load desired module data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
        desired_module_data = file_content.get('dumped_module', {}).get('module', [])[0]

        # Load module data from dumped prepare.json file
        with open('{}/{}.json'.format(yc_gc.temp_dir, self.prepare_output_filename), 'r') as f:
            file_content = json.load(f)
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

    def test_prepare_dump_vendors(self):
        """
        Prepare object is initialized and key of one Modules object is added to 'yang_modules' dictionary.
        It is necessary that this module has filled information about the implementation.
        This can be achieved by calling add_vendor_information() method.
        Vendor data are then dumped into normal.json file using dump_vendors() method.
        Content of dumped normal.json file is then compared with desired content loaded from parseAndPopulate_tests_data.json file.
        """
        # Modules object
        xml_path = '{}/tmp/master/vendor/cisco/xr/701/{}'.format(self.resources_path, self.hello_message_filename)
        platform_data, netconf_version, netconf_capabilities = self.get_platform_data(xml_path)
        yang = self.declare_vendor_module()
        yang.add_vendor_information(platform_data,
                                    'implement',
                                    netconf_capabilities,
                                    netconf_version,
                                    None,
                                    xml_path.split('/'))
        # Prepare object
        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)
        prepare.add_key_sdo_module(yang)
        prepare.dump_vendors(yc_gc.temp_dir)

        # Load desired module data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
        desired_vendor_data = file_content.get('dumped_vendor_data', {})

        # Load vendor module data from normal.json file
        with open('{}/normal.json'.format(yc_gc.temp_dir), 'r') as f:
            dumped_vendor_data = json.load(f)

        self.assertEqual(desired_vendor_data, dumped_vendor_data)

    def test_prepare_get_dependencies_none(self):
        """
        Set value of dependencies property to None, to test if __get_dependencies() method
        correctly set value.
        If value is set to None, it should not be dumped into normal.json file.
        """
        yang = self.declare_sdo_module()

        # Clear dependencies property to test functionality of __get_dependencies() method
        yang.dependencies = None

        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)
        prepare.add_key_sdo_module(yang)
        prepare.dump_modules(yc_gc.temp_dir)

        # Load module data from dumped .json file
        with open('{}/{}.json'.format(yc_gc.temp_dir, self.prepare_output_filename), 'r') as f:
            file_content = json.load(f)
        dumped_module_data = file_content['module'][0]

        # Since dependencies property has value None, it should not be present in dumped module
        self.assertNotIn('dependencies', dumped_module_data)

    def test_prepare_get_deviations_none(self):
        """
        Set value of deviations property to None, to test if __get_deviations() method
        correctly set value.
        If value is set to None, it should not be dumped into .json file.
        """
        xml_path = '{}/tmp/master/vendor/cisco/xr/701/{}'.format(self.resources_path, self.hello_message_filename)
        platform_data, netconf_version, netconf_capabilities = self.get_platform_data(xml_path)
        yang = self.declare_vendor_module()
        yang.add_vendor_information(platform_data,
                                    'implement',
                                    netconf_capabilities,
                                    netconf_version,
                                    None,
                                    xml_path.split('/'))

        # Clear deviations property to test functionality of __get_deviations() method
        for implementation in yang.implementation:
            implementation.deviations = None

        # Prepare object
        prepare = Prepare(yc_gc.logs_dir, self.prepare_output_filename, self.yangcatalog_api_prefix)
        prepare.add_key_sdo_module(yang)
        prepare.dump_vendors(yc_gc.temp_dir)

        # Load vendor module data from normal.json file
        with open('{}/normal.json'.format(yc_gc.temp_dir), 'r') as f:
            dumped_vendor_data = json.load(f)

        # Since deviations property has value None, it should not be present in dumped module
        self.assertNotIn('deviations', dumped_vendor_data)

    ##########################
    ### HELPER DEFINITIONS ###
    ##########################

    def declare_sdo_module(self):
        """
        Initialize Modules object for SDO (ietf) module.

        :returns:           Created instance of Modules object of SDO (ietf) module
        :rtype: Modules
        """
        parsed_jsons = LoadFiles(self.test_private_dir, yc_gc.logs_dir)
        path_to_yang = '{}/tmp/temp/standard/ietf/RFC/{}'.format(self.resources_path, self.sdo_module_filename)

        yang = Modules(yc_gc.yang_models, yc_gc.logs_dir, path_to_yang,
                       yc_gc.result_dir, parsed_jsons, self.tmp_dir)
        yang.parse_all('master', self.sdo_module_name, {}, self.schema,
                       None, yc_gc.save_file_dir)

        return yang

    def declare_vendor_module(self):
        """
        Initialize Modules object for vendor (Cisco) module.

        :returns:           Created instance of Modules object of vendor (cisco) module
        :rtype: Modules
        """
        parsed_jsons = LoadFiles(self.test_private_dir, yc_gc.logs_dir)
        xml_path = '{}/{}'.format(self.resources_path, self.hello_message_filename)
        yang_lib_data = 'ietf-netconf-acm&revision=2018-02-14&deviations=cisco-xr-ietf-netconf-acm-deviations'
        module_name = yang_lib_data.split('&revision')[0]

        yang = Modules(yc_gc.yang_models, yc_gc.logs_dir, xml_path, yc_gc.result_dir,
                       parsed_jsons, self.tmp_dir, is_vendor=True, data=yang_lib_data)
        yang.parse_all('master', module_name, {},
                       '', None, yc_gc.save_file_dir)

        return yang

    def get_platform_data(self, xml_path: str):
        """
        Load content of platform-metadata.json file and parse data of selected platform.

        :param xml_path         (str) Absolute path of selected .xml file
        """
        platform_data = []
        netconf_version = netconf_capabilities = set()

        with open('/'.join(xml_path.split('/')[:-1]) + '/platform-metadata.json', 'r', encoding='utf-8') as f:
            file_content = json.load(f)
            platforms = file_content['platforms']['platform']
        for platform in platforms:
            if self.platform_name == platform['name']:
                platform_data.append({'software-flavor': platform['software-flavor'],
                                      'platform': platform['name'],
                                      'os-version': platform['software-version'],
                                      'software-version': platform['software-version'],
                                      'feature-set': "ALL",
                                      'vendor': platform['vendor'],
                                      'os': platform['os-type']})
                if 'netconf-capabilities' in platform:
                    netconf_version = [
                        capability for capability in platform['netconf-capabilities'] if ':netconf:base:' in capability]
                    netconf_capabilities = [
                        capability for capability in platform['netconf-capabilities'] if ':capability:' in capability]

        return platform_data, netconf_version, netconf_capabilities


if __name__ == "__main__":
    unittest.main()
