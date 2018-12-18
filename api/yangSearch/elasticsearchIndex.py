# Copyright 2018 Cisco and its affiliates
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
__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

from elasticsearch import Elasticsearch

__schema_types = [
    'typedef',
    'grouping',
    'feature',
    'identity',
    'extension',
    'rpc',
    'container',
    'list',
    'leaf-list',
    'leaf',
    'notification',
    'action'
]

__search_fields = [
    'argument',
    'description',
    'module'
]

__node_data = {
    'name': 'argument',
    'description': 'description',
    'path': 'path',
    'type': 'statement'
}


def do_search(opts, host, protocol, port, LOGGER):
    query = \
        {
            'query': {
                'bool': {
                    'must': []
                }
            },
            'aggs': {
                'groupby': {
                    'terms': {
                        'field': 'module.keyword',
                        'size': 10000
                    },
                    'aggs': {
                        'latest-revision': {
                            'max': {
                                'field': 'revision'
                            }
                        }
                    }
                }
            }
        }

    es = Elasticsearch([{'host': '{}'.format(host), 'port': port}])
    search_term = opts['search']

    if 'case-sensitive' in opts and opts['case-sensitive']:
        case_sensitive = 'sensitive'
    else:
        case_sensitive = 'lowercase'
        search_term = search_term.lower()

    #    case_sensitivity = 'BINARY '

    sts = __search_fields
    if 'search-fields' in opts:
        sts = opts['search-fields']

    if 'type' in opts and opts['type'] == 'regex':
        term_regex = 'regexp'
    else:
        term_regex = 'term'

    should = {
        'bool': {'should':[]}
    }
    for field in sts:
        if field in __search_fields:
            if field == 'module':
                field_term = field
                final_term = search_term.lower()
            else:
                field_term = '{}.{}'.format(field, case_sensitive)
                final_term = search_term

            term = {
                term_regex: {
                    field_term: final_term
                }
            }
            should['bool']['should'].append(term)

    queries = []
    if 'schema-types' in opts:
        for st in opts['schema-types']:
            if st in __schema_types:
                queries.append(st)
    must = {
        'terms': {
            'statement': queries
        }
    }
    query['query']['bool']['must'].append(must)
    query['query']['bool']['must'].append(should)
    LOGGER.info('query:  {}'.format(query))

    search = es.search(index='yindex', doc_type='modules', body=query, size=10000, from_=0)
    rows = search['hits']['hits']
    LOGGER.info('Elasticsearch too {} ms to search for data'.format(search['took']))
    aggregations = search['aggregations']['groupby']['buckets']
    results = []
    filter_list = __node_data.keys()
    if 'filter' in opts and 'node' in opts['filter']:
        filter_list = opts['filter']['node']
    LOGGER.info('filter list:   {}'.format(filter_list))
    latest_revisions = {}
    for agg in aggregations:
        latest_revisions[agg['key']] = agg['latest-revision']['value_as_string'].split('T')[0]
    all_revisions = True
    if 'latest-revisions' in opts and opts['latest-revisions'] is True:
        all_revisions = False
    for row in rows:
        r = row['_source']
        if all_revisions or r['revision'] == latest_revisions[r['module']]:
            module = {'name': r['module'], 'revision': r['revision'], 'organization': r['organization']}
            result = {'module': module}
            result['node'] = {}
            for nf in filter_list:
                if nf in __node_data:
                    result['node'][nf] = r[__node_data[nf]]

            results.append(result)
    return results


