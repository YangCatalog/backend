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
import typing as t
import unittest

import parseAndPopulate.dumper as du
from api.globalConfig import yc_gc
from parseAndPopulate.models.directory_paths import DirPaths
from parseAndPopulate.models.schema_parts import SchemaParts
from parseAndPopulate.models.vendor_modules import VendorInfo
from parseAndPopulate.modules import SdoModule, VendorModule


class TestDumperClass(unittest.TestCase):
    resources_path: str

    @classmethod
    def setUpClass(cls):
        cls.schema_parts = SchemaParts(repo_owner='YangModels', repo_name='yang', commit_hash='master')
        cls.prepare_output_filename = 'prepare'
        cls.platform_name = 'test-platform'
        cls.resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources/dumper')
        cls.dir_paths: DirPaths = {
            'cache': '',
            'json': '',
            'log': yc_gc.logs_dir,
            'private': '',
            'result': yc_gc.result_dir,
            'save': yc_gc.save_file_dir,
            'yang_models': yc_gc.yang_models,
        }
        with open(cls.resource('test_data.json'), 'r') as f:
            cls.test_data = json.load(f)

    def test_dumper_add_module(self):
        """
        Dumper object is initialized and key of one Modules object is added to 'yang_modules' dictionary.
        Created key is then retreived from 'yang_modules' dictionary and compared with desired format of key.
        """
        key = 'sdo-module@2022-08-05/ietf'

        yang = self.declare_sdo_module()

        dumper = du.Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        dumper.add_module(yang)

        self.assertEqual(list(dumper.yang_modules.keys()), [key])

    def test_dumper_dump_modules(self):
        """
        Dumper object is created and one SDO module is added.
        Modules are then dumped into prepare.json file using dump_modules() method.
        Content of prepare.json file is then checked, data from file are compared with Modules object properties.
        """
        yang = self.declare_sdo_module()

        dumper = du.Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        dumper.add_module(yang)
        dumper.dump_modules(yc_gc.temp_dir)

        # Load desired module data from .json file
        desired_module_data = self.test_data['dumped_module']['module']

        # Load module data from dumped prepare.json file
        with open(os.path.join(yc_gc.temp_dir, f'{self.prepare_output_filename}.json'), 'r') as f:
            file_content = json.load(f)
        dumped_module_data = file_content['module']

        # Compare properties/keys of desired and dumped module data objects
        self.compare_module_data(dumped_module_data, desired_module_data)

    def test_dumper_dump_vendors(self):
        """
        Dumper object is initialized and key of one Modules object is added to 'yang_modules' dictionary.
        It is necessary that this module has filled information about the implementation.
        This can be achieved by calling add_vendor_information() method.
        Vendor data are then dumped into normal.json file using dump_vendors() method.
        Content of dumped normal.json file is then compared with desired content loaded from test_data.json file.
        """
        platform_data = [
            {
                'software-flavor': 'test-flavor',
                'platform': 'test-platform',
                'os-version': 'test-version',
                'software-version': 'test-version',
                'feature-set': 'ALL',
                'vendor': 'cisco',
                'os': 'test-os',
            },
        ]
        netconf_version = ['urn:ietf:params:xml:ns:netconf:base:1.0']
        netconf_capabilities = ['urn:ietf:params:netconf:capability:test-capability:1.0']
        # Modules object
        vendor_info = VendorInfo(
            platform_data=platform_data,
            conformance_type='implement',
            capabilities=netconf_capabilities,
            netconf_versions=netconf_version,
        )
        yang = self.declare_vendor_module(vendor_info=vendor_info)
        # Dumper object
        dumper = du.Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        dumper.add_module(yang)
        dumper.dump_vendors(yc_gc.temp_dir)

        # Load desired module data from .json file
        desired_vendor_data = self.test_data['dumped_vendor_data']['vendors']['vendor']

        # Load vendor module data from normal.json file
        os.path.join(yc_gc.temp_dir, 'normal.json')
        with open(os.path.join(yc_gc.temp_dir, 'normal.json'), 'r') as f:
            dumped_vendor_data = json.load(f).get('vendors', {}).get('vendor', [])

        self.compare_vendor_data(desired_vendor_data, dumped_vendor_data)

    def declare_sdo_module(self):
        """
        Initialize Modules object for SDO (ietf) module.

        Arguments:
            :return     (SdoModule) Created instance of Modules object of SDO (ietf) module
        """
        path_to_yang = self.resource('sdo-module.yang')
        yang = SdoModule('sdo-module', path_to_yang, {}, self.dir_paths, {})
        return yang

    def declare_vendor_module(self, vendor_info: t.Optional[VendorInfo] = None):
        """
        Initialize Modules object for vendor (Cisco) module.

        Arguments:
            :return     (VendorModule) Created instance of Modules object of vendor (cisco) module
        """
        vendor_data = 'sdo-module&revision=2022-08-05&deviations=vendor-sdo-module-deviations'
        module_name = vendor_data.split('&revision')[0]
        path_to_yang = self.resource('sdo-module.yang')
        yang = VendorModule(
            module_name,
            path_to_yang,
            {},
            self.dir_paths,
            {},
            vendor_info=vendor_info,
            data=vendor_data,
        )

        return yang

    def compare_module_data(self, desired_module_data, dumped_module_data):
        for desired_module in desired_module_data:
            name = desired_module.get('name')
            revision = desired_module.get('revision')
            for dumped_module in dumped_module_data:
                if name == dumped_module.get('name'):
                    fail_message = f'mismatch in {name}'
                    # Compare properties/keys of desired and dumped module data objects
                    for key in desired_module:
                        if name == 'ietf-yang-library':
                            # We have multiple slightly different versions of ietf-yang-library
                            # marked with the same revision
                            if key in ('description', 'contact'):
                                continue
                        if key == 'yang-tree':
                            # Compare only URL suffix (exclude domain)
                            desired_tree_suffix = f'/api{desired_module[key].split("/api")[1]}'
                            dumped_tree_suffix = f'/api{dumped_module[key].split("/api")[1]}'
                            self.assertEqual(
                                desired_tree_suffix,
                                dumped_tree_suffix,
                                f'tree suffix {fail_message}',
                            )
                        elif key == 'compilation-result':
                            if dumped_module[key] != '' and desired_module[key] != '':
                                # Compare only URL suffix (exclude domain)
                                desired_compilation_result = f'/results{desired_module[key].split("/results")[-1]}'
                                dumped_compilation_result = f'/results{dumped_module[key].split("/results")[-1]}'
                                self.assertEqual(
                                    desired_compilation_result,
                                    dumped_compilation_result,
                                    f'compilation result {fail_message}',
                                )
                        else:
                            if isinstance(desired_module[key], list):
                                # submodules or dependencies
                                for i in desired_module[key]:
                                    for j in dumped_module[key]:
                                        try:
                                            j.pop('schema')
                                        except KeyError:
                                            pass
                                    self.assertIn(i, dumped_module[key], f'{key} {fail_message}')
                            else:
                                self.assertEqual(dumped_module[key], desired_module[key], f'{key} {fail_message}')
                    break
            else:
                self.assertTrue(False, f'{name}@{revision} not found in dumped data')

    def compare_vendor_data(self, desired, dumped):
        for desired_vendor in desired:
            self.assertTrue(
                any(self.compare_vendor(desired_vendor, dumped_vendor) for dumped_vendor in dumped),
                f'the following vendor (or it\'s "superset"):'
                f'\n{desired_vendor}\nwas not found in the dumped data:\n{dumped}',
            )

    def compare_list(self, f, desired, dumped) -> bool:
        for desired_datum in desired:
            if not any(f(desired_datum, dumped_datum) for dumped_datum in dumped):
                return False
        return True

    def compare_vendor(self, desired, dumped) -> bool:
        try:
            if desired['name'] != dumped['name']:
                return False
            desired_platforms = desired['platforms']['platform']
            dumped_platforms = dumped['platforms']['platform']
        except KeyError:
            return False
        return self.compare_list(self.compare_platforms, desired_platforms, dumped_platforms)

    def compare_platforms(self, desired, dumped) -> bool:
        try:
            if desired['name'] != dumped['name']:
                return False
            desired_software_versions = desired['software-versions']['software-version']
            dumped_software_versions = dumped['software-versions']['software-version']
        except KeyError:
            return False
        return self.compare_list(self.compare_software_versions, desired_software_versions, dumped_software_versions)

    def compare_software_versions(self, desired, dumped) -> bool:
        try:
            if desired['name'] != dumped['name']:
                return False
            desired_software_flavors = desired['software-flavors']['software-flavor']
            dumped_software_flavors = dumped['software-flavors']['software-flavor']
        except KeyError:
            return False
        return self.compare_list(self.compare_software_flavors, desired_software_flavors, dumped_software_flavors)

    def compare_software_flavors(self, desired, dumped) -> bool:
        try:
            if not (
                desired['name'] == dumped['name']
                and self.compare_non_recursive(desired['protocols']['protocol'], dumped['protocols']['protocol'])
                and self.compare_non_recursive(desired['modules']['module'], dumped['modules']['module'])
            ):
                return False
        except KeyError:
            return False
        return True

    # used for comparing "modules" and "protocols"
    def compare_non_recursive(self, desired: t.List[dict], dumped: t.List[dict]) -> bool:
        """Compare a list of dicts."""
        return self.compare_list(self.dict_contains, desired, dumped)

    def dict_contains(self, sub: dict, super: dict) -> bool:
        """Check whether the super dict contains all the keys of the sub dict with idetical values."""
        for key in sub:
            try:
                if sub[key] != super[key]:
                    return False
            except KeyError:
                return False
        return True

    @classmethod
    def resource(cls, path: str) -> str:
        return os.path.join(cls.resources_path, path)


if __name__ == '__main__':
    unittest.main()
