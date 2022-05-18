# Copyright The IETF Trust 2021, All Rights Reserved
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

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import json
import os
import typing as t

import gevent
import gevent.queue
from api.views.yangSearch.response_row import ResponseRow
from api.views.yangSearch.search_params import SearchParams
from elasticsearch import ConnectionTimeout
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from redisConnections.redisConnection import RedisConnection
from utility import log
from utility.staticVariables import OUTPUT_COLUMNS

RESPONSE_SIZE = 2000


class ElkSearch:
    """
    Serves distinctly for yangcatalog search. This class will create a query that is sent to elasticsearch
    which returns output that needs to be processed. We process this into a list which is displayed as rows
    in a grid of yangcatalog search.
    """

    def __init__(self, searched_term: str, logs_dir: str, es_manager: ESManager, redis_connection: RedisConnection,
                 search_params: SearchParams) -> None:
        """
        Initialization of search under Elasticsearch engine. We need to prepare a query
        that will be used to search in Elasticsearch.

        Arguments:
            :param searched_term    (str) String that we are searching for
            :param logs_dir         (str) Directory to log files
            :param es_manager       (ESManager) Elasticsearch manager
            :param redis_connection (RedisConnection) Redis connection to modules db (db=1)
            :param search_params    (SearchParams) Contains search parameters
        """
        self._search_params = search_params
        search_query_path = os.path.join(os.environ['BACKEND'], 'api/views/yangSearch/json/search.json')
        with open(search_query_path, encoding='utf-8') as reader:
            self.query = json.load(reader)
        self._searched_term = searched_term
        self._es_manager = es_manager
        self._redis_connection = redis_connection
        self._current_scroll_id = None
        self._latest_revisions = {}
        self._remove_columns = list(set(OUTPUT_COLUMNS) - set(self._search_params.output_columns))
        self._row_hashes = []
        self._missing_modules = []
        log_file_path = os.path.join(logs_dir, 'yang.log')
        self.LOGGER = log.get_logger('yc-elasticsearch', log_file_path)

    def alerts(self):
        """
        Process and return all alerts to user. At the moment it is processing only missing modules
        :return: missing modules from redis
        """
        alerts = []
        for missing in self._missing_modules:
            alerts.append('Module {} metadata does not exist in yangcatalog'.format(missing))
        return alerts

    def construct_query(self):
        """
        Create a json query that is then sent to Elasticsearch.
        Changes being made while creating query:
        - statement is a list of schema types. It is one or more or all of ['typedef', 'grouping', 'feature',
        'identity', 'extension', 'rpc', 'container', 'list', 'leaf-list', 'leaf', 'notification', 'action']
        - Under query -> bool -> must -> bool -> should -> are 3 different bool -> must -> which can contain
        either term if we are searching specific text or regex if we are searching for regular expression
        - The 3 different bools mentioned above are constructed dynamicaly, while at least one must exist and
        all three may exist
        - lowercase may be changed with sensitive giving us an option to search for case sensitive text. If we
        use lowercase everything will be automatically put to lowercase and so we don't care about case sensitivity.
        - aggs (or aggregations) are used to find latest revisions of a module if we are searching for latest
        revisions only.
        This query looks as follows:
        {
          "query": {
            "bool": {
              "must": [
                "terms": {
                  "statement": ["leaf", "container"]
                },
                {
                  "bool": {
                    "should": [
                      "term": {
                        "module": "foo"
                      },
                      "term": {
                        "argument.lowercase": "foo"
                      },
                      "term": {
                        "description.lowercase": "foo"
                      }
                    ]
                  }
                }
              ]
            }
          },
          "aggs": {
            "groupby": {
              "terms": {
                "field": "module.keyword",
                "size": 2000
              },
              "aggs": {
                "latest-revision": {
                  "max": {
                    "field": "revision"
                  }
                }
              }
            }
          }
        }
        """
        self.query['query']['bool']['must'][0]['terms']['statement'] = self._search_params.schema_types
        sensitive = 'lowercase'
        if self._search_params.case_sensitive:
            sensitive = 'sensitive'
        else:
            self._searched_term = self._searched_term.lower()
        search_in = self.query['query']['bool']['must'][1]['bool']['should']
        for searched_field in self._search_params.searched_fields:
            should_query = {
                self._search_params.query_type: {}
            }
            if searched_field == 'module':
                should_query[self._search_params.query_type][searched_field] = self._searched_term
            else:
                should_query[self._search_params.query_type][
                    '{}.{}'.format(searched_field, sensitive)] = self._searched_term
            search_in.append(should_query)
        self.LOGGER.debug('Constructed query:\n{}'.format(self.query))

    def search(self):
        """
        Search using query produced. This search is done in parallel. We are making two searches at the same time.
        One search is being done as a scroll search. Elastic search does not allow us to get more then some number
        of results per search. If we want to search through all the results we have to use scroll but this does not
        give us an output of aggregations. That is why we have to create second normal search where we don t care about
        finding of search but we get only get aggregations from response. These two searches may run in parallel.

        Next we have to process the given response in self._process_hits definition. And while processing it we can
        use scroll search to get next batch of result from search to process if it will be needed.

        :return list of rows containing dictionary that is filled with output for each column for yangcatalog search
        """
        hits = gevent.queue.JoinableQueue()
        process_first_search = gevent.spawn(self._first_scroll, hits)

        self.LOGGER.debug('Running first search in parallel')
        if self._search_params.latest_revision:
            self.LOGGER.debug('Processing aggregations search in parallel')
            self._resolve_aggregations()
            self.LOGGER.debug('Aggregations processed joining the search')
        process_first_search.join()
        hits = hits.get()
        processed_rows = self._process_hits(hits, [])
        if self._current_scroll_id is not None:
            self._es_manager.clear_scroll(self._current_scroll_id)
        return processed_rows, len(hits) == RESPONSE_SIZE

    def _process_hits(self, hits: list, response_rows: list, reject=None):
        if reject is None:
            reject = []
        if not hits:
            return response_rows
        secondary_hits = gevent.queue.JoinableQueue()
        process_scroll_search = gevent.spawn(self._continue_scrolling, secondary_hits)
        for hit in hits:
            row = ResponseRow(elastic_hit=hit['_source'])
            module_key = '{}@{}/{}'.format(row.module_name, row.revision, row.organization)
            if module_key in reject:
                continue

            module_latest_revision = self._latest_revisions.get(row.module_name, '').replace('02-28', '02-29')
            if self._search_params.latest_revision and row.revision != module_latest_revision:
                reject.append(module_key)
                continue

            module_data = self._redis_connection.get_module(module_key)
            module_data = json.loads(module_data)
            if not module_data:
                self.LOGGER.error('Failed to get module from Redis, but found in Elasticsearch: {}'.format(module_key))
                reject.append(module_key)
                self._missing_modules.append(module_key)
                continue
            row.maturity = module_data.get('maturity-level', '')
            row.dependents = len(module_data.get('dependents', []))
            row.compilation_status = module_data.get('compilation-status', 'unknown')
            row.create_representation()

            if self._rejects_mibs_or_versions(module_key, reject, module_data):
                continue

            if not row.meets_subsearch_condition(self._search_params.sub_search):
                continue

            row.create_output(self._remove_columns)
            if self._remove_columns:
                row_hash = row.get_row_hash_by_columns()
                if row_hash in self._row_hashes:
                    self.LOGGER.info(
                        'Trimmed output row {} already exists in response rows - cutting this one out'
                        .format(row.output_row))
                    continue
                self._row_hashes.append(row_hash)
            response_rows.append(row.output_row)
            if len(response_rows) >= RESPONSE_SIZE or self._current_scroll_id is None:
                self.LOGGER.debug('ElkSearch finished with len {} and scroll id {}'
                                  .format(len(response_rows), self._current_scroll_id))
                process_scroll_search.kill()
                return response_rows

        process_scroll_search.join()
        return self._process_hits(secondary_hits.get(), response_rows, reject)

    def _first_scroll(self, hits):
        elk_response = {}
        try:
            query_no_agg = self.query.copy()
            query_no_agg.pop('aggs', '')
            elk_response = self._es_manager.generic_search(ESIndices.YINDEX, query_no_agg,
                                                           response_size=RESPONSE_SIZE, use_scroll=True)
        except ConnectionTimeout:
            self.LOGGER.exception('Failed to connect to Elasticsearch')
            elk_response['hits'] = {'hits': []}
        self.LOGGER.debug('search complete with {} hits'.format(len(elk_response['hits']['hits'])))
        self._current_scroll_id = elk_response.get('_scroll_id')
        hits.put(elk_response['hits']['hits'])

    def _continue_scrolling(self, hits):
        if self._current_scroll_id is None:
            hits.put([])
            return
        elk_response = {}
        try:
            elk_response = self._es_manager.scroll(self._current_scroll_id)
        except ConnectionTimeout:
            self.LOGGER.exception('Failed to connect to Elasticsearch')
            elk_response['hits'] = {'hits': []}
        self._current_scroll_id = elk_response.get('_scroll_id')
        hits.put(elk_response['hits']['hits'])

    def _resolve_aggregations(self):
        response = {'aggregations': {'groupby': {'buckets': []}}}
        try:
            response = self._es_manager.generic_search(ESIndices.YINDEX, self.query)
        except ConnectionTimeout:
            self.LOGGER.exception('Failed to connect to Elasticsearch')
        aggregations = response['aggregations']['groupby']['buckets']
        for agg in aggregations:
            self._latest_revisions[agg['key']] = agg['latest-revision']['value_as_string'].split('T')[0]

    def _rejects_mibs_or_versions(self, module_key: str, reject: t.List[str], module_data: dict) -> bool:
        if not self._search_params.include_mibs and 'yang:smiv2:' in module_data.get('namespace', ''):
            reject.append(module_key)
            return True
        if module_data.get('yang-version') not in self._search_params.yang_versions:
            reject.append(module_key)
            return True
        return False
