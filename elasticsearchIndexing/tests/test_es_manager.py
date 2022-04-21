# Copyright The IETF Trust 2022, All Rights Reserved
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
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

import json
import os
import unittest
from unittest import mock

from elasticsearch import Elasticsearch
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from utility.create_config import create_config


class MockESManager(ESManager):
    def __init__(self) -> None:
        self.es = mock.MagicMock()


class TestESManagerWithoutIndexClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestESManagerWithoutIndexClass, self).__init__(*args, **kwargs)
        config = create_config()
        es_host_config = {
            'host': config.get('DB-Section', 'es-host', fallback='localhost'),
            'port': config.get('DB-Section', 'es-port', fallback='9200')
        }
        self.es = Elasticsearch(hosts=[es_host_config])
        self.test_index = ESIndices.TEST

    def setUp(self):
        self.es_manager = ESManager()
        self.es.indices.delete(index=ESIndices.TEST.value, ignore=[400, 404])

    def test_create_index(self):
        create_result = self.es_manager.create_index(self.test_index)

        self.assertIn('acknowledged', create_result)
        self.assertIn('index', create_result)
        self.assertTrue(create_result['acknowledged'])
        self.assertEqual(create_result['index'], self.test_index.value)


class TestESManagerWithIndexClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestESManagerWithIndexClass, self).__init__(*args, **kwargs)
        config = create_config()
        es_host_config = {
            'host': config.get('DB-Section', 'es-host', fallback='localhost'),
            'port': config.get('DB-Section', 'es-port', fallback='9200')
        }
        self.es = Elasticsearch(hosts=[es_host_config])
        self.test_index = ESIndices.TEST

    def setUp(self):
        self.es_manager = ESManager()
        index_json_name = f'initialize_{self.test_index.value}_index.json'
        index_json_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/', index_json_name)
        with open(index_json_path, encoding='utf-8') as reader:
            index_config = json.load(reader)
        self.es.indices.create(index=self.test_index.value, body=index_config, ignore=400)

    def test_create_index_already_exists(self):
        create_result = self.es_manager.create_index(self.test_index)

        self.assertIn('error', create_result)
        self.assertIn('status', create_result)
        self.assertEqual(create_result['status'], 400)
        self.assertEqual(create_result['error']['index'], self.test_index.value)
        self.assertEqual(create_result['error']['type'], 'resource_already_exists_exception')


if __name__ == '__main__':
    unittest.main()
