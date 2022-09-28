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

    def setUp(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = create_config()
        self.resources_path = os.path.join(os.environ['BACKEND'], 'tests', 'resources')
        self._configure_es(config)
        self.redis_connection_mock = RedisConnectionMock()
        self.grep_search = GrepSearch(
            config=config, es_manager=self.es_manager, modules_es_index=self.es_index,
            redis_connection=self.redis_connection_mock,
        )

    def tearDown(self):
        super().tearDown()
        self.es.indices.delete(index=self.es_index.value, ignore=[400, 404])

    def _configure_es(self, config: ConfigParser):
        es_host_config = {
            'host': config.get('DB-Section', 'es-host', fallback='localhost'),
            'port': config.get('DB-Section', 'es-port', fallback='9200')
        }
        self.es = Elasticsearch(hosts=[es_host_config])
        self.es_manager = ESManager(self.es)
        self.es_index = ESIndices.TEST_SEARCH
        self.es_test_data = self._load_es_test_data()
        index_json_name = f'initialize_{self.es_index.value}_index.json'
        index_json_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing', 'json', index_json_name)
        with open(index_json_path, encoding='utf-8') as reader:
            index_config = json.load(reader)
        self.es.indices.create(index=self.es_index.value, body=index_config, ignore=400)
        all_modules = self.es_test_data['all_modules']
        for module in all_modules:
            self.es.index(index=self.es_index.value, body=module, refresh='true')

    def _load_es_test_data(self):
        data_file_path = os.path.join(self.resources_path, 'search_test_data.json')
        with open(data_file_path, 'r') as reader:
            test_data = json.load(reader)
        return test_data

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

    def test_empty_search(self):
        organizations = []
        search = 'non_existent_search_term1|non_existent_search_term2|non_existent_search_term3'
        search_result = self.grep_search.search(organizations, search)
        self.assertEqual(search_result, [])
