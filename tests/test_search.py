import json
import os
import unittest
from configparser import ConfigParser

from elasticsearch import Elasticsearch

from api.views.yangSearch.grep_search import GrepSearch
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from utility.create_config import create_config


class RedisConnectionMock:
    def get_module(self, module_key: str):
        return b'{}'


class TestSearchClass(unittest.TestCase):
    resources_path: str
    es: Elasticsearch
    es_manager: ESManager
    es_index: ESIndices

    @classmethod
    def setUpClass(cls):
        config = create_config()
        cls.resources_path = os.path.join(os.environ['BACKEND'], 'tests', 'resources')
        cls._configure_es(config)
        redis_connection_mock = RedisConnectionMock()
        cls.grep_search = GrepSearch(
            config=config,
            es_manager=cls.es_manager,
            modules_es_index=cls.es_index,
            redis_connection=redis_connection_mock,
        )

    @classmethod
    def _configure_es(cls, config: ConfigParser):
        es_host_config = {
            'host': config.get('DB-Section', 'es-host', fallback='localhost'),
            'port': config.get('DB-Section', 'es-port', fallback='9200'),
        }
        cls.es = Elasticsearch(hosts=[es_host_config])
        cls.es_manager = ESManager(cls.es)
        cls.es_index = ESIndices.TEST_SEARCH
        with open(os.path.join(cls.resources_path, 'search_test_data.json'), 'r') as reader:
            es_test_data = json.load(reader)
        index_json_name = f'initialize_{cls.es_index.value}_index.json'
        index_json_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing', 'json', index_json_name)
        with open(index_json_path, encoding='utf-8') as reader:
            index_config = json.load(reader)
        cls.es.indices.create(index=cls.es_index.value, body=index_config, ignore=400)
        all_modules = es_test_data['all_modules']
        for module in all_modules:
            cls.es.index(index=cls.es_index.value, body=module, refresh='true')

    @classmethod
    def tearDownClass(cls):
        cls.es.indices.delete(index=cls.es_index.value, ignore=[400, 404])

    def test_grep_search(self):
        organizations = ['ietf']
        simple_search = 'typedef minutes64 {\n.*type uint64;'
        simple_search_result = self.grep_search.search(organizations, simple_search)
        self.assertNotEqual(simple_search_result, [])
        complicated_search = (
            'identity restconf {\n.*base protocol;|typedef email-address {\n.*type string {|'
            'typedef email-address {\n.*type string {\n.*pattern "'
        )
        complicated_search_result = self.grep_search.search(organizations, complicated_search)
        self.assertNotEqual(complicated_search_result, [])
        modules_from_complicated_search_result = [
            f'{module_data["module-name"]}@{module_data["revision"]}' for module_data in complicated_search_result
        ]
        self.assertIn('yang-catalog@2017-09-26', modules_from_complicated_search_result)
        self.assertIn('yang-catalog@2018-04-03', modules_from_complicated_search_result)

    def test_empty_grep_search(self):
        organizations = []
        search = 'non_existent_search_term1|non_existent_search_term2|non_existent_search_term3'
        search_result = self.grep_search.search(organizations, search)
        self.assertEqual(search_result, [])

    def test_inverted_grep_search(self):
        organizations = ['cisco']
        simple_search = 'organization'
        simple_search_result = self.grep_search.search(organizations, simple_search, inverted_search=True)
        self.assertEqual(simple_search_result, [])
        organizations = ['ietf']
        complicated_search = (
            'identity restconf {\n.*base protocol;|typedef email-address {\n.*type string {|'
            'typedef email-address {\n.*type string {\n.*pattern "'
        )
        complicated_search_result = self.grep_search.search(organizations, complicated_search, inverted_search=True)
        self.assertNotEqual(complicated_search_result, [])
        modules_from_complicated_search_result = [
            f'{module_data["module-name"]}@{module_data["revision"]}' for module_data in complicated_search_result
        ]
        self.assertNotIn('yang-catalog@2017-09-26', modules_from_complicated_search_result)
        self.assertNotIn('yang-catalog@2018-04-03', modules_from_complicated_search_result)

    def test_empty_inverted_grep_search(self):
        organizations = []
        search = 'namespace'
        search_result = self.grep_search.search(organizations, search, inverted_search=True)
        self.assertEqual(search_result, [])

    def test_empty_case_sensitive_grep_search(self):
        organizations = []
        search = 'Namespace ".*";'
        search_result = self.grep_search.search(organizations, search, case_sensitive=True)
        self.assertEqual(search_result, [])
