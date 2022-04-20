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

"""
This script contains functionality,
which re-index Elasticsearch indices
after ES update from version 6.8 to
version 7.10 (done in April 2022).
"""
import os

from elasticsearch import Elasticsearch
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from utility.create_config import create_config


def _store_hits(hits: list, all_results: dict):
    for hit in hits:
        new_path = '/var/yang/all_modules/{}@{}.yang'.format(hit['_source']['module'], hit['_source']['revision'])
        if not os.path.exists(new_path):
            print(f'{new_path} does not exists')

        module = {
            'name': hit['_source']['module'],
            'revision': hit['_source']['revision'],
            'organization': hit['_source']['organization'],
            'path': new_path
        }
        key = '{}@{}/{}'.format(module.get('name'), module.get('revision'), module.get('organization'))
        if key not in all_results:
            all_results[key] = module


def main():
    config = create_config()
    es_aws = config.get('DB-Section', 'es-aws')
    elk_credentials = config.get('Secrets-Section', 'elk-secret').strip('"').split(' ')

    # ------------------------------------------------------------------------------------------------------------------
    # INIT ES CONNECTION
    # ------------------------------------------------------------------------------------------------------------------
    es_host_config = {
        'host': config.get('DB-Section', 'es-host', fallback='localhost'),
        'port': config.get('DB-Section', 'es-port', fallback='9200')
    }
    if es_aws == 'True':
        es = Elasticsearch(hosts=[es_host_config], http_auth=(elk_credentials[0], elk_credentials[1]), scheme='https')
    else:
        es = Elasticsearch(hosts=[es_host_config])
    # ------------------------------------------------------------------------------------------------------------------
    # INIT ALL INDICES
    # ------------------------------------------------------------------------------------------------------------------
    es_manager = ESManager()
    for index in ESIndices:
        if not es_manager.index_exists(index):
            create_result = es_manager.create_index(index)
            print(create_result)
    # ------------------------------------------------------------------------------------------------------------------
    # GET ALL MODULES FROM 'modules' INDEX
    # ------------------------------------------------------------------------------------------------------------------
    all_results = {}
    match_all_query = {
        'query': {
            'match_all': {}
        }
    }

    total_index_docs = 0
    es_result = es.search(index=ESIndices.MODULES.value, body=match_all_query, scroll=u'10s', size=250)
    scroll_id = es_result.get('_scroll_id')
    hits = es_result['hits']['hits']
    _store_hits(hits, all_results)
    total_index_docs += len(hits)

    while len(es_result['hits']['hits']):
        es_result = es.scroll(scroll_id=scroll_id, scroll=u'10s')
        scroll_id = es_result.get('_scroll_id')
        hits = es_result['hits']['hits']
        _store_hits(hits, all_results)
        total_index_docs += len(hits)

    es.clear_scroll(scroll_id=scroll_id, ignore=(404, ))
    print('Total number of modules retreived from "modules" index: {}'.format(total_index_docs))
    # ------------------------------------------------------------------------------------------------------------------
    # FILL 'autocomplete' INDEX
    # ------------------------------------------------------------------------------------------------------------------
    for query in all_results.values():
        es_manager.delete_from_index(ESIndices.AUTOCOMPLETE, query)
        index_result = es_manager.index_module(ESIndices.AUTOCOMPLETE, query)
        if index_result['result'] != 'created':
            print(index_result)


if __name__ == '__main__':
    main()
