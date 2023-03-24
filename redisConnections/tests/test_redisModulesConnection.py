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

from redis import Redis

from redisConnections.redisConnection import RedisConnection
from utility.create_config import create_config


class TestRedisModulesConnectionClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.redis_key = 'ietf-bgp@2021-10-25/ietf'
        config = create_config()
        _redis_host = config.get('DB-Section', 'redis-host')
        _redis_port = config.get('DB-Section', 'redis-port')
        resources_path = os.path.join(os.environ['BACKEND'], 'redisConnections/tests/resources')
        cls.redisConnection = RedisConnection(modules_db=6, vendors_db=9)
        cls.modulesDB = Redis(host=_redis_host, port=_redis_port, db=6)  # pyright: ignore
        cls.vendorsDB = Redis(host=_redis_host, port=_redis_port, db=9)  # pyright: ignore
        with open(os.path.join(resources_path, 'ietf-bgp@2021-10-25.json'), 'r') as f:
            cls.original_data = json.load(f)

    def setUp(self):
        self.modulesDB.set(self.redis_key, json.dumps(self.original_data))
        self.modulesDB.set('modules-data', json.dumps({self.redis_key: self.original_data}))

    def tearDown(self):
        self.modulesDB.flushdb()
        self.vendorsDB.flushdb()

    def test_get_module(self):
        name = 'ietf-bgp'
        revision = '2021-10-25'
        organization = 'ietf'
        redis_key = f'{name}@{revision}/{organization}'

        raw_data = self.redisConnection.get_module(redis_key)
        data = json.loads(raw_data)

        self.assertNotEqual(data, '{}')
        self.assertEqual(data.get('name'), name)
        self.assertEqual(data.get('revision'), revision)
        self.assertEqual(data.get('organization'), organization)

    @mock.patch('redisConnections.redisConnection.Redis.get')
    def test_get_module_key_not_exists(self, mock_redis_get: mock.MagicMock):
        mock_redis_get.return_value = None
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        data = self.redisConnection.get_module(redis_key)

        self.assertEqual(data, '{}')

    def test_get_all_modules(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        raw_data = self.redisConnection.get_all_modules()
        data = json.loads(raw_data)

        self.assertNotEqual(raw_data, '{}')
        self.assertIn(redis_key, data)

    @mock.patch('redisConnections.redisConnection.Redis.get')
    def test_get_all_modules_key_not_exists(self, mock_redis_get: mock.MagicMock):
        mock_redis_get.return_value = None
        data = self.redisConnection.get_all_modules()

        self.assertEqual(data, '{}')

    def test_set_redis_module(self):
        name = 'ietf-bgp'
        revision = '2021-10-25'
        organization = 'ietf'
        redis_key = f'{name}@{revision}/{organization}'
        self.modulesDB.flushdb()

        result = self.redisConnection.set_module(self.original_data, redis_key)
        raw_data = self.redisConnection.get_module(redis_key)
        data = json.loads(raw_data)

        self.assertTrue(result)
        self.assertNotEqual(data, '{}')
        self.assertEqual(data.get('name'), name)
        self.assertEqual(data.get('revision'), revision)
        self.assertEqual(data.get('organization'), organization)

    def test_populate_modules_empty_database(self):
        self.modulesDB.flushdb()
        name = 'ietf-bgp'
        revision = '2021-10-25'
        organization = 'ietf'
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        module = deepcopy(self.original_data)

        self.redisConnection.populate_modules([module])
        raw_data = self.redisConnection.get_module(redis_key)
        data = json.loads(raw_data)

        self.assertNotEqual(data, {})
        self.assertEqual(data.get('name'), name)
        self.assertEqual(data.get('revision'), revision)
        self.assertEqual(data.get('organization'), organization)

    def test_reload_modules_cache(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        self.modulesDB.delete('modules-data')
        result = self.redisConnection.reload_modules_cache()
        raw_data = self.redisConnection.get_all_modules()
        data = json.loads(raw_data)

        self.assertTrue(result)
        self.assertNotEqual(raw_data, '{}')
        self.assertIn(redis_key, data)

    def test_reload_modules_cache_empty_database(self):
        self.modulesDB.flushdb()

        result = self.redisConnection.reload_modules_cache()
        data = self.redisConnection.get_all_modules()

        self.assertTrue(result)
        self.assertEqual(data, '{}')

    def test_reload_modules_cache_changed_string_property(self):
        new_description = 'Updated description'
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        module = deepcopy(self.original_data)
        module['description'] = new_description

        self.redisConnection.populate_modules([module])
        result = self.redisConnection.reload_modules_cache()
        raw_data = self.redisConnection.get_all_modules()
        data = json.loads(raw_data)

        self.assertTrue(result)
        self.assertNotEqual(raw_data, '{}')
        self.assertIn(redis_key, data)
        self.assertEqual(data.get(redis_key).get('description'), new_description)

    def test_reload_modules_cache_changed_submodule_property(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        module = deepcopy(self.original_data)
        original_length = len(module['submodule'])

        new_submodule = {
            'name': 'yang-catalog',
            'revision': '2018-04-03',
            'schema': 'https://raw.githubusercontent.com/YangModels/yang/yang-catalog@2018-04-03.yang',
        }

        module['submodule'].append(new_submodule)

        self.redisConnection.populate_modules([module])
        result = self.redisConnection.reload_modules_cache()
        raw_data = self.redisConnection.get_all_modules()
        data = json.loads(raw_data)

        self.assertTrue(result)
        self.assertNotEqual(raw_data, '{}')
        self.assertIn(redis_key, data)
        self.assertIn(new_submodule, data[redis_key]['submodule'])
        self.assertEqual(original_length + 1, len(data[redis_key]['submodule']))

    def test_reload_modules_cache_changed_dependencies_property(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        module = deepcopy(self.original_data)
        original_length = len(module['dependencies'])

        new_dependency = {
            'name': 'yang-catalog',
            'schema': 'https://raw.githubusercontent.com/YangModels/yang/yang-catalog@2018-04-03.yang',
        }

        module['dependencies'].append(new_dependency)

        self.redisConnection.populate_modules([module])
        result = self.redisConnection.reload_modules_cache()
        raw_data = self.redisConnection.get_all_modules()
        data = json.loads(raw_data)

        self.assertTrue(result)
        self.assertNotEqual(raw_data, '{}')
        self.assertIn(redis_key, data)
        self.assertIn(new_dependency, data[redis_key]['dependencies'])
        self.assertEqual(original_length + 1, len(data[redis_key]['dependencies']))

    def test_reload_modules_cache_updated_scheme_in_dependents_property(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        module = deepcopy(self.original_data)
        original_length = len(module['dependents'])

        new_dependent = {
            'name': 'ietf-bgp-sr',
            'revision': '2018-06-26',
            'schema': 'https://raw.githubusercontent.com/YangModels/yang/master/experimental/'
            'ietf-extracted-YANG-modules/ietf-bgp-sr@2018-06-26.yang',
        }

        module['dependents'][1] = new_dependent

        self.redisConnection.populate_modules([module])
        result = self.redisConnection.reload_modules_cache()
        raw_data = self.redisConnection.get_all_modules()
        data = json.loads(raw_data)

        self.assertTrue(result)
        self.assertNotEqual(raw_data, '{}')
        self.assertIn(redis_key, data)
        self.assertIn(new_dependent, data[redis_key]['dependents'])
        self.assertEqual(original_length, len(data[redis_key]['dependents']))

    def test_reload_modules_cache_changed_implementations_property(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        module = deepcopy(self.original_data)
        original_length = len(module['implementations']['implementation'])

        new_implementation = {
            'conformance-type': 'implement',
            'feature': ['candidate'],
            'feature-set': 'ALL',
            'os-type': 'VRP',
            'os-version': 'V800R011C10SPC810',
            'platform': 'ne5000e',
            'software-flavor': 'ALL',
            'software-version': 'V800R011C10SPC810',
            'vendor': 'huawei',
        }

        module['implementations']['implementation'].append(new_implementation)

        self.redisConnection.populate_modules([module])
        result = self.redisConnection.reload_modules_cache()
        raw_data = self.redisConnection.get_all_modules()
        data = json.loads(raw_data)

        self.assertTrue(result)
        self.assertNotEqual(raw_data, '{}')
        self.assertIn(redis_key, data)
        self.assertIn(new_implementation, data[redis_key]['implementations']['implementation'])
        self.assertEqual(original_length + 1, len(data[redis_key]['implementations']['implementation']))

    def test_reload_modules_cache_duplicite_implementations_property(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        module = deepcopy(self.original_data)
        original_length = len(module['implementations']['implementation'])

        new_implementation = {
            'conformance-type': 'implement',
            'feature': ['candidate'],
            'feature-set': 'ALL',
            'os-type': 'VRP',
            'os-version': 'V800R013C00',
            'platform': 'ne9000',
            'software-flavor': 'ALL',
            'software-version': 'V800R013C00',
            'vendor': 'huawei',
        }

        module['implementations']['implementation'].append(new_implementation)

        self.redisConnection.populate_modules([module])
        result = self.redisConnection.reload_modules_cache()
        raw_data = self.redisConnection.get_all_modules()
        data = json.loads(raw_data)

        self.assertTrue(result)
        self.assertNotEqual(raw_data, '{}')
        self.assertIn(redis_key, data)
        self.assertIn(new_implementation, data[redis_key]['implementations']['implementation'])
        self.assertEqual(original_length, len(data[redis_key]['implementations']['implementation']))

    def test_delete_modules(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'

        result = self.redisConnection.delete_modules([redis_key])
        data = self.redisConnection.get_module(redis_key)

        self.assertEqual(result, 1)
        self.assertEqual(data, '{}')

    def test_delete_modules_with_reload_modules_cache(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'

        delete_result = self.redisConnection.delete_modules([redis_key])
        reload_result = self.redisConnection.reload_modules_cache()
        data = self.redisConnection.get_module(redis_key)
        raw_all_modules_data = self.redisConnection.get_all_modules()
        all_modules_data = json.loads(raw_all_modules_data)

        self.assertEqual(delete_result, 1)
        self.assertTrue(reload_result)
        self.assertEqual(data, '{}')
        self.assertEqual(all_modules_data, {})
        self.assertNotIn(redis_key, all_modules_data)

    def test_delete_modules_non_existing_key(self):
        redis_key = 'random-key'

        result = self.redisConnection.delete_modules([redis_key])

        self.assertEqual(result, 0)

    def test_delete_modules_multiple_keys(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        modules_keys = [redis_key, 'modules-data']

        result = self.redisConnection.delete_modules(modules_keys)
        data = self.redisConnection.get_module(redis_key)
        all_modules_data = self.redisConnection.get_all_modules()

        self.assertEqual(result, 2)
        self.assertEqual(data, '{}')
        self.assertEqual(all_modules_data, '{}')

    def test_delete_modules_multiple_keys_with_non_existing_keys(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        modules_keys = [redis_key, 'random-key']

        result = self.redisConnection.delete_modules(modules_keys)
        data = self.redisConnection.get_module(redis_key)

        self.assertEqual(result, 1)
        self.assertEqual(data, '{}')

    def test_delete_dependent(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        dependent_to_delete = 'ietf-bgp-l3vpn'
        module = deepcopy(self.original_data)
        original_length = len(module['dependents'])

        result = self.redisConnection.delete_dependent(redis_key, dependent_to_delete)
        raw_data = self.redisConnection.get_module(redis_key)
        data = json.loads(raw_data)

        dependents_list_names = [dependent.get('name') for dependent in data['dependents']]

        self.assertTrue(result)
        self.assertEqual(original_length - 1, len(data['dependents']))
        self.assertNotIn(dependent_to_delete, dependents_list_names)

    def test_delete_dependent_not_existing_dependent(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'
        dependent_to_delete = 'yang-catalog'
        module = deepcopy(self.original_data)
        original_length = len(module['dependents'])

        result = self.redisConnection.delete_dependent(redis_key, dependent_to_delete)
        raw_data = self.redisConnection.get_module(redis_key)
        data = json.loads(raw_data)

        dependents_list_names = [dependent.get('name') for dependent in data['dependents']]

        self.assertFalse(result)
        self.assertEqual(original_length, len(data['dependents']))
        self.assertNotIn(dependent_to_delete, dependents_list_names)

    def test_delete_expires(self):
        redis_key = 'ietf-bgp@2021-10-25/ietf'

        module = deepcopy(self.original_data)
        result = self.redisConnection.delete_expires(module)
        raw_data = self.redisConnection.get_module(redis_key)
        data = json.loads(raw_data)

        self.assertTrue(result)
        self.assertNotEqual(raw_data, '{}')
        self.assertNotIn('expires', data)


if __name__ == '__main__':
    unittest.main()
