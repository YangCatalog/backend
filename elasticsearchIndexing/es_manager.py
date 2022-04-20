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
