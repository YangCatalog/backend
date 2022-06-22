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

from api.globalConfig import yc_gc
from parseAndPopulate.dir_paths import DirPaths
from parseAndPopulate.dumper import Dumper
from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.modules import SdoModule, VendorModule
from utility.staticVariables import github_raw


class TestDumperClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestDumperClass, self).__init__(*args, **kwargs)

        # Declare variables
        self.schema_base = '{}/YangModels/yang/'.format(github_raw)
        self.prepare_output_filename = 'prepare'
        self.sdo_module_filename = 'ietf-yang-types@2013-07-15.yang'
        self.sdo_module_name = 'ietf-yang-types'
        self.hello_message_filename = 'capabilities-ncs5k.xml'
        self.platform_name = 'ncs5k'
        self.resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        self.test_private_dir = os.path.join(self.resources_path, 'html/private')
        self.dir_paths: DirPaths = {
            'cache': '',
            'json': '',
            'log': yc_gc.logs_dir,
            'private': self.test_private_dir,
            'result': yc_gc.result_dir,
            'save': yc_gc.save_file_dir,
            'yang_models': yc_gc.yang_models
        }

    #########################
    ### TESTS DEFINITIONS ###
    #########################

    def test_dumper_add_module(self):
        """
        Dumper object is initialized and key of one Modules object is added to 'yang_modules' dictionary.
        Created key is then retreived from 'yang_modules' dictionary and compared with desired format of key.
        """
        desired_key = 'ietf-yang-types@2013-07-15/ietf'

        yang = self.declare_sdo_module()

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        dumper.add_module(yang)

        created_key = list(dumper.yang_modules.keys())[0]

        self.assertEqual(created_key, desired_key)
        self.assertIn(desired_key, dumper.yang_modules)

    def test_dumper_dump_modules(self):
        """
        Dumper object is created and one SDO module is added.
        Modules are then dumped into prepare.json file using dump_modules() method.
        Content of prepare.json file is then checked, data from file are compared with Modules object properties.
        """
        yang = self.declare_sdo_module()

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        dumper.add_module(yang)
        dumper.dump_modules(yc_gc.temp_dir)

        # Load desired module data from .json file
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
        desired_module_data = file_content['dumped_module']['module'][0]

        # Load module data from dumped prepare.json file
        with open('{}/{}.json'.format(yc_gc.temp_dir, self.prepare_output_filename), 'r') as f:
            file_content = json.load(f)
        dumped_module_data = file_content['module'][0]

        # Compare properties/keys of desired and dumped module data objects
        for key in desired_module_data:
            self.assertIn(key, dumped_module_data, desired_module_data[key])
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

    def test_dumper_dump_vendors(self):
        """
        Dumper object is initialized and key of one Modules object is added to 'yang_modules' dictionary.
        It is necessary that this module has filled information about the implementation.
        This can be achieved by calling add_vendor_information() method.
        Vendor data are then dumped into normal.json file using dump_vendors() method.
        Content of dumped normal.json file is then compared with desired content loaded from parseAndPopulate_tests_data.json file.
        """
        # Modules object
        directory = os.path.join(yc_gc.temp_dir, 'test/YangModels/yang/vendor/cisco/xr/701')
        platform_data, netconf_version, netconf_capabilities = self.get_platform_data(directory)
        yang = self.declare_vendor_module()
        yang.add_vendor_information(platform_data, 'implement', netconf_capabilities, netconf_version)
        # Dumper object
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        dumper.add_module(yang)
        dumper.dump_vendors(yc_gc.temp_dir)

        # Load desired module data from .json file
        with open(os.path.join(self.resources_path, 'parseAndPopulate_tests_data.json'), 'r') as f:
            file_content = json.load(f)
        desired_vendor_data = file_content.get('dumped_vendor_data', {})

        # Load vendor module data from normal.json file
        os.path.join(yc_gc.temp_dir, 'normal.json')
        with open(os.path.join(yc_gc.temp_dir, 'normal.json'), 'r') as f:
            dumped_vendor_data = json.load(f)

        self.assertEqual(desired_vendor_data, dumped_vendor_data)

    def test_dumper_get_dependencies_none(self):
        """
        Set value of dependencies property to None, to test if __get_dependencies() method
        correctly set value.
        If value is set to None, it should not be dumped into normal.json file.
        """
        yang = self.declare_sdo_module()

        # Clear dependencies property to test functionality of __get_dependencies() method
        yang.dependencies = []

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        dumper.add_module(yang)
        dumper.dump_modules(yc_gc.temp_dir)

        # Load module data from dumped .json file
        with open('{}/{}.json'.format(yc_gc.temp_dir, self.prepare_output_filename), 'r') as f:
            file_content = json.load(f)
        dumped_module_data = file_content['module'][0]

        # Since dependencies property has value None, it should not be present in dumped module
        self.assertNotIn('dependencies', dumped_module_data)

    def test_dumper_get_deviations_none(self):
        """
        Set value of deviations property to None, to test if __get_deviations() method
        correctly set value.
        If value is set to None, it should not be dumped into .json file.
        """
        directory = os.path.join(yc_gc.temp_dir, 'test/YangModels/yang/vendor/cisco/xr/701')
        platform_data, netconf_version, netconf_capabilities = self.get_platform_data(directory)
        yang = self.declare_vendor_module()
        yang.add_vendor_information(platform_data, 'implement', netconf_capabilities, netconf_version)

        # Clear deviations property to test functionality of __get_deviations() method
        for implementation in yang.implementations:
            implementation.deviations = []

        # Dumper object
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        dumper.add_module(yang)
        dumper.dump_vendors(yc_gc.temp_dir)

        # Load vendor module data from normal.json file
        with open(os.path.join(yc_gc.temp_dir, 'normal.json'), 'r') as f:
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
        parsed_jsons = LoadFiles('IETFTEST', self.test_private_dir, yc_gc.logs_dir)
        path_to_yang = os.path.join(yc_gc.temp_dir, 'test/YangModels/yang/standard/ietf/RFC', self.sdo_module_filename)

        yang = SdoModule(self.sdo_module_name, path_to_yang, parsed_jsons, self.dir_paths, 'master', {},
                         self.schema_base)

        return yang

    def declare_vendor_module(self):
        """
        Initialize Modules object for vendor (Cisco) module.

        :returns:           Created instance of Modules object of vendor (cisco) module
        :rtype: Modules
        """
        parsed_jsons = LoadFiles('IETFTEST', self.test_private_dir, yc_gc.logs_dir)
        vendor_data = 'ietf-netconf-acm&revision=2018-02-14&deviations=cisco-xr-ietf-netconf-acm-deviations'
        module_name = vendor_data.split('&revision')[0]
        module_path = '{}/{}.yang'.format(self.resources_path, module_name)

        yang = VendorModule(module_name, module_path, parsed_jsons, self.dir_paths, 'master', {}, self.schema_base,
                            data=vendor_data)

        return yang

    def get_platform_data(self, directory: str):
        """
        Load content of platform-metadata.json file and parse data of selected platform.

        :param xml_path         (str) Absolute path of selected .xml file
        """
        platform_data = []
        netconf_version = []
        netconf_capabilities = []

        with open(os.path.join(directory, 'platform-metadata.json'), 'r') as f:
            file_content = json.load(f)
            platforms = file_content['platforms']['platform']
        for platform in platforms:
            if self.platform_name == platform['name']:
                platform_data.append({'software-flavor': platform['software-flavor'],
                                      'platform': platform['name'],
                                      'os-version': platform['software-version'],
                                      'software-version': platform['software-version'],
                                      'feature-set': 'ALL',
                                      'vendor': platform['vendor'],
                                      'os': platform['os-type']})
                if 'netconf-capabilities' in platform:
                    netconf_version = [
                        capability for capability in platform['netconf-capabilities'] if ':netconf:base:' in capability]
                    netconf_capabilities = [
                        capability for capability in platform['netconf-capabilities'] if ':capability:' in capability]

        return platform_data, netconf_version, netconf_capabilities


if __name__ == '__main__':
    unittest.main()
