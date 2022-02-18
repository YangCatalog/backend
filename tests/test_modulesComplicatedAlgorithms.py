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
from copy import deepcopy
from unittest import mock

from api.globalConfig import yc_gc
from parseAndPopulate.modulesComplicatedAlgorithms import \
    ModulesComplicatedAlgorithms


class TestModulesComplicatedAlgorithmsClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestModulesComplicatedAlgorithmsClass, self).__init__(*args, **kwargs)
        self.resources_path = '{}/resources'.format(os.path.dirname(os.path.abspath(__file__)))
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            self.payloads = json.load(f)
        self.yangcatalog_api_prefix = 'http://non-existing-site.com/api/'
        self.save_file_dir = '{}/all_modules'.format(self.resources_path)

    #########################
    ### TESTS DEFINITIONS ###
    #########################

    ### parse_semver() - parsing latest revision ###
    ################################################
    """
    TEST CASES:
    I. 1st revision - 1.0.0
    II. 2nd revision - major version update (2.0.0)
    III. 3rd revision - major version update (3.0.0)
    IV. 4th revision - major version update (4.0.0)
    V. 5th revision - minor version update (4.1.0)
    VI. 6th revision - patch version update (4.1.1)
    """
    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_semver_init_revision(self, mock_requests_get: mock.MagicMock):
        """ Check whether the value of the 'derived-semantic-version' property was set correctly.
        Only one - first revision of the module is passed to the modulesComplicatedAlgorithms script.
        Expected 'derived-semantic-version': 1.0.0

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return only the necessary modules
        """
        modules = self.payloads['modulesComplicatedAlgorithms_prepare_json']['module']
        modules = sorted(modules, key=lambda k: k['revision'])
        # List od modules returned from patched /api/search/modules GET request
        modules[0].pop('derived-semantic-version')
        existing_modules = {}
        existing_modules['module'] = deepcopy(modules[:1])
        mock_requests_get.return_value.json.return_value = existing_modules

        module_to_parse = modules[0]
        all_modules = {}
        all_modules['module'] = [module_to_parse]

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)

        complicatedAlgorithms.parse_semver()

        self.assertNotEqual(len(complicatedAlgorithms.new_modules), 0)
        name = module_to_parse['name']
        revision = module_to_parse['revision']
        new_module = complicatedAlgorithms.new_modules.get(name).get(revision, {})
        self.assertEqual(new_module.get('derived-semantic-version'), '1.0.0')

    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_semver_update_major(self, mock_requests_get: mock.MagicMock):
        """ Check whether the value of the 'derived-semantic-version' property was set correctly.
        Module compilation status is 'passed-with-warnings' so a major version update is expected.
        Expected 'derived-semantic-version': 2.0.0

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return only the necessary modules
        """
        modules = self.payloads['modulesComplicatedAlgorithms_prepare_json']['module']
        modules = sorted(modules, key=lambda k: k['revision'])
        # List od modules returned from patched /api/search/modules GET request
        modules[1].pop('derived-semantic-version')
        existing_modules = {}
        existing_modules['module'] = deepcopy(modules[:2])
        mock_requests_get.return_value.json.return_value = existing_modules

        module_to_parse = modules[1]
        all_modules = {}
        all_modules['module'] = [module_to_parse]

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)

        complicatedAlgorithms.parse_semver()

        self.assertNotEqual(len(complicatedAlgorithms.new_modules), 0)
        name = module_to_parse['name']
        revision = module_to_parse['revision']
        new_module = complicatedAlgorithms.new_modules.get(name).get(revision, {})
        self.assertEqual(new_module.get('derived-semantic-version'), '2.0.0')

    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_semver_update_major_2(self, mock_requests_get: mock.MagicMock):
        """ Check whether the value of the 'derived-semantic-version' property was set correctly.
        Module compilation status is 'passed' after previous 'passed-with-warnings' so a major version update is expected.
        Expected 'derived-semantic-version': 3.0.0

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return only the necessary modules
        """
        modules = self.payloads['modulesComplicatedAlgorithms_prepare_json']['module']
        modules = sorted(modules, key=lambda k: k['revision'])
        # List od modules returned from patched /api/search/modules GET request
        modules[2].pop('derived-semantic-version')
        existing_modules = {}
        existing_modules['module'] = deepcopy(modules[:3])
        mock_requests_get.return_value.json.return_value = existing_modules

        module_to_parse = modules[2]
        all_modules = {}
        all_modules['module'] = [module_to_parse]

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)

        complicatedAlgorithms.parse_semver()

        self.assertNotEqual(len(complicatedAlgorithms.new_modules), 0)
        name = module_to_parse['name']
        revision = module_to_parse['revision']
        new_module = complicatedAlgorithms.new_modules.get(name).get(revision, {})
        self.assertEqual(new_module.get('derived-semantic-version'), '3.0.0')

    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_semver_update_major_3(self, mock_requests_get: mock.MagicMock):
        """ Check whether the value of the 'derived-semantic-version' property was set correctly.
        Module compilation status is 'passed', but errors occured while running --check-update-from
        so a major version update is expected.
        Expected 'derived-semantic-version': 4.0.0

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return only the necessary modules
        """
        modules = self.payloads['modulesComplicatedAlgorithms_prepare_json']['module']
        modules = sorted(modules, key=lambda k: k['revision'])
        # List od modules returned from patched /api/search/modules GET request
        modules[3].pop('derived-semantic-version')
        existing_modules = {}
        existing_modules['module'] = deepcopy(modules[:4])
        mock_requests_get.return_value.json.return_value = existing_modules

        module_to_parse = modules[3]
        all_modules = {}
        all_modules['module'] = [module_to_parse]

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)

        complicatedAlgorithms.parse_semver()

        self.assertNotEqual(len(complicatedAlgorithms.new_modules), 0)
        name = module_to_parse['name']
        revision = module_to_parse['revision']
        new_module = complicatedAlgorithms.new_modules.get(name).get(revision, {})
        self.assertEqual(new_module.get('derived-semantic-version'), '4.0.0')

    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_semver_update_minor(self, mock_requests_get: mock.MagicMock):
        """ Check whether the value of the 'derived-semantic-version' property was set correctly.
        Module compilation status is 'passed', no error occured while running --check-update-from,
        but yang-trees are different so a minor version update is expected.
        Expected 'derived-semantic-version': 4.1.0

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return only the necessary modules
        """
        modules = self.payloads['modulesComplicatedAlgorithms_prepare_json']['module']
        modules = sorted(modules, key=lambda k: k['revision'])
        # List od modules returned from patched /api/search/modules GET request
        modules[4].pop('derived-semantic-version')
        existing_modules = {}
        existing_modules['module'] = deepcopy(modules[:5])
        mock_requests_get.return_value.json.return_value = existing_modules

        module_to_parse = modules[4]
        all_modules = {}
        all_modules['module'] = [module_to_parse]

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)

        complicatedAlgorithms.parse_semver()

        self.assertNotEqual(len(complicatedAlgorithms.new_modules), 0)
        name = module_to_parse['name']
        revision = module_to_parse['revision']
        new_module = complicatedAlgorithms.new_modules.get(name).get(revision, {})
        self.assertEqual(new_module.get('derived-semantic-version'), '4.1.0')

    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_semver_update_patch(self, mock_requests_get: mock.MagicMock):
        """ Check whether the value of the 'derived-semantic-version' property was set correctly.
        Module compilation status is 'passed', no error occured while running --check-update-from,
        yang-trees are same so a patch version update is expected.
        Expected 'derived-semantic-version': 4.1.1

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return only the necessary modules
        """
        modules = self.payloads['modulesComplicatedAlgorithms_prepare_json']['module']
        modules = sorted(modules, key=lambda k: k['revision'])
        # List od modules returned from patched /api/search/modules GET request
        modules[5].pop('derived-semantic-version')
        existing_modules = {}
        existing_modules['module'] = deepcopy(modules[:6])
        mock_requests_get.return_value.json.return_value = existing_modules

        module_to_parse = modules[5]
        all_modules = {}
        all_modules['module'] = [module_to_parse]

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)

        complicatedAlgorithms.parse_semver()

        self.assertNotEqual(len(complicatedAlgorithms.new_modules), 0)
        name = module_to_parse['name']
        revision = module_to_parse['revision']
        new_module = complicatedAlgorithms.new_modules.get(name).get(revision, {})
        self.assertEqual(new_module.get('derived-semantic-version'), '4.1.1')

    ### parse_semver() - parsing middle revision ###
    ################################################
    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_semver_update_versions(self, mock_requests_get: mock.MagicMock):
        """ Check whether the value of the 'derived-semantic-version' property was set correctly.
        Module between two other revisions is parsed, which means, it will loop through all the available
        module revisions and assign 'derived-semantic-version' to them.
        Expected 'derived-semantic-version' order: '1.0.0', '2.0.0', '3.0.0', '4.0.0', '4.1.0', '4.1.1'

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return only the necessary modules
        """
        expected_semver_order = ['1.0.0', '2.0.0', '3.0.0', '4.0.0', '4.1.0', '4.1.1']
        modules = self.payloads['modulesComplicatedAlgorithms_prepare_json']['module']
        modules = sorted(modules, key=lambda k: k['revision'])
        # List od modules returned from patched /api/search/modules GET request
        existing_modules = {}
        existing_modules['module'] = deepcopy([{k: v for k, v in mod.items() if k != 'derived-semantic-version'} for mod in modules])

        mock_requests_get.return_value.json.return_value = existing_modules

        module_to_parse = modules[4]
        all_modules = {}
        all_modules['module'] = [module_to_parse]

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)

        complicatedAlgorithms.parse_semver()

        self.assertNotEqual(len(complicatedAlgorithms.new_modules), 0)
        revisions = sorted(complicatedAlgorithms.new_modules['semver-test'])
        for revision, expected_version in zip(revisions, expected_semver_order):
            new_module = complicatedAlgorithms.new_modules['semver-test'].get(revision, {})
            self.assertEqual(new_module.get('derived-semantic-version'), expected_version)

    ### resolve_tree_type() ###
    ###########################
    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_non_requests_openconfig(self, mock_requests_get: mock.MagicMock):
        module = self.payloads['parse_tree_type']['module'][0]
        all_modules = {'module': [module]}
        mock_requests_get.return_value.json.return_value = {'module': []}

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)
        complicatedAlgorithms.parse_non_requests()
        name = module['name']
        revision = module['revision']
        self.assertEqual(complicatedAlgorithms.new_modules[name][revision]['tree-type'], 'openconfig')

    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_non_requests_split(self, mock_requests_get: mock.MagicMock):
        module = self.payloads['parse_tree_type']['module'][1]
        all_modules = {'module': [module]}
        mock_requests_get.return_value.json.return_value = {'module': []}

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)
        complicatedAlgorithms.parse_non_requests()
        name = module['name']
        revision = module['revision']
        self.assertEqual(complicatedAlgorithms.new_modules[name][revision]['tree-type'], 'split')

    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_non_requests_combined(self, mock_requests_get: mock.MagicMock):
        module = self.payloads['parse_tree_type']['module'][2]
        all_modules = {'module': [module]}
        mock_requests_get.return_value.json.return_value = {'module': []}

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)
        complicatedAlgorithms.parse_non_requests()
        name = module['name']
        revision = module['revision']
        self.assertEqual(complicatedAlgorithms.new_modules[name][revision]['tree-type'], 'nmda-compatible')

    ### parse_dependents() ###
    ##########################
    @mock.patch('parseAndPopulate.modulesComplicatedAlgorithms.ModulesComplicatedAlgorithms.parse_semver',
                mock.MagicMock())
    @mock.patch('parseAndPopulate.dumper.requests.get')
    def test_parse_dependents(self, mock_requests_get: mock.MagicMock):
        payload = self.payloads['parse_dependents']
        all_modules = {'module': payload[0]['new']}
        mock_requests_get.return_value.json.return_value = {'module': payload[0]['existing']}

        complicatedAlgorithms = ModulesComplicatedAlgorithms(yc_gc.logs_dir, self.yangcatalog_api_prefix,
                                                             yc_gc.credentials, self.save_file_dir,
                                                             yc_gc.temp_dir, all_modules, yc_gc.yang_models, yc_gc.temp_dir,
                                                             yc_gc.json_ytree)
        complicatedAlgorithms.parse_requests()
        new = complicatedAlgorithms.new_modules
        self.assertIn({'name': 'n1', 'revision': '1'}, new['e1']['1']['dependents'])
        self.assertIn({'name': 'n2', 'revision': '1'}, new['e1']['1']['dependents'])
        self.assertNotIn('1', new['e2'])
        self.assertIn({'name': 'n2', 'revision': '1'}, new['n1']['1']['dependents'])
        self.assertIn({'name': 'e2', 'revision': '1'}, new['n1']['1']['dependents'])
        self.assertNotIn('1', new['n2'])

    ##########################
    ### HELPER DEFINITIONS ###
    ##########################

    def load_from_json(self, key: str):
        with open('{}/parseAndPopulate_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            loaded_result = file_content.get(key, {})
        return loaded_result


if __name__ == "__main__":
    unittest.main()
