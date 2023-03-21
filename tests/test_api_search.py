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

import collections
import json
import os
import unittest
from unittest import mock

from lxml import html as HT
from markupsafe import escape
from werkzeug.exceptions import BadRequest, NotFound

import api.views.redisSearch.redisSearch as search_bp
from api.yangCatalogApi import app

app_config = app.config


class TestApiSearchClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        cls.client = app.test_client()
        with open(os.path.join(cls.resources_path, 'payloads.json'), 'r') as f:
            cls.payloads_content = json.load(f)

    def test_search_by_organization(self):
        """Test if response has the correct structure.
        Each module should have property defined in 'key' variable
        and value same as defined in 'variable' property.
        """
        key = 'organization'
        value = 'ietf'
        path = f'{key}/{value}'
        result = self.client.get(f'api/search/{path}')
        data = json.loads(result.data)
        modules = data.get('yang-catalog:modules')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:modules', data)
        self.assertIn('module', modules)

        for module in modules['module']:
            self.assertIn(key, module)
            self.assertEqual(module.get(key), value)

    def test_search_incorrect_module_key(self):
        """Test error response when invalid 'key' value was provided."""
        key = 'incorrect_key'
        value = 'ietf'
        path = f'{key}/{value}'
        result = self.client.get(f'api/search/{path}')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], f'Search on path {path} is not supported')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_search_no_hits(self):
        """Test error response when no hits were found and 404 status code was returned."""
        key = 'organization'
        value = 'random_organization'
        path = f'{key}/{value}'
        result = self.client.get(f'api/search/{path}')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No module found using provided input data')
        self.assertEqual(data['error'], 'Not found -- in api code')

    @mock.patch('api.my_flask.Redis.get')
    def test_search_no_modules_loaded(self, mock_redis_get: mock.MagicMock):
        """Redis get() method patched to return None.
        Then empty OrderedDict is returned from modules_data() method.
        Test error response when no modules loaded from Redis and 404 status code was returned.
        """
        # Patch mock to return None while getting value from Redis
        mock_redis_get.return_value = None
        key = 'organization'
        value = 'ietf'
        path = f'{key}/{value}'
        result = self.client.get(f'api/search/{path}')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No module found in Redis database')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_rpc_search_get_one(self):
        """Test if response has the correct structure. Response should contain 'output' property.
        Additional property named by 'leaf' variable should be nested inside 'output' property.
        Also list of leaf values of filtered modules should be in property named by 'leaf' property.
        """
        leaf = 'name'
        body = self.payloads_content.get('rpc_search_get_one')
        result = self.client.post(f'api/search-filter/{leaf}', json=body)
        data = json.loads(result.data)
        output = data.get('output')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('output', data)
        self.assertNotEqual(len(output), 0)
        self.assertIn(leaf, output)
        self.assertNotEqual(len(output.get(leaf)), 0)

    def test_rpc_search_get_one_recursive(self):
        """
        Test if response has the correct structure. Response should contain 'output' property.
        Additional property named by 'leaf' variable should be nested inside 'output' property.
        Also list of leaf values of filtered modules should be in property named by 'leaf' property.
        Include 'recursive' property to look for all dependencies of the module
        and search for data in those modules too.
        """
        leaf = 'name'
        body = self.payloads_content.get('rpc_search_get_one')
        body['input']['recursive'] = True
        result = self.client.post(f'api/search-filter/{leaf}', json=body)
        data = json.loads(result.data)
        output = data.get('output')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('output', data)
        self.assertNotEqual(len(output), 0)
        self.assertIn(leaf, output)
        self.assertNotEqual(len(output.get(leaf)), 0)

    def test_rpc_search_get_one_no_body(self):
        """Test error response when no body was send with request."""
        leaf = 'name'
        result = self.client.post(f'api/search-filter/{leaf}')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(
            data['description'],
            'The browser (or proxy) sent a request that this server could not understand.',
        )
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_rpc_search_get_one_no_input(self):
        """Test error response when input do not have correct structure (no 'input' property)."""
        leaf = 'name'
        result = self.client.post(f'api/search-filter/{leaf}', json={})
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'body of request need to start with input')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_rpc_search_get_one_incorrect_leaf(self):
        """Test error response when using incorrect 'leaf' name (one that is not defined by yang-catalog)."""
        leaf = 'random_leaf'
        body = self.payloads_content.get('rpc_search_get_one')
        result = self.client.post(f'api/search-filter/{leaf}', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No module found using provided input data')
        self.assertEqual(data['error'], 'Not found -- in api code')

    @mock.patch('api.my_flask.Redis.get')
    def test_rpc_search_get_one_no_modules_loaded(self, mock_redis_get: mock.MagicMock):
        """Redis get() method patched to return None.
        Then empty OrderedDict is returned from modules_data() method.
        Test error response when no modules loaded from Redis and 404 status code was returned.
        """
        # Patch mock to return None while getting value from Redis
        mock_redis_get.return_value = None
        leaf = 'name'
        body = self.payloads_content.get('rpc_search_get_one')
        result = self.client.post(f'api/search-filter/{leaf}', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No module found in Redis database')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_rpc_search_dependecies(self):
        """Test if response has the correct structure. Each module should have dependencies property
        and organization same as on body of request.
        """
        body = self.payloads_content.get('dependecies')
        result = self.client.post('api/search-filter', json=body)
        data = json.loads(result.data)
        modules = data.get('yang-catalog:modules')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:modules', data)
        self.assertIn('module', modules)

        for module in modules['module']:
            self.assertIn('dependencies', module)
            self.assertEqual(module.get('organization'), 'fujitsu')

    def test_rpc_search_dependents(self):
        """Test if response has the correct structure. Each module should have dependents property
        and organization same as on body of request.
        """
        body = self.payloads_content.get('dependents')
        result = self.client.post('api/search-filter', json=body)
        data = json.loads(result.data)
        modules = data.get('yang-catalog:modules')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:modules', data)
        self.assertIn('module', modules)

        for module in modules['module']:
            self.assertIn('dependents', module)
            self.assertEqual(module.get('organization'), 'ietf')

    def test_rpc_search_submodule(self):
        """Test if response has the correct structure. Each module should have submodule property
        and organization same as on body of request.
        """
        body = self.payloads_content.get('submodule')
        result = self.client.post('api/search-filter', json=body)
        data = json.loads(result.data)
        modules = data.get('yang-catalog:modules')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:modules', data)
        self.assertIn('module', modules)

        for module in modules['module']:
            self.assertIn('submodule', module)
            self.assertEqual(module.get('organization'), 'ietf')

    def test_rpc_search_implementations(self):
        """Test if response has the correct structure. Each module should have implementations property
        and organization same as on body of request.
        """
        body = self.payloads_content.get('implementations')
        result = self.client.post('api/search-filter', json=body)
        data = json.loads(result.data)
        modules = data.get('yang-catalog:modules')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:modules', data)
        self.assertIn('module', modules)

        for module in modules['module']:
            self.assertIn('implementations', module)
            self.assertEqual(module.get('organization'), 'fujitsu')
            implementations = module['implementations']
            self.assertIn('implementation', implementations)
            for implementation in implementations['implementation']:
                self.assertIn('vendor', implementation)
                self.assertIn('software-version', implementation)
                self.assertIn('platform', implementation)
                self.assertIn('software-flavor', implementation)

    def test_rpc_search_no_input(self):
        """Test error response when input do not have correct structure (no 'input' property)."""
        body = {}
        result = self.client.post('api/search-filter', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'body request has to start with "input" container')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_rpc_search_not_found(self):
        """Test error response when no module was found."""
        body = self.payloads_content.get('not_found')
        result = self.client.post('api/search-filter', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No modules found with provided input')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_get_organizations(self):
        """Test if json payload has correct form (should not contain empty 'contributors' list)

        WARNING: if you change this test, make sure the endpoint stays compatible with ycclient
        https://github.com/YangCatalog/backend/issues/551
        """
        result = self.client.get('api/contributors')
        payload = json.loads(result.data)
        contributors_list = payload.get('contributors')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('contributors', payload)
        self.assertNotEqual(len(contributors_list), 0)

    @mock.patch('api.my_flask.Redis.get')
    def test_get_organizations_no_modules(self, mock_redis_get: mock.MagicMock):
        """Redis get() method patched to return None.
        Then empty OrderedDict is returned from modules_data() method.
        This should result into empty 'contributors' list.

        WARNING: if you change this test, make sure the endpoint stays compatible with ycclient
        https://github.com/YangCatalog/backend/issues/551
        """
        mock_redis_get.return_value = None
        result = self.client.get('api/contributors')
        payload = json.loads(result.data)
        contributors_list = payload.get('contributors')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('contributors', payload)
        self.assertEqual(len(contributors_list), 0)

    def test_create_update_from(self):
        """
        Test if payload contains desired output = comparison of pyang outputs for two different yang module revisions.
        """
        desired_output = (
            f'{app_config.d_save_file_dir}/'
            'yang-catalog@2018-04-03.yang:1: the grouping \'yang-lib-imlementation-leafs\', '
            f'defined at {app_config.d_save_file_dir}/yang-catalog@2017-09-26.yang:599 is illegally removed\n'
        )
        file1 = 'yang-catalog'
        revision1 = '2018-04-03'
        file2 = 'yang-catalog'
        revision2 = '2017-09-26'

        path = f'api/services/file1={file1}@{revision1}/check-update-from/file2={file2}@{revision2}'
        result = self.client.get(path)

        response_text = HT.fromstring(result.data).find('body').find('pre').text  # pyright: ignore

        self.assertEqual(desired_output, response_text)

    def test_get_common_by_implementation(self):
        """Test if json payload has correct form (should not contain empty 'output' list)
        Based on request body, each module in 'output' list should not contain empty 'implementations' list.
        """
        body = self.payloads_content.get('get_common')
        result = self.client.post('api/get-common', json=body)
        data = json.loads(result.data)
        output = data.get('output')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('output', data)
        self.assertNotEqual(len(output), 0)

        for module in output:
            self.assertIn('implementations', module)
            self.assertNotEqual(len(module['implementations']['implementation']), 0)
            for implementation in module['implementations']['implementation']:
                # Modules were filtered by following leafs, so each implementation object should contain them
                self.assertIn('platform', implementation)
                self.assertIn('software-version', implementation)
                self.assertIn('vendor', implementation)

    def test_get_common_no_body(self):
        """Test error response when no body was send with request."""
        result = self.client.post('api/get-common')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(
            data['description'],
            'The browser (or proxy) sent a request that this server could not understand.',
        )
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_get_common_no_input(self):
        """Test error response when input do not have correct structure (no 'input' property)."""
        result = self.client.post('api/get-common', json={})
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'body of request need to start with input')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_get_common_no_new_old_container(self):
        """Test error response when input do not have correct structure (no 'first' or 'second' properties)"""
        body = {'input': {'first': {}}}
        result = self.client.post('api/get-common', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'body of request need to contain first and second container')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_get_common_no_hits(self):
        """Test error response when no hits were found and 404 status code was returned."""
        body = self.payloads_content.get('get_common_no_hits')
        result = self.client.post('api/get-common', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No hits found either in first or second input')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_get_common_no_common_modules(self):
        """
        Test error response when no common modules were found and 404 status code was returned
        (different organizations used in filters).
        """
        body = self.payloads_content.get('get_common_no_common_modules')
        result = self.client.post('api/get-common', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No common modules found within provided input')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_compare(self):
        """
        Test if response has the correct structure. Each module should have additional 'reason-to-show' property
        which should have one of the following value: 'New module', 'Different revision'
        """
        body = self.payloads_content.get('compare')

        result = self.client.post('api/compare', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('output', data)

        modules = data['output']

        reasons = ['New module', 'Different revision']
        for module in modules:
            self.assertIn('reason-to-show', module)
            reason = module['reason-to-show']
            self.assertIn(reason, reasons)

    def test_compare_no_body(self):
        """Test error response when no body was send with request."""
        result = self.client.post('api/compare')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(
            data['description'],
            'The browser (or proxy) sent a request that this server could not understand.',
        )
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_compare_no_input(self):
        """Test error response when input do not have correct structure (no 'input' property)."""
        result = self.client.post('api/compare', json={})
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'body of request need to start with input')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_compare_no_new_old_container(self):
        """Test error response when input do not have correct structure (no 'new' or 'old' properties)"""
        body = {'input': {'new': {}}}
        result = self.client.post('api/compare', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'body of request need to contain new and old container')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_compare_no_hits(self):
        """
        Test error response when no hits were found and 404 status code was returned
        (one filter does not find any module).
        """
        body = self.payloads_content.get('compare_no_hits')
        result = self.client.post('api/compare', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No hits found either in old or new input')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_compare_no_new_modules(self):
        """
        Test error response when no new modules were found and 404 status code was returned
        (same filter used as new and old).
        """
        body = self.payloads_content.get('compare_no_new_modules')
        result = self.client.post('api/compare', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No new modules or modules with different revisions found')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_check_semver_same_module(self):
        """Test if json payload has correct form (should not contain empty 'output' list).
        Goal: Check sematic difference for same module with different revisions
        Based on request body, each module in 'output' list should contain certain properties.
        """
        body = self.payloads_content.get('check_semver_same_module')
        result = self.client.post('api/check-semantic-version', json=body)
        data = json.loads(result.data)
        output = data.get('output')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('output', data)
        self.assertNotEqual(len(output), 0)

        for output_module in output:
            self.assertIn('name', output_module)
            self.assertIn('revision-old', output_module)
            self.assertIn('revision-new', output_module)
            self.assertIn('organization', output_module)
            self.assertIn('old-derived-semantic-version', output_module)
            self.assertIn('new-derived-semantic-version', output_module)
            self.assertIn('derived-semantic-version-results', output_module)

    def test_check_semver_same_platform(self):
        """Test if json payload has correct form (should not contain empty 'output' list).
        Goal: Check semantic differences between 1.2 and 1.1.2 software versions from T600 platform.
        Based on request body, each module in 'output' list should contain certain properties.
        """
        body = self.payloads_content.get('check_semver_same_platform')
        result = self.client.post('api/check-semantic-version', json=body)
        data = json.loads(result.data)
        output = data.get('output')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('output', data)
        self.assertNotEqual(len(output), 0)

        for output_module in output:
            self.assertIn('name', output_module)
            self.assertIn('revision-old', output_module)
            self.assertIn('revision-new', output_module)
            self.assertIn('organization', output_module)
            self.assertIn('old-derived-semantic-version', output_module)
            self.assertIn('new-derived-semantic-version', output_module)
            self.assertIn('derived-semantic-version-results', output_module)

    def test_check_semver_no_body(self):
        """Test error response when no body was send with request."""
        result = self.client.post('api/check-semantic-version')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(
            data['description'],
            'The browser (or proxy) sent a request that this server could not understand.',
        )
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_check_semver_no_input(self):
        """Test error response when input do not have correct structure (no 'input' property)."""
        result = self.client.post('api/check-semantic-version', json={})
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'body of request need to start with input')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_check_semver_no_new_old_container(self):
        """Test error response when input do not have correct structure (no 'new' or 'old' properties)"""
        body = {'input': {'new': {}}}
        result = self.client.post('api/check-semantic-version', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'body of request need to contain new and old container')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_check_semver_no_difference(self):
        """Test error response when no difference in semantic versions were found and 404 status code was returned
        (= same filter used as new and old).
        """
        body = self.payloads_content.get('check_semver_no_difference')
        result = self.client.post('api/check-semantic-version', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No different semantic versions with provided input')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_check_semver_no_hits(self):
        """
        Test error response when no hits were found and 404 status code was returned (same filter used as new and old).
        """
        body = self.payloads_content.get('check_semver_no_hits')
        result = self.client.post('api/check-semantic-version', json=body)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No hits found either in old or new input')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_search_vendor_statistics(self):
        """Test if payload contains desired output (os-type)."""
        vendor_name = 'fujitsu'
        desired_os_type = 'FSS2 Linux'
        result = self.client.get(f'api/search/vendor/{vendor_name}')
        payload = json.loads(result.data)
        vendor_data = payload.get(desired_os_type)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn(desired_os_type, payload)
        self.assertNotEqual(len(vendor_data), 0)

    def test_search_vendor_statistics_incorrect_vendor(self):
        """Test if responded with empty payload if vendor does not exist."""
        vendor_name = 'random-vendor'
        result = self.client.get(f'api/search/vendor/{vendor_name}')
        payload = json.loads(result.data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertEqual(payload, {})

    def test_search_vendors(self):
        """Test if vendor json payload has correct form (should contain certain keys)"""
        vendor_name = 'fujitsu'
        path = f'vendor/{vendor_name}'
        result = self.client.get(f'api/search/vendors/{path}')
        payload = json.loads(result.data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:vendor', payload)
        vendor = payload['yang-catalog:vendor'][0]
        self.assertIn('name', vendor)
        self.assertIn('platforms', vendor)
        self.assertEqual(vendor['name'], vendor_name)

    def test_search_vendors_vendor_not_found(self):
        """Test if responded with code 400 if vendor not found."""
        vendor_name = 'random-vendor'
        path = f'vendor/{vendor_name}'

        result = self.client.get(f'api/search/vendors/{path}')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], f'No vendors found on path {path}')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_search_vendors_software_platform(self):
        """Compare values when searching for specific vendor platform (T100)."""
        platform_name = 'T100'
        path = f'vendor/fujitsu/platforms/platform/{platform_name}/'
        result = self.client.get(f'api/search/vendors/{path}')
        payload = json.loads(result.data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:platform', payload)
        platform = payload['yang-catalog:platform'][0]
        self.assertIn('name', platform)
        self.assertIn('software-versions', platform)
        self.assertEqual(platform['name'], platform_name)

    def test_search_vendors_software_version(self):
        """Compare values when searching for specific vendor software version (2.4)."""
        platform_name = 'T100'
        software_version_number = '2.4'
        path = (
            f'vendor/fujitsu/platforms/platform/{platform_name}/'
            f'software-versions/software-version/{software_version_number}'
        )
        result = self.client.get(f'api/search/vendors/{path}')
        payload = json.loads(result.data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:software-version', payload)
        software_version = payload['yang-catalog:software-version'][0]
        self.assertIn('name', software_version)
        self.assertIn('software-flavors', software_version)
        self.assertEqual(software_version['name'], software_version_number)

    def test_search_vendors_software_flavor(self):
        """Compare values when searching for specific vendor software flavor (Linux)."""
        platform_name = 'T100'
        software_version_number = '2.4'
        software_flavor_name = 'Linux'
        path = (
            f'vendor/fujitsu/platforms/platform/{platform_name}/software-versions/'
            f'software-version/{software_version_number}/software-flavors/software-flavor/{software_flavor_name}'
        )
        result = self.client.get(f'api/search/vendors/{path}')
        payload = json.loads(result.data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:software-flavor', payload)
        software_flavor = payload['yang-catalog:software-flavor'][0]
        self.assertIn('name', software_flavor)
        self.assertIn('protocols', software_flavor)
        self.assertIn('modules', software_flavor)
        self.assertEqual(software_flavor['name'], software_flavor_name)

    def test_search_module(self):
        """Compare response payload with content of 'yang-catalog@2018-04-03.json' file from resources.

        WARNING: if you change this test, make sure the endpoint stays compatible with ycclient
        https://github.com/YangCatalog/backend/issues/551
        """
        name = 'yang-catalog'
        revision = '2018-04-03'
        organization = 'ietf'
        result = self.client.get(f'api/search/modules/{name},{revision},{organization}')
        payload = json.loads(result.data)
        module = payload.get('module')[0]

        with open(os.path.join(self.resources_path, 'yang-catalog@2018-04-03.json'), 'r') as f:
            modules_data = json.load(f)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('module', payload)
        for attr, value in modules_data.items():
            self.assertEqual(module[attr], value)

    def test_search_module_not_found(self):
        """Test if responded with code 400 if module not found.

        WARNING: if you change this test, make sure the endpoint stays compatible with ycclient
        https://github.com/YangCatalog/backend/issues/551
        """
        name = 'yang-catalog'
        revision = '2018-01-01'
        organization = 'cisco'

        result = self.client.get(f'api/search/modules/{name},{revision},{organization}')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], f'Module {name}@{revision}/{organization} not found')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_search_module_missing_data(self):
        """Test if responded with code 400 if the input arguments are missing."""
        name = ''
        revision = ''
        organization = ''

        with app.app_context():
            with self.assertRaises(NotFound) as http_error:
                search_bp.search_module(name, revision, organization)

        self.assertEqual(http_error.exception.code, 404)
        self.assertEqual(
            http_error.exception.description,
            f'Module {name}@{revision}/{organization} not found',
        )
        self.assertEqual(http_error.exception.name, 'Not Found')

    def test_get_modules(self):
        """Test if modules json payload has correct form (should not contain empty 'module' list)"""
        result = self.client.get('api/search/modules')
        payload = json.loads(result.data)
        modules = payload.get('module')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('module', payload)
        self.assertNotEqual(len(modules), 0)

    @mock.patch('api.my_flask.Redis.get')
    def test_get_modules_no_modules(self, mock_redis_get: mock.MagicMock):
        """Redis get() method patched to return None.
        Then empty OrderedDict is returned from modules_data() method.
        Test error response when no modules found and 404 status code was returned.
        """
        # Patch mock to return None while getting value from Redis
        mock_redis_get.return_value = None
        result = self.client.get('api/search/modules')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No module is loaded')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_get_vendors(self):
        """Test if vendors json payload has correct form (should not contain empty 'vendor' list)"""
        result = self.client.get('api/search/vendors')
        payload = json.loads(result.data)
        vendors = payload.get('vendor')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('vendor', payload)
        self.assertNotEqual(len(vendors), 0)

    @mock.patch('api.my_flask.Redis.get')
    def test_get_vendors_no_vendors(self, mock_redis_get: mock.MagicMock):
        """Redis get() method patched to return None.
        Then empty OrderedDict is returned from vendors_data() method.
        Test error response when no modules found and 404 status code was returned.
        """
        # Patch mock to return None while getting value from Redis
        mock_redis_get.return_value = None
        result = self.client.get('api/search/vendors')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No vendor is loaded')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_get_catalog(self):
        """Test if catalog json payload has correct form (should contain both 'vendors' and 'modules' data)"""
        result = self.client.get('api/search/catalog')
        payload = json.loads(result.data)
        yang_catalog_data = payload.get('yang-catalog:catalog')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('yang-catalog:catalog', payload)
        self.assertIn('modules', yang_catalog_data)
        self.assertIn('vendors', yang_catalog_data)

    @mock.patch('api.my_flask.Redis.get')
    def test_get_catalog_no_catalog_data(self, mock_redis_get: mock.MagicMock):
        """Redis get() method patched to return None.
        Then empty OrderedDict is returned from catalog_data() method.
        Test error response when no modules found and 404 status code was returned.
        """
        # Patch mock to return None while getting value from Redis
        mock_redis_get.return_value = None
        result = self.client.get('api/search/catalog')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], 'No data loaded to YangCatalog')
        self.assertEqual(data['error'], 'Not found -- in api code')

    def test_create_tree(self):
        """Compare response with content of yang tree stored in yang-tree.txt file."""
        filename = 'yang-catalog'
        revision = '2018-04-03'

        result = self.client.get(f'api/services/tree/{filename}@{revision}.yang')
        data = result.data.decode()
        response_text = HT.fromstring(data).find('body').find('div').find('pre').text  # pyright: ignore

        with open(os.path.join(self.resources_path, 'yang-tree.txt'), 'r') as f:
            yang_tree_data = f.readlines()
            yang_tree_data = ''.join(yang_tree_data)

        self.assertEqual(yang_tree_data, response_text)

    def test_create_tree_incorrect_yang(self):
        """Test if responded with code 400 if the input arguments are not correct (incorrect yang module name)."""
        filename = 'incorrect-yang-file'
        revision = '2018-01-01'
        path_to_yang = f'{app_config.d_save_file_dir}/{filename}@{revision}.yang'

        result = self.client.get(f'api/services/tree/{filename}@{revision}.yang')
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertIn('error', data)
        self.assertEqual(data['description'], f'File {path_to_yang} was not found')
        self.assertEqual(data['error'], 'YangCatalog did not understand the message you have sent')

    def test_create_tree_missing_data(self):
        """Test if responded with code 400 if the input arguments are missing."""
        filename = ''
        revision = ''
        path_to_yang = f'{app_config.d_save_file_dir}/{filename}@{revision}.yang'

        with self.assertRaises(BadRequest) as http_error:
            search_bp.create_tree(filename, revision)

        self.assertEqual(http_error.exception.code, 400)
        self.assertEqual(http_error.exception.description, f'File {path_to_yang} was not found')
        self.assertEqual(http_error.exception.name, 'Bad Request')

    def test_create_reference(self):
        """Compare response with content of yang file from resources."""
        filename = 'yang-catalog'
        revision = '2018-04-03'

        result = self.client.get(f'api/services/reference/{filename}@{revision}.yang')
        data = result.data.decode()
        response_text = data.split('</pre>')[0].split('<pre>')[1]

        with open(os.path.join(self.resources_path, 'all_modules/yang-catalog@2018-04-03.yang'), 'r') as f:
            yang_file_data = escape(f.read())

        self.assertEqual(result.status_code, 200)
        self.assertEqual(yang_file_data, response_text)

    def test_create_reference_file_not_exists(self):
        """Test if text in 'expected_message' is part of received HTML."""
        filename = 'yang-catalog-incorrect-name'
        revision = '2020-01-01'
        expected_message = f'File {filename}@{revision}.yang was not found.'

        result = self.client.get(f'api/services/reference/{filename}@{revision}.yang')
        data = result.data.decode()

        self.assertEqual(result.status_code, 200)
        self.assertIn(expected_message, data)

    @mock.patch('api.views.redisSearch.redisSearch.ac', app_config)
    @mock.patch('api.my_flask.Redis.get')
    def test_modules_data_no_value(self, mock_redis_get: mock.MagicMock):
        """Redis get() method patched to return None.
        Then empty OrderedDict is returned from modules_data() method
        """
        # Patch mock to return None while getting value from Redis
        mock_redis_get.return_value = None
        with app.app_context():
            result = search_bp.modules_data()

        self.assertEqual(len(result), 0)
        self.assertIsInstance(result, collections.OrderedDict)

    @mock.patch('api.views.redisSearch.redisSearch.ac', app_config)
    @mock.patch('api.my_flask.Redis.get')
    def test_vendors_data_no_value(self, mock_redis_get: mock.MagicMock):
        """Redis get() method patched to return None.
        Then empty OrderedDict is returned from vendors_data() method
        """
        # Patch mock to return None while getting value from Redis
        mock_redis_get.return_value = None
        with app.app_context():
            result = search_bp.vendors_data()

        self.assertEqual(len(result), 0)
        self.assertIsInstance(result, collections.OrderedDict)

    @mock.patch('api.my_flask.Redis.get')
    def test_catalog_data_no_value(self, mock_redis_get: mock.MagicMock):
        """Redis get() method patched to return None.
        Then empty OrderedDict is returned from catalog_data() method
        """
        search_bp.ac = app_config
        # Patch mock to return None while getting value from Redis
        mock_redis_get.return_value = None
        with app.app_context():
            result = search_bp.catalog_data()

        self.assertEqual(len(result), 0)
        self.assertIsInstance(result, collections.OrderedDict)


if __name__ == '__main__':
    unittest.main()
