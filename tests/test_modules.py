# Copyright The IETF Trust 2020, All Rights Reserved
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
__copyright__ = 'Copyright The IETF Trust 2020, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

import json
import os
import unittest

from api.globalConfig import yc_gc
from parseAndPopulate.models.directory_paths import DirPaths
from parseAndPopulate.models.schema_parts import SchemaParts
from parseAndPopulate.models.vendor_modules import VendorInfo
from parseAndPopulate.modules import SdoModule, VendorModule


class TestModulesClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema_parts = SchemaParts(repo_owner='YangModels', repo_name='yang', commit_hash='master')
        cls.sdo_module_filename = 'sdo-module@2022-08-05.yang'
        cls.sdo_module_name = 'sdo-module'
        cls.hello_message_filename = 'capabilities-ncs5k.xml'
        resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        cls.test_private_dir = os.path.join(resources_path, 'html/private')
        cls.dir_paths: DirPaths = {
            'cache': '',
            'json': '',
            'log': yc_gc.logs_dir,
            'private': '',
            'result': yc_gc.result_dir,
            'save': yc_gc.save_file_dir,
            'yang_models': yc_gc.yang_models,
        }

        cls.test_repo = os.path.join(yc_gc.temp_dir, 'test/YangModels/yang')

    def test_modules_parse_all_sdo_object(self):
        """
        Create modules object from SDO (= ietf) YANG file,
        and compare object property values.
        """
        path_to_yang = os.path.join(yc_gc.save_file_dir, self.sdo_module_filename)

        yang = SdoModule(self.sdo_module_name, path_to_yang, {}, self.dir_paths, {})

        self.assertEqual(yang.generated_from, 'not-applicable')
        self.assertEqual(yang.module_type, 'module')
        self.assertEqual(yang.name, 'sdo-module')
        self.assertEqual(yang.namespace, 'testing')
        self.assertEqual(yang.organization, 'ietf')
        self.assertEqual(yang.prefix, 'yang')
        self.assertEqual(yang.revision, '2022-08-05')
        self.assertEqual(yang.yang_version, '1.0')

    def test_modules_parse_all_sdo_object_already_in_keys(self):
        """
        Create modules object from SDO (= ietf) YANG file,
        and compare object property values.
        Pass keys as an argument so only some properties will be resolved, while other will stay set to None.
        """
        path_to_yang = os.path.join(yc_gc.save_file_dir, self.sdo_module_filename)
        keys = {'sdo-module@2022-08-05/ietf': ''}
        additional_info = {
            'author-email': 'test@test.test',
            'maturity-level': 'ratified',
            'reference': 'https://tools.ietf.org/html/rfc6991',
            'document-name': 'rfc6991',
            'generated-from': 'test',
            'organization': 'ietf',
            'module-classification': 'testing',
        }

        yang = SdoModule(self.sdo_module_name, path_to_yang, {}, self.dir_paths, keys, additional_info)

        self.assertEqual(yang.name, 'sdo-module')
        self.assertEqual(yang.module_type, 'module')
        self.assertEqual(yang.organization, 'ietf')
        self.assertEqual(yang.revision, '2022-08-05')
        self.assertEqual(yang.namespace, 'testing')

    def test_modules_parse_all_vendor_object(self):
        """
        Create modules object from vendor YANG file,
        and compare object property values.
        """
        yang_lib_data = 'sdo-module&revision=2022-08-05&deviations=vendor-sdo-module-deviations'
        module_name = 'sdo-module'
        path_to_yang = os.path.join(yc_gc.save_file_dir, 'sdo-module@2022-08-05.yang')
        deviation = 'vendor-sdo-module-deviations'

        yang = VendorModule(module_name, path_to_yang, {}, self.dir_paths, {}, data=yang_lib_data)

        self.assertEqual(yang.generated_from, 'not-applicable')
        self.assertEqual(yang.module_type, 'module')
        self.assertEqual(yang.name, module_name)
        self.assertEqual(yang.namespace, 'testing')
        self.assertEqual(yang.organization, 'ietf')
        self.assertEqual(yang.prefix, 'yang')
        self.assertEqual(yang.revision, '2022-08-05')
        self.assertIn(deviation, yang.deviations[0]['name'])

    def test_modules_add_vendor_information(self):
        """
        Create modules object from vendor (= cisco) YANG file.
        Vendor information are then added using add_vendor_information() method and object values are compared
        with data from platform-metadata.json.
        """
        xml_path = os.path.join(self.test_repo, 'vendor/cisco/xr/701', self.hello_message_filename)
        vendor_data = 'ietf-netconf-acm&revision=2018-02-14&deviations=cisco-xr-ietf-netconf-acm-deviations'
        module_name = vendor_data.split('&revision')[0]
        path_to_yang = f'{self.test_repo}/vendor/cisco/xr/701/{module_name}.yang'
        platform_name = 'ncs5k'

        platform_data, netconf_versions, netconf_capabilities = self.get_platform_data(xml_path, platform_name)

        vendor_info = VendorInfo(
            platform_data=platform_data,
            conformance_type='implement',
            capabilities=netconf_capabilities,
            netconf_versions=netconf_versions,
        )
        yang = VendorModule(
            module_name,
            path_to_yang,
            {},
            self.dir_paths,
            {},
            vendor_info=vendor_info,
            data=vendor_data,
        )

        self.assertNotEqual(len(yang.implementations), 0)
        self.assertNotEqual(len(platform_data), 0)
        for implementation, platform in zip(yang.implementations, platform_data):
            self.assertEqual(implementation.feature_set, platform['feature-set'])
            self.assertEqual(implementation.netconf_versions, netconf_versions)
            self.assertEqual(implementation.os_type, platform['os'])
            self.assertEqual(implementation.os_version, platform['os-version'])
            self.assertEqual(implementation.platform, platform['platform'])
            self.assertEqual(implementation.software_flavor, platform['software-flavor'])
            self.assertEqual(implementation.software_version, platform['software-version'])
            self.assertEqual(implementation.vendor, platform['vendor'])

    def test_modules_add_vendor_information_is_yang_lib(self):
        """
        Create modules object from yang_lib (= huawei) YANG file.
        Vendor information is then added using the add_vendor_information() method and object values are compared
        with data from platform-metadata.json.
        """
        yang_lib_info = {
            'path': os.path.join(self.test_repo, 'vendor/huawei/network-router/8.20.0/ne5000e'),
            'name': 'huawei-aaa',
            'features': [],
            'deviations': [{'name': 'huawei-aaa-deviations-NE-X1X2', 'revision': '2019-04-23'}],
            'revision': '2020-07-01',
        }
        xml_path = os.path.join(self.test_repo, 'vendor/huawei/network-router/8.20.0/ne5000e/ietf-yang-library.xml')
        module_name = 'huawei-aaa'
        path_to_yang = f'{self.test_repo}/vendor/huawei/network-router/8.20.0/ne5000e/{module_name}.yang'
        platform_name = 'ne5000e'

        platform_data, netconf_versions, netconf_capabilities = self.get_platform_data(xml_path, platform_name)

        vendor_info = VendorInfo(
            platform_data=platform_data,
            conformance_type='implement',
            capabilities=netconf_capabilities,
            netconf_versions=netconf_versions,
        )
        yang = VendorModule(
            module_name,
            path_to_yang,
            {},
            self.dir_paths,
            {},
            vendor_info=vendor_info,
            data=yang_lib_info,
        )

        self.assertNotEqual(len(yang.implementations), 0)
        self.assertNotEqual(len(platform_data), 0)
        for implementation, platform in zip(yang.implementations, platform_data):
            self.assertEqual(implementation.feature_set, platform['feature-set'])
            self.assertEqual(implementation.netconf_versions, netconf_versions)
            self.assertEqual(implementation.os_type, platform['os'])
            self.assertEqual(implementation.os_version, platform['os-version'])
            self.assertEqual(implementation.platform, platform['platform'])
            self.assertEqual(implementation.software_flavor, platform['software-flavor'])
            self.assertEqual(implementation.software_version, platform['software-version'])
            self.assertEqual(implementation.vendor, platform['vendor'])

    def get_platform_data(self, xml_path: str, platform_name: str):
        """
        Load content of platform-metadata.json file and parse data of a selected platform.

        :param xml_path         (str) Absolute path of selected .xml file
        :param platform_name    (str) Name of platform to find
        """
        platform_data = []
        netconf_version = []
        netconf_capabilities = []

        with open('/'.join(xml_path.split('/')[:-1]) + '/platform-metadata.json', 'r', encoding='utf-8') as f:
            file_content = json.load(f)
            platforms = file_content['platforms']['platform']
        for platform in platforms:
            if platform_name == platform['name']:
                platform_data.append(
                    {
                        'software-flavor': platform['software-flavor'],
                        'platform': platform['name'],
                        'os-version': platform['software-version'],
                        'software-version': platform['software-version'],
                        'feature-set': 'ALL',
                        'vendor': platform['vendor'],
                        'os': platform['os-type'],
                    },
                )
                if 'netconf-capabilities' in platform:
                    netconf_version = [
                        capability for capability in platform['netconf-capabilities'] if ':netconf:base:' in capability
                    ]
                    netconf_capabilities = [
                        capability for capability in platform['netconf-capabilities'] if ':capability:' in capability
                    ]

        return platform_data, netconf_version, netconf_capabilities


if __name__ == '__main__':
    unittest.main()
