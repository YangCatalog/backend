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

import os
import shutil
import unittest
from unittest import mock

import parseAndPopulate.parse_directory as pd
from api.globalConfig import yc_gc
from parseAndPopulate.models.directory_paths import DirPaths


class TestParseDirectoryClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module_name = 'parseAndPopulate'
        cls.script_name = 'parse_directory'
        cls.resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources/parse_directory')
        cls.dir_paths = DirPaths(cache='', json='', log='', private='', result='', save='', yang_models='')

    def test_save_files(self):
        save_file_dir = self.resource('all_modules')
        shutil.rmtree(save_file_dir, ignore_errors=True)
        os.mkdir(save_file_dir)

        file_mapping = pd.save_files(self.resource('sdo'), save_file_dir)

        self.assertListEqual(
            sorted(os.listdir(save_file_dir)),
            ['sdo-first@2022-08-05.yang', 'sdo-second@2022-08-05.yang', 'sdo-third@2022-08-05.yang'],
        )
        self.assertDictEqual(
            file_mapping,
            {
                self.resource('sdo/sdo-first.yang'): self.resource('all_modules/sdo-first@2022-08-05.yang'),
                self.resource('sdo/sdo-second.yang'): self.resource('all_modules/sdo-second@2022-08-05.yang'),
                self.resource('sdo/subdir/sdo-third.yang'): self.resource('all_modules/sdo-third@2022-08-05.yang'),
            },
        )

    @mock.patch('parseAndPopulate.parse_directory.SdoDirectory')
    def test_parse_sdo_generic(self, mock_sdo_directory_cls: mock.MagicMock):
        dumper = mock.MagicMock()
        file_hasher = mock.MagicMock()
        logger = mock.MagicMock()
        config = mock.MagicMock()

        try:
            pd.parse_sdo(self.resource('sdo'), dumper, file_hasher, False, self.dir_paths, {}, logger, config=config)
        except Exception as e:
            e.args = (*e.args, 'This probably means the constructor of IanaDirectory was called.')
            raise e

        mock_sdo_directory_cls.assert_called_with(
            self.resource('sdo'),
            dumper,
            file_hasher,
            False,
            self.dir_paths,
            {},
            config=config,
        )
        mock_sdo_directory = mock_sdo_directory_cls.return_value
        mock_sdo_directory.parse_and_load.assert_called()

    @mock.patch('parseAndPopulate.parse_directory.IanaDirectory')
    def test_parse_sdo_iana(self, mock_iana_directory_cls: mock.MagicMock):
        dumper = mock.MagicMock()
        file_hasher = mock.MagicMock()
        logger = mock.MagicMock()
        config = mock.MagicMock()

        try:
            pd.parse_sdo(self.resource('iana'), dumper, file_hasher, False, self.dir_paths, {}, logger, config=config)
        except Exception as e:
            e.args = (*e.args, 'This probably means the constructor of SdoDirectory was called.')
            raise e

        mock_iana_directory_cls.assert_called_with(
            self.resource('iana'),
            dumper,
            file_hasher,
            False,
            self.dir_paths,
            {},
            config=config,
        )
        mock_iana_directory = mock_iana_directory_cls.return_value
        mock_iana_directory.parse_and_load.assert_called()

    @mock.patch('parseAndPopulate.parse_directory.VendorCapabilities')
    @mock.patch('parseAndPopulate.parse_directory.VendorYangLibrary')
    def test_parse_vendor(self, mock_yang_lib_cls: mock.MagicMock, mock_capabilities_cls: mock.MagicMock):
        dumper = mock.MagicMock()
        file_hasher = mock.MagicMock()
        logger = mock.MagicMock()
        config = mock.MagicMock()
        redis_connection = mock.MagicMock()

        pd.parse_vendor(
            self.resource('vendor'),
            dumper,
            file_hasher,
            False,
            self.dir_paths,
            logger,
            config=config,
            redis_connection=redis_connection,
        )

        root = self.resource('vendor/yang_lib')
        filename = os.path.join(root, 'ietf-yang-library.xml')
        mock_yang_lib_cls.assert_called_with(
            root,
            filename,
            dumper,
            file_hasher,
            False,
            self.dir_paths,
            config=config,
            redis_connection=redis_connection,
        )
        mock_yang_lib = mock_yang_lib_cls.return_value
        mock_yang_lib.parse_and_load.assert_called()

        root = self.resource('vendor/capabilities')
        filename = os.path.join(root, 'capabilities.xml')
        mock_capabilities_cls.assert_called_with(
            root,
            filename,
            dumper,
            file_hasher,
            False,
            self.dir_paths,
            config=config,
            redis_connection=redis_connection,
        )
        mock_capabilities = mock_capabilities_cls.return_value
        mock_capabilities.parse_and_load.assert_called()

    @mock.patch('parseAndPopulate.parse_directory.save_files')
    @mock.patch('parseAndPopulate.parse_directory.parse_sdo')
    @mock.patch('parseAndPopulate.parse_directory.Dumper')
    def test_main_sdo(
        self,
        mock_dumper_cls: mock.MagicMock,
        mock_parse_sdo: mock.MagicMock,
        mock_save_files: mock.MagicMock,
    ):
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()
        self.set_script_conf_arguments(script_conf)
        script_conf.args.sdo = True
        script_conf.args.dir = self.resource('sdo')
        mock_save_files.return_value = ({}, {})

        pd.main(script_conf)

        mock_dumper_cls.assert_called()
        mock_dumper = mock_dumper_cls.return_value
        mock_dumper.dump_modules.assert_called()

        self.assertIn(mock_dumper, mock_parse_sdo.call_args.args)
        self.assertIn(self.resource('sdo'), mock_parse_sdo.call_args.args)

    @mock.patch('parseAndPopulate.parse_directory.save_files')
    @mock.patch('parseAndPopulate.parse_directory.parse_vendor')
    @mock.patch('parseAndPopulate.parse_directory.Dumper')
    def test_main_vendor(
        self,
        mock_dumper_cls: mock.MagicMock,
        mock_parse_vendor: mock.MagicMock,
        mock_save_files: mock.MagicMock,
    ):
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()
        self.set_script_conf_arguments(script_conf)
        script_conf.args.sdo = False
        script_conf.args.dir = self.resource('vendor')
        mock_save_files.return_value = ({}, {})

        pd.main(script_conf)

        mock_dumper_cls.assert_called()
        mock_dumper = mock_dumper_cls.return_value
        mock_dumper.dump_modules.assert_called()
        mock_dumper.dump_vendors.assert_called()

        self.assertIn(mock_dumper, mock_parse_vendor.call_args.args)
        self.assertIn(self.resource('vendor'), mock_parse_vendor.call_args.args)

    def test_get_help(self):
        """Test whether script help has the correct structure (check only structure not content)."""
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()

        script_help = script_conf.get_help()

        self.assertIn('help', script_help)
        self.assertIn('options', script_help)
        self.assertNotEqual(script_help.get('options'), {})

    def test_get_args_list(self):
        """Test whether script default arguments has the correct structure (check only structure not content)."""
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()

        script_args_list = script_conf.get_args_list()

        self.assertNotEqual(script_args_list, {})
        for key in script_args_list:
            self.assertIn('type', script_args_list.get(key))
            self.assertIn('default', script_args_list.get(key))

    def set_script_conf_arguments(self, script_conf):
        """Set values to ScriptConfig arguments to be able to run in test environment.

        :returns        ScriptConfig with arguments set.
        """
        script_conf.args.__setattr__('result_html_dir', yc_gc.result_dir)
        script_conf.args.__setattr__('save_file_dir', yc_gc.save_file_dir)
        script_conf.args.__setattr__('json_dir', yc_gc.temp_dir)

        return script_conf

    def resource(self, path: str):
        return os.path.join(self.resources_path, path)


if __name__ == '__main__':
    unittest.main()
