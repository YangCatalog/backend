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
from elasticsearch.exceptions import AuthorizationException, RequestError
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
            :param index   (ESIndices) Index to be created
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
        """ Check if the index already exists. 

        Argument:
            :param index   (ESIndices) Index to be checked
        """
        return self.es.indices.exists(index=index.value)

    def autocomplete(self, index: ESIndices, keyword: KeywordsNames, searched_term: str) -> list:
        """ Get list of the modules which will be returned as autocomplete
        after entering the 'searched_term' by the user.

        Arguments:
            :param index            (ESIndices) Index in which to search
            :param keyword          (KeywordsNames)
            :param searched_term    (str) String entered by the user
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

    def delete_from_index(self, index: ESIndices, module: dict) -> dict:
        """ Delete module from the index.

        Arguments:
            :param index        (ESIndices) Target index from which to delete module
            :param document     (dict) Document to delete
        """
        delete_module_query = self._get_name_revision_query(index, module)

        return self.es.delete_by_query(index=index.value, body=delete_module_query, conflicts='proceed')

    def delete_from_indices(self, module: dict):
        for index in ESIndices:
            self.delete_from_index(index, module)

    def index_module(self, index: ESIndices, document: dict) -> dict:
        """ Creates or updates a 'document' in an selcted index.

        Arguments:
            :param index            (ESIndices) Target index to be indexed
            :param document         (dict) Document to index
        """
        # TODO: Remove this IF after reindexing and unification of both indices
        if index == ESIndices.MODULES:
            try:
                name = document['name']
                del document['name']
                document['module'] = name
            except KeyError:
                pass

        return self.es.index(index=index.value, body=document, request_timeout=40)

    def match_all(self, index: ESIndices) -> dict:
        """ Return the dictionary of all modules that are in the index.

        Argument:
            :param index    (ESIndices) Index in which to search
        """
        def _store_hits(hits: list, all_results: dict):
            for hit in hits:
                new_path = '/var/yang/all_modules/{}@{}.yang'.format(hit['_source']['module'], hit['_source']['revision'])
                if not os.path.exists(new_path):
                    print('{} does not exists'.format(new_path))                
                name = ''
                try:
                    name = hit['_source']['name']
                except KeyError:
                    name = hit['_source']['module']

                mod = {
                    'name': name,
                    'revision': hit['_source']['revision'],
                    'organization': hit['_source']['organization']
                }
                key = '{}@{}/{}'.format(mod.get('name'), mod.get('revision'), mod.get('organization'))
                if key not in all_results:
                    all_results[key] = mod

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

    def get_module_by_name_revision(self, index: ESIndices, module: dict) -> list:
        get_module_query = self._get_name_revision_query(index, module)

        es_result = self.es.search(index=index.value, body=get_module_query)

        return es_result['hits']['hits']

    def get_sorted_module_revisions(self, index: ESIndices, name: str):
        query_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/sorted_name_rev_query.json')
        with open(query_path, encoding='utf-8') as reader:
            sorted_name_rev_query = json.load(reader)

        # TODO: Remove this IF after reindexing and unification of both indices
        if index == ESIndices.MODULES:
            del sorted_name_rev_query['query']['bool']['must'][0]['match_phrase']['name.keyword']
            sorted_name_rev_query['query']['bool']['must'][0]['match_phrase'] = {
                'module.keyword': {
                    'query': name
                }
            }
        else:
            sorted_name_rev_query['query']['bool']['must'][0]['match_phrase']['name.keyword']['query'] = name

        try:
            es_result = self.es.search(index=index.value, body=sorted_name_rev_query)
        except RequestError:
            return []

        return es_result['hits']['hits']

    def document_exists(self, index: ESIndices, module: dict) -> bool:
        """ Check whether 'module' already exists in index - if count is greater than 0.

        Arguments:
            :param index        (ESIndices) Index in which to search
            :param module       (dict) Document to search
        """
        get_module_query = self._get_name_revision_query(index, module)

        es_count = self.es.count(index=index.value, body=get_module_query)

        return es_count['count'] > 0

    ### SNAPSOTS RELATED METHODS ###

    def create_snapshot_repository(self, compress: bool) -> dict:
        """ Register a snapshot repository."""
        body = {
            'type': 'fs',
            'settings': {
                'location': self.elk_repo_name,
                'compress': compress
            }
        }
        return self.es.snapshot.create_repository(repository=self.elk_repo_name, body=body)

    def create_snapshot(self, snapshot_name: str) -> dict:
        """ Creates a snapshot with given 'snapshot_name' in a snapshot repository.

        Argument:
            :param snapshot_name    (str) Name of the snapshot to be created
        """
        index_body = {
            'indices': '_all'
        }
        return self.es.snapshot.create(repository=self.elk_repo_name, snapshot=snapshot_name, body=index_body)

    def get_sorted_snapshots(self) -> list:
        """ Return a sorted list of existing snapshots. """
        snapshots = self.es.snapshot.get(repository=self.elk_repo_name, snapshot='_all')['snapshots']
        return sorted(snapshots, key=itemgetter('start_time_in_millis'))

    def restore_snapshot(self, snapshot_name: str) -> dict:
        """ Restore snapshot which is given by 'snapshot_name'.

        Argument:
            :param snapshot_name    (str) Name of the snapshot to restore
        """
        index_body = {
            'indices': '_all'
        }
        return self.es.snapshot.restore(repository=self.elk_repo_name, snapshot=snapshot_name, body=index_body)

    def delete_snapshot(self, snapshot_name: str) -> dict:
        """ Delete snapshot which is given by 'snapshot_name'.

        Argument:
            :param snapshot_name    (str) Name of the snapshot to delete
        """
        return self.es.snapshot.delete(repository=self.elk_repo_name, snapshot=snapshot_name)

    ### HELPER METHODS ###

    def _get_name_revision_query(self, index: ESIndices, module: dict) -> dict:
        module_search_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/module_search.json')
        with open(module_search_path, encoding='utf-8') as reader:
            name_revision_query = json.load(reader)

        # TODO: Remove this IF after reindexing and unification of both indices
        if index == ESIndices.MODULES:
            del name_revision_query['query']['bool']['must'][0]['match_phrase']['name.keyword']
            name_revision_query['query']['bool']['must'][0]['match_phrase'] = {
                'module.keyword': {
                    'query': module['name']
                }
            }
        else:
            name_revision_query['query']['bool']['must'][0]['match_phrase']['name.keyword']['query'] = module['name']
        name_revision_query['query']['bool']['must'][1]['match_phrase']['revision']['query'] = module['revision']

        return name_revision_query
