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
from ast import literal_eval
from unittest import mock

from api.globalConfig import yc_gc
from parseAndPopulate.dumper import Dumper
from parseAndPopulate.file_hasher import FileHasher, VendorModuleHashCheckForParsing
from parseAndPopulate.groupings import SdoDirectory, VendorCapabilities, VendorGrouping, VendorYangLibrary
from parseAndPopulate.models.directory_paths import DirPaths
from redisConnections.redisConnection import RedisConnection
from sandbox import constants as sandbox_constants
from sandbox import save_yang_files
from utility.create_config import create_config


class TestGroupingsClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        save_yang_files.main(os.path.join(os.environ['BACKEND'], 'tests/resources/groupings'))
        cls.prepare_output_filename = 'prepare'
        cls.resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources/groupings')
        cls.test_private_dir = os.path.join(cls.resources_path, 'html/private')
        cls.file_hasher = FileHasher('test_modules_hashes', yc_gc.cache_dir, False, yc_gc.logs_dir)
        cls.dir_paths: DirPaths = {
            'cache': '',
            'json': cls.resources_path,
            'log': yc_gc.logs_dir,
            'private': cls.test_private_dir,
            'result': yc_gc.result_dir,
            'save': yc_gc.save_file_dir,
            'yang_models': yc_gc.yang_models,
        }
        cls.test_repo = os.path.join(yc_gc.temp_dir, 'test/YangModels/yang')
        cls.config = create_config()
        cls.redis_connection = RedisConnection(config=cls.config)
        cls.save_file_dir = cls.config.get('Directory-Section', 'save-file-dir')

    @classmethod
    def tearDownClass(cls):
        modules_paths_to_remove_file_path = os.path.join(
            cls.config.get('Directory-Section', 'cache'),
            sandbox_constants.NEW_COPIED_MODULES_PATHS_FILENAME,
        )
        with open(modules_paths_to_remove_file_path, 'r') as f:
            modules_paths_to_remove = json.load(f)
        for module_path in modules_paths_to_remove:
            if not os.path.exists(module_path):
                continue
            os.remove(module_path)

    def test_sdo_directory_parse_and_load(self):
        """
        Test whether keys were created and prepare object values were set correctly
        from all the .yang files which are located in 'path' directory.
        """
        path = self.resource('owner/repo/sdo')
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        file_mapping = {
            self.resource('owner/repo/sdo/sdo-first.yang'): os.path.join(
                self.save_file_dir,
                'sdo-first@2022-08-05.yang',
            ),
            self.resource('owner/repo/sdo/sdo-second.yang'): os.path.join(
                self.save_file_dir,
                'sdo-second@2022-08-05.yang',
            ),
            self.resource('owner/repo/sdo/subdir/sdo-third.yang'): os.path.join(
                self.save_file_dir,
                'sdo-third@2022-08-05.yang',
            ),
        }

        sdo_directory = SdoDirectory(path, dumper, self.file_hasher, api, self.dir_paths, file_mapping)
        sdo_directory.parse_and_load()

        self.assertListEqual(
            sorted(sdo_directory.dumper.yang_modules),
            ['sdo-first@2022-08-05/ietf', 'sdo-second@2022-08-05/ietf', 'sdo-third@2022-08-05/ietf'],
        )

    def test_sdo_directory_parse_and_load_api(self):
        """
        Test whether key was created and prepare object value was set correctly
        from all modules loaded from request-data.json file.
        """
        api = True
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        file_mapping = {
            self.resource('owner/repo/sdo/sdo-first.yang'): os.path.join(
                self.save_file_dir,
                'sdo-first@2022-08-05.yang',
            ),
            self.resource('owner/repo/sdo/sdo-second.yang'): os.path.join(
                self.save_file_dir,
                'sdo-second@2022-08-05.yang',
            ),
            self.resource('owner/repo/sdo/subdir/sdo-third.yang'): os.path.join(
                self.save_file_dir,
                'sdo-third@2022-08-05.yang',
            ),
        }

        sdo_directory = SdoDirectory(
            self.resources_path,
            dumper,
            self.file_hasher,
            api,
            self.dir_paths,
            file_mapping,
        )
        sdo_directory.parse_and_load()

        self.assertListEqual(
            sorted(sdo_directory.dumper.yang_modules),
            ['sdo-first@2022-08-05/ietf', 'sdo-second@2022-08-05/ietf', 'sdo-third@2022-08-05/ietf'],
        )

    def test_vendor_parse_raw_capability(self):
        path = self.resource('owner/repo/vendor')
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        xml_file = os.path.join(path, 'ietf-yang-library.xml')
        api = False

        vendor_grouping = VendorGrouping(path, xml_file, dumper, self.file_hasher, api, self.dir_paths)
        vendor_grouping._parse_raw_capability('urn:ietf:params:xml:ns:netconf:base:1.0')

        self.assertEqual(vendor_grouping.netconf_versions, ['urn:ietf:params:xml:ns:netconf:base:1.0'])

        vendor_grouping._parse_raw_capability('urn:ietf:params:netconf:capability:test-capability:1.0')

        self.assertEqual(vendor_grouping.capabilities, ['urn:ietf:params:netconf:capability:test-capability:1.0'])

    def test_vendor_parse_implementation(self):
        path = self.resource('owner/repo/vendor')
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        xml_file = os.path.join(path, 'ietf-yang-library.xml')
        api = False
        implementation = {
            'module-list-file': {
                'path': 'ietf-yang-library.xml',
                'owner': 'owner',
                'repository': 'repo',
            },
            'software-flavor': 'test-flavor',
            'name': 'test-platform',
            'software-version': 'test-version',
            'vendor': 'cisco',
            'os-type': 'test-os',
            'netconf-capabilities': ['"urn:ietf:params:netconf:capability:test-capability:1.0'],
        }

        vendor_grouping = VendorGrouping(path, xml_file, dumper, self.file_hasher, api, self.dir_paths)
        vendor_grouping._parse_implementation(implementation)

        self.assertEqual(
            vendor_grouping.platform_data,
            [
                {
                    'software-flavor': 'test-flavor',
                    'platform': 'test-platform',
                    'os-version': 'test-version',
                    'software-version': 'test-version',
                    'feature-set': 'ALL',
                    'vendor': 'cisco',
                    'os': 'test-os',
                },
            ],
        )

    def test_vendor_parse_platform_metadata(self):
        path = self.resource('owner/repo/vendor')
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        xml_file = os.path.join(path, 'ietf-yang-library.xml')
        api = False

        vendor_grouping = VendorGrouping(path, xml_file, dumper, self.file_hasher, api, self.dir_paths)
        with mock.patch.object(vendor_grouping, '_parse_implementation') as mock_parse_implementation:
            vendor_grouping._parse_platform_metadata()

        with open(self.resource('owner/repo/vendor/platform-metadata.json')) as f:
            platform_metadata = json.load(f)
        implementation = platform_metadata['platforms']['platform'][1]
        mock_parse_implementation.assert_called_with(implementation)

    def test_vendor_parse_platform_metadata_api(self):
        path = self.resource('owner/repo/vendor')
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)
        xml_file = os.path.join(path, 'ietf-yang-library.xml')
        api = True
        implementation = {
            'module-list-file': {'path': 'vendor/ietf-yang-library.xml'},
            'software-flavor': 'test-flavor',
            'name': 'test-platform',
            'software-version': 'test-version',
            'vendor': 'cisco',
            'os-type': 'test-os',
            'netconf-capabilities': ['"urn:ietf:params:netconf:capability:test-capability:1.0'],
        }

        vendor_grouping = VendorGrouping(path, xml_file, dumper, self.file_hasher, api, self.dir_paths)
        with mock.patch.object(vendor_grouping, '_parse_implementation') as mock_parse_implementation:
            with mock.patch('parseAndPopulate.groupings.open', mock.mock_open(read_data=json.dumps(implementation))):
                vendor_grouping._parse_platform_metadata()

        mock_parse_implementation.assert_called_with(implementation)

    def test_vendor_yang_lib_parse_and_load(self):
        """
        Test whether keys were created and dumper object values were set correctly
        from all the .yang files specified in the ietf-yang-library.xml file.
        """
        directory = self.resource('owner/repo/vendor')
        xml_file = os.path.join(directory, 'ietf-yang-library.xml')
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_yang_lib = VendorYangLibrary(
            directory,
            xml_file,
            dumper,
            self.file_hasher,
            api,
            self.dir_paths,
            config=self.config,
            redis_connection=self.redis_connection,
        )
        vendor_yang_lib.parse_and_load()

        self.assertEqual(
            sorted(vendor_yang_lib.dumper.yang_modules),
            ['sdo-first@2022-08-05/ietf', 'vendor-first@2022-08-05/cisco', 'vendor-second@2022-08-05/cisco'],
        )
        self.assertEqual(
            vendor_yang_lib.dumper.yang_modules['sdo-first@2022-08-05/ietf'].implementations[0].deviations[0].name,
            'vendor-sdo-first-deviations',
        )
        self.assertEqual(
            vendor_yang_lib.dumper.yang_modules['sdo-first@2022-08-05/ietf'].implementations[0].deviations[0].revision,
            '2022-08-05',
        )
        self.assertEqual(
            vendor_yang_lib.dumper.yang_modules['vendor-first@2022-08-05/cisco'].implementations[0].conformance_type,
            'implement',
        )
        self.assertEqual(
            vendor_yang_lib.dumper.yang_modules['vendor-first@2022-08-05/cisco'].implementations[0].feature,
            ['test-feature'],
        )

    def test_vendor_yang_lib_parse_and_load_from_db(self):
        """
        Test whether keys were created and dumper object values were set correctly
        from all the .yang files specified in the ietf-yang-library.xml file.
        """
        directory = self.resource('owner/repo/vendor')
        xml_file = os.path.join(directory, 'ietf-yang-library.xml')
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        def check_vendor_module_hash_for_parsing_mock(path: str, new_implementations: t.Optional[list[str]] = None):
            return VendorModuleHashCheckForParsing(file_hash_exists=True, new_implementations_detected=True)

        self.file_hasher.check_vendor_module_hash_for_parsing = check_vendor_module_hash_for_parsing_mock

        self.populate_test_modules_basic_info_to_db()

        vendor_yang_lib = VendorYangLibrary(
            directory,
            xml_file,
            dumper,
            self.file_hasher,
            api,
            self.dir_paths,
            config=self.config,
            redis_connection=self.redis_connection,
        )
        vendor_yang_lib.parse_and_load()

        self.assertEqual(
            sorted(vendor_yang_lib.dumper.yang_modules),
            ['sdo-first@2022-08-05/ietf', 'vendor-first@2022-08-05/cisco', 'vendor-second@2022-08-05/cisco'],
        )
        self.assertEqual(
            vendor_yang_lib.dumper.yang_modules['sdo-first@2022-08-05/ietf'].implementations[0].deviations[0].name,
            'vendor-sdo-first-deviations',
        )
        self.assertEqual(
            vendor_yang_lib.dumper.yang_modules['sdo-first@2022-08-05/ietf'].implementations[0].deviations[0].revision,
            '2022-08-05',
        )
        self.assertEqual(
            vendor_yang_lib.dumper.yang_modules['vendor-first@2022-08-05/cisco'].implementations[0].conformance_type,
            'implement',
        )
        self.assertEqual(
            vendor_yang_lib.dumper.yang_modules['vendor-first@2022-08-05/cisco'].implementations[0].feature,
            ['test-feature'],
        )

    def test_vendor_capabilities_parse_and_load(self):
        """
        Test whether keys were created and dumper object values were set correctly
        from all the .yang files specified in the capabilities.xml file.
        """
        directory = self.resource('owner/repo/vendor')
        xml_file = os.path.join(directory, 'capabilities.xml')
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_capabilities = VendorCapabilities(
            directory,
            xml_file,
            dumper,
            self.file_hasher,
            api,
            self.dir_paths,
            config=self.config,
        )
        vendor_capabilities.parse_and_load()

        self.assertEqual(
            sorted(vendor_capabilities.dumper.yang_modules),
            ['sdo-first@2022-08-05/ietf', 'vendor-first@2022-08-05/cisco', 'vendor-second@2022-08-05/cisco'],
        )
        self.assertEqual(
            vendor_capabilities.dumper.yang_modules['sdo-first@2022-08-05/ietf'].implementations[0].deviations[0].name,
            'vendor-sdo-first-deviations',
        )
        self.assertEqual(
            vendor_capabilities.dumper.yang_modules['sdo-first@2022-08-05/ietf']
            .implementations[0]
            .deviations[0]
            .revision,
            '2022-08-05',
        )
        self.assertEqual(
            vendor_capabilities.dumper.yang_modules['vendor-first@2022-08-05/cisco']
            .implementations[0]
            .conformance_type,
            'implement',
        )
        self.assertEqual(
            vendor_capabilities.dumper.yang_modules['vendor-first@2022-08-05/cisco'].implementations[0].feature,
            ['test-feature'],
        )

    def test_vendor_capabilities_parse_and_load_from_db(self):
        """
        Test whether keys were created and dumper object values were set correctly
        from all the .yang files specified in the ietf-yang-library.xml file.
        """
        directory = self.resource('owner/repo/vendor')
        xml_file = os.path.join(directory, 'capabilities.xml')
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        def check_vendor_module_hash_for_parsing_mock(path: str, new_implementations: t.Optional[list[str]] = None):
            return VendorModuleHashCheckForParsing(file_hash_exists=True, new_implementations_detected=True)

        self.file_hasher.check_vendor_module_hash_for_parsing = check_vendor_module_hash_for_parsing_mock

        self.populate_test_modules_basic_info_to_db()

        vendor_capabilities = VendorCapabilities(
            directory,
            xml_file,
            dumper,
            self.file_hasher,
            api,
            self.dir_paths,
            config=self.config,
            redis_connection=self.redis_connection,
        )
        vendor_capabilities.parse_and_load()

        self.assertEqual(
            sorted(vendor_capabilities.dumper.yang_modules),
            ['sdo-first@2022-08-05/ietf', 'vendor-first@2022-08-05/cisco', 'vendor-second@2022-08-05/cisco'],
        )
        self.assertEqual(
            vendor_capabilities.dumper.yang_modules['sdo-first@2022-08-05/ietf'].implementations[0].deviations[0].name,
            'vendor-sdo-first-deviations',
        )
        self.assertEqual(
            vendor_capabilities.dumper.yang_modules['sdo-first@2022-08-05/ietf']
            .implementations[0]
            .deviations[0]
            .revision,
            '2022-08-05',
        )
        self.assertEqual(
            vendor_capabilities.dumper.yang_modules['vendor-first@2022-08-05/cisco']
            .implementations[0]
            .conformance_type,
            'implement',
        )
        self.assertEqual(
            vendor_capabilities.dumper.yang_modules['vendor-first@2022-08-05/cisco'].implementations[0].feature,
            ['test-feature'],
        )

    def test_vendor_capabilities_ampersand_exception(self):
        """Test if ampersand character will be replaced in .xml file if occurs.
        If ampersand character occurs, exception is raised, and character is replaced.
        """
        directory = self.resource('owner/repo/vendor')
        xml_file = os.path.join(directory, 'capabilities-amp.xml')
        api = False
        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_capabilities = VendorGrouping(directory, xml_file, dumper, self.file_hasher, api, self.dir_paths)

        self.assertEqual(vendor_capabilities.root.tag, '{urn:ietf:params:xml:ns:netconf:base:1.0}hello')

    def test_vendor__path_to_platform_data_xr(self):
        """Test if platform_data are set correctly when platform_metadata.json file is not present in the folder."""
        directory = os.path.join(self.test_repo, 'vendor/cisco/xr/702')
        xml_file = os.path.join(directory, 'capabilities-ncs5k.xml')
        api = False

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_capabilities = VendorCapabilities(directory, xml_file, dumper, self.file_hasher, api, self.dir_paths)
        platform_data = vendor_capabilities._path_to_platform_data()

        self.assertDictEqual(
            platform_data,
            {
                'software-flavor': 'ALL',
                'platform': 'ncs5k',
                'software-version': '702',
                'os-version': '702',
                'feature-set': 'ALL',
                'os': 'IOS-XR',
                'vendor': 'cisco',
            },
        )

    def test_vendor__path_to_platform_data_nx(self):
        """Test if platform_data are set correctly when platform_metadata.json file is not present in the folder."""
        directory = os.path.join(self.test_repo, 'vendor/cisco/nx/9.2-1')
        xml_file = os.path.join(directory, 'netconf-capabilities.xml')
        api = False

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_capabilities = VendorCapabilities(directory, xml_file, dumper, self.file_hasher, api, self.dir_paths)
        platform_data = vendor_capabilities._path_to_platform_data()

        self.assertEqual(
            platform_data,
            {
                'software-flavor': 'ALL',
                'platform': 'Unknown',
                'software-version': '9.2-1',
                'os-version': '9.2-1',
                'feature-set': 'ALL',
                'os': 'NX-OS',
                'vendor': 'cisco',
            },
        )

    def test_vendor__path_to_platform_data_xe(self):
        """Test if platform_data are set correctly when platform_metadata.json file is not present in the folder."""
        directory = os.path.join(self.test_repo, 'vendor/cisco/xe/16101')
        xml_file = os.path.join(directory, 'capability-asr1k.xml')
        api = False

        dumper = Dumper(yc_gc.logs_dir, self.prepare_output_filename)

        vendor_capabilities = VendorCapabilities(directory, xml_file, dumper, self.file_hasher, api, self.dir_paths)
        platform_data = vendor_capabilities._path_to_platform_data()

        self.assertEqual(
            platform_data,
            {
                'software-flavor': 'ALL',
                'platform': 'asr1k',
                'software-version': '16101',
                'os-version': '16101',
                'feature-set': 'ALL',
                'os': 'IOS-XE',
                'vendor': 'cisco',
            },
        )

    def load_path_to_name_rev(self, key: str):
        """Load a path to (name, revision) dictionary needed by SdoDirectory from parseAndPopulate_tests_data.json."""
        with open(self.resource('parseAndPopulate_tests_data.json'), 'r') as f:
            file_content = json.load(f)
            return literal_eval(file_content.get(key, ''))

    def resource(self, path: str) -> str:
        return os.path.join(self.resources_path, path)

    def populate_test_modules_basic_info_to_db(self):
        data_to_populate = [
            {
                'name': 'sdo-first',
                'revision': '2022-08-05',
                'organization': 'ietf',
            },
            {
                'name': 'vendor-first',
                'revision': '2022-08-05',
                'organization': 'cisco',
            },
            {
                'name': 'vendor-second',
                'revision': '2022-08-05',
                'organization': 'cisco',
            },
        ]
        self.redis_connection.populate_modules(data_to_populate)


if __name__ == '__main__':
    unittest.main()
