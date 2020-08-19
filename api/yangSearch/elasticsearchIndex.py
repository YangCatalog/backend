# Copyright The IETF Trust 2019, All Rights Reserved
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
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan, ScanError

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


def do_search(opts, host, port, es_aws, elk_credentials, LOGGER):
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

    if es_aws:
        es = Elasticsearch(host, http_auth=(elk_credentials[0], elk_credentials[1]))
    else:
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
    request_number = 1
    if 'request-number' in opts:
        request_number = opts['request-number']
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
    limit_reacher = LimitReacher()
    search = scan(es, LOGGER, limit_reacher, query, scroll=u'2m', scroll_limit=2*request_number, index='yindex', doc_type='modules')
    LOGGER.info(search)

    filter_list = __node_data.keys()
    results = []
    rows = search

    if 'filter' in opts and 'node' in opts['filter']:
        filter_list = opts['filter']['node']
    LOGGER.info('filter list:   {}'.format(filter_list))
    latest_revisions = {}

    all_revisions = True
    if 'latest-revisions' in opts and opts['latest-revisions'] is True:
        all_revisions = False
        aggregations = es.search(index='yindex', doc_type='modules', body=query, size=0)['aggregations']['groupby']['buckets']
        for agg in aggregations:
            latest_revisions[agg['key']] = agg['latest-revision']['value_as_string'].split('T')[0]
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
    return (results, limit_reacher.limit_reached)


def scan(client, LOGGER, limit_reacher, query=None, scroll='5m', raise_on_error=True,
         preserve_order=False, size=10000, request_timeout=None, clear_scroll=True,
         scroll_limit=2, scroll_kwargs=None, **kwargs):
    """
    Simple abstraction on top of the
    :meth:`~elasticsearch.Elasticsearch.scroll` api - a simple iterator that
    yields all hits as returned by underlining scroll requests.

    By default scan does not return results in any pre-determined order. To
    have a standard order in the returned documents (either by score or
    explicit sort definition) when scrolling, use ``preserve_order=True``. This
    may be an expensive operation and will negate the performance benefits of
    using ``scan``.

    :arg client: instance of :class:`~elasticsearch.Elasticsearch` to use
    :arg query: body for the :meth:`~elasticsearch.Elasticsearch.search` api
    :arg scroll: Specify how long a consistent view of the index should be
        maintained for scrolled search
    :arg raise_on_error: raises an exception (``ScanError``) if an error is
        encountered (some shards fail to execute). By default we raise.
    :arg preserve_order: don't set the ``search_type`` to ``scan`` - this will
        cause the scroll to paginate with preserving the order. Note that this
        can be an extremely expensive operation and can easily lead to
        unpredictable results, use with caution.
    :arg size: size (per shard) of the batch send at each iteration.
    :arg request_timeout: explicit timeout for each call to ``scan``
    :arg clear_scroll: explicitly calls delete on the scroll id via the clear
        scroll API at the end of the method on completion or error, defaults
        to true.
    :arg scroll_kwargs: additional kwargs to be passed to
        :meth:`~elasticsearch.Elasticsearch.scroll`

    Any additional keyword arguments will be passed to the initial
    :meth:`~elasticsearch.Elasticsearch.search` call::

        scan(es,
            query={"query": {"match": {"title": "python"}}},
            index="orders-*",
            doc_type="books"
        )

    """
    scroll_kwargs = scroll_kwargs or {}

    if not preserve_order:
        query = query.copy() if query else {}
        query["sort"] = "_doc"
    # initial search
    resp = client.search(body=query, scroll=scroll, size=size,
                         request_timeout=request_timeout, **kwargs)

    scroll_id = resp.get('_scroll_id')
    if scroll_id is None:
        return

    try:
        limit = 0
        first_run = True
        yeald_limit = scroll_limit - 2
        while True:
            limit += 1
            # if we didn't set search_type to scan initial search contains data
            if first_run:
                first_run = False
            else:
                resp = client.scroll(scroll_id, scroll=scroll,
                                     request_timeout=request_timeout,
                                     **scroll_kwargs)

            if limit > yeald_limit:
                for hit in resp['hits']['hits']:
                    yield hit

            # check if we have any errrors
            if resp["_shards"]["successful"] < resp["_shards"]["total"]:
                LOGGER.warning(
                    'Scroll request has only succeeded on %d shards out of %d.',
                    resp['_shards']['successful'], resp['_shards']['total']
                )
                if raise_on_error:
                    raise ScanError(
                        scroll_id,
                        'Scroll request has only succeeded on %d shards out of %d.' %
                        (resp['_shards']['successful'], resp['_shards']['total'])
                    )

            scroll_id = resp.get('_scroll_id')
            # end of scroll
            if scroll_id is None or not resp['hits']['hits']:
                limit_reacher.limit_reached = True
                break
            if scroll_limit == limit:
                break
    finally:
        if scroll_id and clear_scroll:
            client.clear_scroll(body={'scroll_id': [scroll_id]}, ignore=(404, ))


class LimitReacher():

    def __init__(self):
        self.limit_reached = False


