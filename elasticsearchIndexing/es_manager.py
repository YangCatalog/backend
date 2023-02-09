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
import typing as t
from configparser import ConfigParser

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import AuthorizationException, NotFoundError, RequestError
from elasticsearch.helpers import parallel_bulk

import utility.log as log
from elasticsearchIndexing.models.es_indices import ESIndices
from elasticsearchIndexing.models.keywords_names import KeywordsNames
from utility.create_config import create_config


class ESManager:
    def __init__(self, es: t.Optional[Elasticsearch] = None):
        config = create_config()
        self.threads = int(config.get('General-Section', 'threads'))
        log_directory = config.get('Directory-Section', 'logs')
        self.elk_repo_name = config.get('General-Section', 'elk-repo-name')
        self.elk_request_timeout = int(config.get('General-Section', 'elk-request-timeout', fallback=60))
        self._setup_elasticsearch(config, es)
        log_file_path = os.path.join(log_directory, 'jobs', 'es-manager.log')
        self.logger = log.get_logger('es-manager', log_file_path)

    def _setup_elasticsearch(self, config: ConfigParser, es: t.Optional[Elasticsearch] = None):
        if es:
            self.es = es
            return
        es_aws = config.get('DB-Section', 'es-aws')
        elk_credentials = config.get('Secrets-Section', 'elk-secret').strip('"').split(' ')
        es_host_config = {
            'host': config.get('DB-Section', 'es-host', fallback='localhost'),
            'port': config.get('DB-Section', 'es-port', fallback='9200'),
        }
        if es_aws == 'True':
            self.es = Elasticsearch(
                hosts=[es_host_config],
                http_auth=(elk_credentials[0], elk_credentials[1]),
                scheme='https',
            )
            return
        self.es = Elasticsearch(hosts=[es_host_config])

    def ping(self) -> bool:
        return self.es.ping()

    def cluster_health(self) -> dict:
        """Returns a brief representation of the cluster health"""
        return self.es.cluster.health()

    def create_index(self, index: ESIndices):
        """
        Create Elasticsearch index with given name.

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
            self.logger.exception('Problem with index creation')
            read_only_query = {'index': {'blocks': {'read_only_allow_delete': 'false'}}}
            self.es.indices.put_settings(index=index_name, body=read_only_query)
            create_result = self.es.indices.create(index=index_name, body=index_config, ignore=400)
        return create_result

    def index_exists(self, index: ESIndices) -> bool:
        """
        Check if the index already exists.

        Argument:
            :param index   (ESIndices) Index to be checked
        """
        name = index.value
        return self.es.indices.exists(name) or self.es.indices.exists_alias(name)

    def get_indices(self) -> list:
        """Returns a list of existing indices."""
        return list(self.es.indices.get_alias().keys())

    def put_index_mapping(self, index: ESIndices, body: dict) -> dict:
        """
        Update mapping for provided index.

        Arguments:
            :param index    (ESIndices) Index whose mapping to update
            :param body     (dict) Mapping definition
        """
        return self.es.indices.put_mapping(index=index.value, body=body, ignore=403)

    def get_index_mapping(self, index: ESIndices) -> dict:
        """
        Get mapping for provided index.

        Argument:
            :param index    (ESIndices) Index whose mapping to get
        """
        mapping = {}
        try:
            mapping = self.es.indices.get_mapping(index=index.value)
        except NotFoundError:
            self.logger.exception('Index not found')
        return mapping

    def get_documents_count(self, index: ESIndices) -> int:
        """
        Get number of documents stored in provided index.

        Argument:
            :param index        (ESIndices) Index in which to search
        """
        count = 0
        try:
            count = self.es.count(index=index.value)['count']
        except NotFoundError:
            self.logger.exception('Index not found')
        return count

    def autocomplete(self, index: ESIndices, keyword: KeywordsNames, searched_term: str) -> list:
        """
        Get list of the modules which will be returned as autocomplete after entering the 'searched_term' by the user.

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
        """
        Delete module from the index.

        Arguments:
            :param index        (ESIndices) Target index from which to delete module
            :param module     (dict) Document to delete
        """
        self.logger.info(f'Deleting module: "{module}" from index: "{index}"')
        delete_module_query = self._get_name_revision_query(index, module)
        return self.es.delete_by_query(index=index.value, body=delete_module_query, conflicts='proceed')

    def delete_from_indices(self, module: dict):
        for index in ESIndices:
            self.delete_from_index(index, module)

    def index_module(self, index: ESIndices, document: dict) -> dict:
        """
        Creates or updates a 'document' in a selected index.

        Arguments:
            :param index            (ESIndices) Target index to be indexed
            :param document         (dict) Document to index
        """
        # TODO: Remove this IF after reindexing and unification of both indices
        if index in [ESIndices.MODULES, ESIndices.YINDEX]:
            try:
                document['module'] = document.pop('name')
            except KeyError:
                pass

        return self.es.index(index=index.value, body=document, request_timeout=self.elk_request_timeout)

    def bulk_modules(self, index: ESIndices, chunk):
        for success, info in parallel_bulk(
            client=self.es,
            actions=chunk,
            index=index.value,
            thread_count=self.threads,
            request_timeout=self.elk_request_timeout,
        ):
            if not success:
                self.logger.error(f'Elasticsearch document failed with info: {info}')

    def match_all(self, index: ESIndices) -> dict:
        """
        Return the dictionary of all modules that are in the index.

        Argument:
            :param index    (ESIndices) Index in which to search
        """

        def _store_hits(hits: list, all_results: dict):
            for hit in hits:
                name = ''
                revision = hit['_source']['revision']
                organization = hit['_source']['organization']
                try:
                    name = hit['_source']['name']
                except KeyError:
                    name = hit['_source']['module']
                new_path = f'/var/yang/all_modules/{name}@{revision}.yang'
                if not os.path.exists(new_path):
                    self.logger.error(f'{new_path} does not exists')

                key = f'{name}@{revision}/{organization}'
                if key not in all_results:
                    all_results[key] = hit['_source']

        all_results = {}
        match_all_query = {'query': {'match_all': {}}}
        total_index_docs = 0
        es_result = self.es.search(index=index.value, body=match_all_query, scroll=u'1m', size=250)
        scroll_id = es_result.get('_scroll_id')
        hits = es_result['hits']['hits']
        _store_hits(hits, all_results)
        total_index_docs += len(hits)

        while es_result['hits']['hits']:
            es_result = self.scroll(scroll_id)

            scroll_id = es_result.get('_scroll_id')
            hits = es_result['hits']['hits']
            _store_hits(hits, all_results)
            total_index_docs += len(hits)

        self.clear_scroll(scroll_id)
        return all_results

    def get_module_by_name_revision(self, index: ESIndices, module: dict) -> list:
        get_module_query = self._get_name_revision_query(index, module)

        es_result = self.es.search(index=index.value, body=get_module_query, size=1000)

        return es_result['hits']['hits']

    def get_sorted_module_revisions(self, index: ESIndices, name: str):
        query_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/sorted_name_rev_query.json')
        with open(query_path, encoding='utf-8') as reader:
            sorted_name_rev_query = json.load(reader)

        # TODO: Remove this IF after reindexing and unification of both indices
        if index in [ESIndices.MODULES, ESIndices.YINDEX]:
            del sorted_name_rev_query['query']['bool']['must'][0]['match_phrase']['name.keyword']
            sorted_name_rev_query['query']['bool']['must'][0]['match_phrase'] = {'module.keyword': {'query': name}}
        else:
            sorted_name_rev_query['query']['bool']['must'][0]['match_phrase']['name.keyword']['query'] = name

        try:
            es_result = self.es.search(index=index.value, body=sorted_name_rev_query)
        except RequestError:
            return []

        return es_result['hits']['hits']

    def get_node(self, module: dict) -> dict:
        query_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/show_node.json')
        with open(query_path, encoding='utf-8') as reader:
            show_node_query = json.load(reader)

        show_node_query['query']['bool']['must'][0]['match_phrase']['module.keyword']['query'] = module['name']
        show_node_query['query']['bool']['must'][1]['match_phrase']['path']['query'] = module['path']
        show_node_query['query']['bool']['must'][2]['match_phrase']['revision']['query'] = module['revision']
        hits = self.es.search(index=ESIndices.YINDEX.value, body=show_node_query)

        return hits

    def generic_search(
        self,
        index: t.Union[ESIndices, str],
        query: dict,
        response_size: t.Optional[int] = 0,
        use_scroll: bool = False,
    ):
        index = index if isinstance(index, str) else index.value
        if use_scroll:
            return self.es.search(
                index=index,
                body=query,
                request_timeout=self.elk_request_timeout,
                scroll=u'10m',
                size=response_size,
            )
        return self.es.search(index=index, body=query, request_timeout=self.elk_request_timeout, size=response_size)

    def clear_scroll(self, scroll_id: str):
        return self.es.clear_scroll(scroll_id=scroll_id, ignore=(404,))

    def scroll(self, scroll_id: str):
        return self.es.scroll(scroll_id=scroll_id, scroll=u'10m', request_timeout=self.elk_request_timeout)

    def document_exists(self, index: ESIndices, module: dict) -> bool:
        """
        Check whether 'module' already exists in index - if count is greater than 0.

        Arguments:
            :param index        (ESIndices) Index in which to search
            :param module       (dict) Document to search
        """
        if index == ESIndices.DRAFTS:
            get_query = self._get_draft_query(index, module)
        else:
            get_query = self._get_name_revision_query(index, module)

        try:
            es_count = self.es.count(index=index.value, body=get_query)
        except RequestError:
            return False

        return es_count['count'] > 0

    def _get_name_revision_query(self, index: ESIndices, module: dict) -> dict:
        module_search_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/module_search.json')
        with open(module_search_path, encoding='utf-8') as reader:
            name_revision_query = json.load(reader)

        # TODO: Remove this IF after reindexing and unification of both indices
        if index in [ESIndices.MODULES, ESIndices.YINDEX]:
            del name_revision_query['query']['bool']['must'][0]['match_phrase']['name.keyword']
            name_revision_query['query']['bool']['must'][0]['match_phrase'] = {
                'module.keyword': {'query': module['name']},
            }
        else:
            name_revision_query['query']['bool']['must'][0]['match_phrase']['name.keyword']['query'] = module['name']
        name_revision_query['query']['bool']['must'][1]['match_phrase']['revision']['query'] = module['revision']

        return name_revision_query

    def _get_draft_query(self, index: ESIndices, draft: dict) -> dict:
        draft_search_path = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json/draft_search.json')
        with open(draft_search_path, encoding='utf-8') as reader:
            draft_query = json.load(reader)

        draft_query['query']['bool']['must'][0]['match_phrase']['draft']['query'] = draft['draft']
        return draft_query
