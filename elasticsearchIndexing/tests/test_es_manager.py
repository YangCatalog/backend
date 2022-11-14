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

from ddt import data, ddt
from elasticsearch import Elasticsearch

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from elasticsearchIndexing.models.keywords_names import KeywordsNames
from utility.create_config import create_config


class TestESManagerClass(unittest.TestCase):
    es: Elasticsearch
    test_index: ESIndices

    @classmethod
    def setUpClass(cls):
        config = create_config()
        es_host_config = {
            'host': config.get('DB-Section', 'es-host', fallback='localhost'),
            'port': config.get('DB-Section', 'es-port', fallback='9200'),
        }
        cls.es = Elasticsearch(hosts=[es_host_config])
        cls.es_manager = ESManager(cls.es)
        cls.test_index = ESIndices.TEST
        resources_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/tests/resources')
        with open(os.path.join(resources_path, 'es_test_data.json'), 'r') as reader:
            cls.test_data = json.load(reader)
        cls.ietf_rip_module = {'name': 'ietf-rip', 'revision': '2020-02-20', 'organization': 'ietf'}

    def setUp(self):
        self.es.indices.delete(index=self.test_index.value, ignore=[400, 404])

    def tearDown(self):
        self.es.indices.delete(index=self.test_index.value, ignore=[400, 404])


class TestESManagerWithoutIndexClass(TestESManagerClass):
    def test_create_index(self):
        create_result = self.es_manager.create_index(self.test_index)

        self.assertIn('acknowledged', create_result)
        self.assertIn('index', create_result)
        self.assertTrue(create_result['acknowledged'])
        self.assertEqual(create_result['index'], self.test_index.value)

    def test_index_exists(self):
        index_exists = self.es_manager.index_exists(self.test_index)

        self.assertFalse(index_exists)


class TestESManagerWithEmptyIndexClass(TestESManagerClass):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        index_json_name = f'initialize_{cls.test_index.value}_index.json'
        index_json_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/', index_json_name)
        with open(index_json_path, encoding='utf-8') as reader:
            cls.index_config = json.load(reader)

    def setUp(self):
        super().setUp()
        self.es.indices.create(index=self.test_index.value, body=self.index_config, ignore=400)

    def test_create_index_already_exists(self):
        create_result = self.es_manager.create_index(self.test_index)

        self.assertIn('error', create_result)
        self.assertIn('status', create_result)
        self.assertEqual(create_result['status'], 400)
        self.assertEqual(create_result['error']['index'], self.test_index.value)
        self.assertEqual(create_result['error']['type'], 'resource_already_exists_exception')

    def test_index_exists(self):
        index_exists = self.es_manager.index_exists(self.test_index)

        self.assertTrue(index_exists)

    def test_document_exists(self):
        in_es = self.es_manager.document_exists(self.test_index, self.ietf_rip_module)

        self.assertFalse(in_es)

    def test_autocomplete_no_results(self):
        searched_term = 'ietf-'
        results = self.es_manager.autocomplete(self.test_index, KeywordsNames.NAME, searched_term)

        self.assertEqual(results, [])

    def test_delete_from_index(self):
        delete_result = self.es_manager.delete_from_index(self.test_index, self.ietf_rip_module)

        self.assertIn('deleted', delete_result)
        self.assertEqual(delete_result['deleted'], 0)

    def test_index_module(self):
        index_result = self.es_manager.index_module(self.test_index, self.ietf_rip_module)

        self.assertIn('result', index_result)
        self.assertEqual(index_result['result'], 'created')
        self.assertEqual(index_result['_shards']['successful'], 1)
        self.assertEqual(index_result['_shards']['failed'], 0)

    def test_get_module_by_name_revision(self):
        hits = self.es_manager.get_module_by_name_revision(self.test_index, self.ietf_rip_module)

        self.assertEqual(hits, [])

    def test_get_sorted_module_revisions(self):
        name = 'ietf-rip'
        hits = self.es_manager.get_sorted_module_revisions(self.test_index, name)

        self.assertEqual(hits, [])

    def test_match_all(self):
        all_es_modules = self.es_manager.match_all(self.test_index)

        self.assertEqual(all_es_modules, {})


@ddt
class TestESManagerAutocompleteIndexClass(TestESManagerClass):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        index_json_name = f'initialize_{cls.test_index.value}_index.json'
        index_json_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/', index_json_name)
        with open(index_json_path, encoding='utf-8') as reader:
            cls.index_config = json.load(reader)
        cls.autocomplete_modules = cls.test_data['autocomplete_modules']

    def setUp(self):
        super().setUp()
        self.es.indices.create(index=self.test_index.value, body=self.index_config, ignore=400)
        for module in self.autocomplete_modules:
            self.es.index(index=self.test_index.value, body=module, refresh='true')

    @data('ietf-', 'IETF-R', '-yang-')
    def test_autocomplete(self, searched_term: str):
        results = self.es_manager.autocomplete(self.test_index, KeywordsNames.NAME, searched_term)

        self.assertNotEqual(results, [])
        for result in results:
            self.assertIn(searched_term.lower(), result)

    @data('a', 'ab', 'ief-r')
    def test_autocomplete_no_results(self, searched_term: str):
        results = self.es_manager.autocomplete(self.test_index, KeywordsNames.NAME, searched_term)

        self.assertEqual(results, [])

    @data('ietf', 'open')
    def test_autocomplete_organization(self, searched_term: str):
        results = self.es_manager.autocomplete(self.test_index, KeywordsNames.ORGANIZATION, searched_term)

        self.assertNotEqual(results, [])
        for result in results:
            self.assertIn(searched_term.lower(), result)

    @data('i', 'ie', 'random')
    def test_autocomplete_organization_no_results(self, searched_term: str):
        results = self.es_manager.autocomplete(self.test_index, KeywordsNames.ORGANIZATION, searched_term)

        self.assertEqual(results, [])

    def test_delete_from_index(self):
        delete_result = self.es_manager.delete_from_index(self.test_index, self.ietf_rip_module)

        self.assertIn('deleted', delete_result)
        self.assertNotEqual(delete_result['deleted'], 0)

    def test_document_exists(self):
        in_es = self.es_manager.document_exists(self.test_index, self.ietf_rip_module)

        self.assertTrue(in_es)

    def test_get_module_by_name_revision(self):
        hits = self.es_manager.get_module_by_name_revision(self.test_index, self.ietf_rip_module)

        self.assertNotEqual(hits, [])
        self.assertEqual(len(hits), 1)
        hit = hits.pop()
        self.assertEqual(hit['_source'], self.ietf_rip_module)

    def test_get_module_by_name_revision_not_exists(self):
        module = {'name': 'random', 'revision': '2022-01-01', 'organization': 'random'}
        hits = self.es_manager.get_module_by_name_revision(self.test_index, module)

        self.assertEqual(hits, [])

    def test_get_sorted_module_revisions(self):
        name = 'ietf-rip'
        hits = self.es_manager.get_sorted_module_revisions(self.test_index, name)

        self.assertNotEqual(hits, [])
        for hit in hits:
            self.assertEqual(hit['_source']['name'], name)

    def test_get_sorted_module_revisions_not_exists(self):
        name = 'random'
        hits = self.es_manager.get_sorted_module_revisions(self.test_index, name)

        self.assertEqual(hits, [])

    def test_match_all(self):
        all_es_modules = self.es_manager.match_all(self.test_index)

        self.assertNotEqual(all_es_modules, {})
        for module in all_es_modules.values():
            self.assertIn('name', module)
            self.assertIn('revision', module)
            self.assertIn('organization', module)


if __name__ == '__main__':
    unittest.main()
