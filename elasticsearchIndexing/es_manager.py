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
from operator import itemgetter

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import AuthorizationException
from utility.create_config import create_config

from elasticsearchIndexing.models.es_indices import ESIndices
from elasticsearchIndexing.models.keywords_names import KeywordsNames


class ESManager:
    def __init__(self) -> None:
        config = create_config()
        es_aws = config.get('DB-Section', 'es-aws')
        elk_credentials = config.get('Secrets-Section', 'elk-secret').strip('"').split(' ')
        self.elk_repo_name = config.get('General-Section', 'elk-repo-name')
        es_host_config = {
            'host': config.get('DB-Section', 'es-host', fallback='localhost'),
            'port': config.get('DB-Section', 'es-port', fallback='9200')
        }
        if es_aws == 'True':
            self.es = Elasticsearch(hosts=[es_host_config], http_auth=(elk_credentials[0], elk_credentials[1]), scheme='https')
        else:
            self.es = Elasticsearch(hosts=[es_host_config])

    def create_index(self, index: ESIndices):
        """ Create Elasticsearch index with given name.

        Argument:
            :param index_name   (str) name of the index to be created
        """
        index_name = index.value
        index_json_name = f'initialize_{index_name}_index.json'
        index_json_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/', index_json_name)
        with open(index_json_path, encoding='utf-8') as reader:
            index_config = json.load(reader)

        create_result = None
        try:
            create_result = self.es.indices.create(index=index_name, body=index_config, ignore=400)
        except AuthorizationException:
            # https://discuss.elastic.co/t/forbidden-12-index-read-only-allow-delete-api/110282/4
            read_only_query = {'index': {'blocks': {'read_only_allow_delete': 'false'}}}
            self.es.indices.put_settings(index=index_name, body=read_only_query)
            create_result = self.es.indices.create(index=index_name, body=index_config, ignore=400)
        return create_result

    def index_exists(self, index: ESIndices) -> bool:
        """ Check if the index already exists. """
        return self.es.indices.exists(index=index.value)

    def autocomplete(self, index: ESIndices, keyword: KeywordsNames, searched_term: str) -> list:
        """ Get list of the modules which will be returned as autocomplete
        after entering the "search_term" by the user.
        Arguments:
            :param keyword          (KeywordsNames)
            :param searched_term    (str)
        """
        autocomplete_json_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/completion.json')
        with open(autocomplete_json_path, encoding='utf-8') as reader:
            autocomplete_query = json.load(reader)

        autocomplete_query['query']['bool']['must'][0]['term'] = {keyword.value: searched_term.lower()}
        autocomplete_query['aggs']['groupby_module']['terms']['field'] = f'{keyword.value}.keyword'
        rows = self.es.search(index=index.value, body=autocomplete_query)
        hits = rows['aggregations']['groupby_module']['buckets']

        result = [hit['key'] for hit in hits]

        return result

    def delete_from_index(self, index: ESIndices, module: dict):
        delete_module_query = self._get_name_revision_query(index, module)

        return self.es.delete_by_query(index=index.value, body=delete_module_query, conflicts='proceed')

    def delete_from_indices(self, module: dict):
        for index in ESIndices:
            self.delete_from_index(index, module)

    def index_module(self, index: ESIndices, document: dict):
        # TODO: Remove this after reindexing and unification of both indices
        if index == ESIndices.MODULES:
            path = document['path']
            del document['path']
            document['dir'] = path

            name = document['name']
            del document['name']
            document['module'] = name

        return self.es.index(index=index.value, body=document, request_timeout=40)

    def match_all(self, index: ESIndices):
        def _store_hits(hits: list, all_results: dict):
            for hit in hits:
                name = ''
                path = ''
                if index == ESIndices.AUTOCOMPLETE:
                    name = hit['_source']['name']
                    path = hit['_source']['path']
                if index == ESIndices.MODULES:
                    name = hit['_source']['module']
                    path = hit['_source']['dir']
                mod = {
                    'name': name,
                    'revision': hit['_source']['revision'],
                    'organization': hit['_source']['organization'],
                    'path': path
                }
                key = '{}@{}/{}'.format(mod.get('name'), mod.get('revision'), mod.get('organization'))
                if key not in all_results:
                    all_results[key] = mod
                else:
                    print('{} already in all results'.format(key))

        all_results = {}
        match_all_query = {
            'query': {
                'match_all': {}
            }
        }
        total_index_docs = 0
        es_result = self.es.search(index=index.value, body=match_all_query, scroll=u'10s', size=250)
        scroll_id = es_result.get('_scroll_id')
        hits = es_result['hits']['hits']
        _store_hits(hits, all_results)
        total_index_docs += len(hits)

        while es_result['hits']['hits']:
            es_result = self.es.scroll(
                scroll_id=scroll_id,
                scroll=u'10s'
            )

            scroll_id = es_result.get('_scroll_id')
            hits = es_result['hits']['hits']
            _store_hits(hits, all_results)
            total_index_docs += len(hits)

        self.es.clear_scroll(scroll_id=scroll_id, ignore=(404, ))
        return all_results

    def get_module_by_name_revision(self, index: ESIndices, module: dict) -> bool:
        get_module_query = self._get_name_revision_query(index, module)

        es_result = self.es.search(index=index.value, body=get_module_query)

        return es_result['hits']['hits']

    def get_latest_module_revision(self, index: ESIndices, name: str):
        query_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/latest_revision_query.json')
        with open(query_path, encoding='utf-8') as reader:
            latest_revision_query = json.load(reader)

        # TODO: Remove this after reindexing and unification of both indices
        if index == ESIndices.AUTOCOMPLETE:
            del latest_revision_query['query']['bool']['must'][0]['match_phrase']['module.keyword']
            latest_revision_query['query']['bool']['must'][0]['match_phrase'] = {
                'name.keyword': {
                    'query': name
                }
            }
        else:
            latest_revision_query['query']['bool']['must'][0]['match_phrase']['module.keyword']['query'] = name

        es_result = self.es.search(index=index.value, body=latest_revision_query)

        return es_result['hits']['hits']

    def document_exists(self, index: ESIndices, module: dict) -> bool:
        get_module_query = self._get_name_revision_query(index, module)

        es_count = self.es.count(index=index.value, body=get_module_query)

        return es_count['count'] > 0

    def create_snapshot_repository(self, compress):
        body = {
            'type': 'fs',
            'settings': {
                'location': self.elk_repo_name,
                'compress': compress
            }
        }
        es_result = self.es.snapshot.create_repository(repository=self.elk_repo_name, body=body)

        return es_result

    def create_snapshot(self, snapshot_name: str):
        index_body = {
            'indices': '_all'
        }
        return self.es.snapshot.create(repository=self.elk_repo_name, snapshot=snapshot_name, body=index_body)

    def get_sorted_snapshots(self) -> list:
        snapshots = self.es.snapshot.get(repository=self.elk_repo_name, snapshot='_all')['snapshots']
        return sorted(snapshots, key=itemgetter('start_time_in_millis'))

    def restore_snapshot(self, snapshot_name: str):
        index_body = {
            'indices': '_all'
        }
        return self.es.snapshot.restore(repository=self.elk_repo_name, snapshot=snapshot_name, body=index_body)

    def delete_snapshot(self, snapshot_name: str):
        return self.es.snapshot.delete(repository=self.elk_repo_name, snapshot=snapshot_name)

    def _get_name_revision_query(self, index: ESIndices, module: dict):
        module_search_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/module_search.json')
        with open(module_search_path, encoding='utf-8') as reader:
            name_revision_query = json.load(reader)

        # TODO: Remove this after reindexing and unification of both indices
        if index == ESIndices.AUTOCOMPLETE:
            del name_revision_query['query']['bool']['must'][0]['match_phrase']['module.keyword']
            name_revision_query['query']['bool']['must'][0]['match_phrase'] = {
                'name.keyword': {
                    'query': module['name']
                }
            }
        else:
            name_revision_query['query']['bool']['must'][0]['match_phrase']['module.keyword']['query'] = module['name']
        name_revision_query['query']['bool']['must'][1]['match_phrase']['revision']['query'] = module['revision']

        return name_revision_query
