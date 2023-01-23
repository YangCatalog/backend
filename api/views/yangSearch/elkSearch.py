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

from elasticsearch import ConnectionTimeout

from api.views.yangSearch.response_row import ResponseRow
from api.views.yangSearch.search_params import SearchParams
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from redisConnections.redisConnection import RedisConnection
from utility import log
from utility.staticVariables import OUTPUT_COLUMNS

RESPONSE_SIZE = 2000
RESERVED_CHARACTERS = ['"', '<']


class ElkSearch:
    """
    Serves distinctly for yangcatalog search. This class will create a query that is sent to elasticsearch
    which returns output that needs to be processed. We process this into a list which is displayed as rows
    in a grid of yangcatalog search.
    """

    def __init__(
        self,
        searched_term: str,
        logs_dir: str,
        es_manager: ESManager,
        redis_connection: RedisConnection,
        search_params: SearchParams,
    ) -> None:
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
            self.query: dict = json.load(reader)
        self._searched_term = searched_term
        self._es_manager = es_manager
        self._redis_connection = redis_connection
        self._latest_revisions = {}
        self._remove_columns = list(set(OUTPUT_COLUMNS) - set(self._search_params.output_columns))
        self._row_hashes = []
        self._missing_modules = []
        self.timeout = False
        log_file_path = os.path.join(logs_dir, 'yang.log')
        self.logger = log.get_logger('yc-elasticsearch', log_file_path)

    def alerts(self):
        """
        Process and return all alerts to user. At the moment it is processing only missing modules
        :return: missing modules from redis
        """
        alerts = []
        for missing in self._missing_modules:
            alerts.append(f'Module {missing} metadata does not exist in yangcatalog')
        return alerts

    def construct_query(self):
        """
        Create a json query that is then sent to Elasticsearch.
        Changes being made while creating query:
        - statement is a list of schema types. It is one or more or all of ['typedef', 'grouping', 'feature',
        'identity', 'extension', 'rpc', 'container', 'list', 'leaf-list', 'leaf', 'notification', 'action']
        - In the case of the module and argument name, either a term or regexp query is constructed.
        - In the case of the description field, if the query_type wasn't set to 'regexp', we run a full text search.
        - Case sensitivity is controlled by the case_sensitive search parameter.
        - Synonyms in the full text search of description can be toggled with the use_synonyms search param.
        - aggs (or aggregations) are used to find th the latest revisions of a module if we are searching for latest
        revisions only.
        See search.json for the full query format.
        """
        self.logger.debug(f'Constructing query for params {self._search_params}')
        self.query['query']['bool']['must'][0]['terms']['statement'] = self._search_params.schema_types
        if not self._search_params.include_drafts:
            self.query['query']['bool']['must'].append({'term': {'rfc': True}})
        case_insensitive = not self._search_params.case_sensitive
        query_type = self._search_params.query_type
        if query_type == 'regexp':
            self._searched_term = _escape_reserved_characters(self._searched_term)
        searched_term = self._searched_term
        should_query: list = self.query['query']['bool']['should']
        for searched_field in self._search_params.searched_fields:
            if searched_field == 'module':
                should_query.append(
                    {query_type: {'module': {'value': searched_term, 'case_insensitive': case_insensitive}}},
                )
            elif searched_field == 'argument':
                should_query.append(
                    {query_type: {'argument': {'value': searched_term, 'case_insensitive': case_insensitive}}},
                )
            elif searched_field == 'description':
                if query_type == 'regexp':
                    should_query.append(
                        {
                            'regexp': {
                                'description.keyword': {
                                    'value': f'.*{searched_term}.*',
                                    'case_insensitive': case_insensitive,
                                },
                            },
                        },
                    )
                else:
                    analyzer = 'description'
                    if case_insensitive:
                        analyzer += '_lowercase'
                    if self._search_params.use_synonyms:
                        analyzer += '_synonym'
                    field = 'description'
                    if case_insensitive:
                        field += '.lowercase'
                    should_query.extend(
                        [
                            {
                                'match': {
                                    field: {
                                        'query': searched_term,
                                        'analyzer': analyzer,
                                        'minimum_should_match': '4<80%',
                                    },
                                },
                            },
                            {
                                # boost results that contain the words in the same order
                                'match_phrase': {field: {'query': searched_term, 'analyzer': analyzer, 'boost': 2}},
                            },
                        ],
                    )

    def search(self) -> tuple[list[dict], bool]:
        """
        Search using the query we've constructed.

        :return list of rows containing dictionary that is filled with output for each column for yangcatalog search
        """
        self.logger.debug('Running search')
        hits: list = self._retrieve_results(self._search_params.latest_revision)
        processed_rows = self._process_hits(hits)
        return processed_rows, len(hits) == RESPONSE_SIZE

    def _retrieve_results(self, latest_revisions: bool) -> list[dict]:
        query = self.query.copy()
        if not latest_revisions:
            query.pop('aggs')
        try:
            response = self._es_manager.generic_search(
                ESIndices.YINDEX,
                query,
                response_size=RESPONSE_SIZE,
            )
        except ConnectionTimeout:
            self.logger.exception('Error while searching in Elasticsearch')
            self.timeout = True
            return []
        hits = response['hits']['hits']
        self.logger.debug(f'search complete with {len(hits)} hits')
        if latest_revisions:
            aggregations = response['aggregations']['groupby']['buckets']
            for agg in aggregations:
                self._latest_revisions[agg['key']] = agg['latest-revision']['value_as_string'].split('T')[0]
        return hits

    def _process_hits(self, hits: list) -> list[dict]:
        response_rows: list[dict] = []
        reject: list[str] = []
        for hit in hits:
            row = ResponseRow(elastic_hit=hit['_source'])
            module_key = f'{row.module_name}@{row.revision}/{row.organization}'
            if module_key in reject:
                continue

            module_latest_revision = self._latest_revisions.get(row.module_name, '').replace('02-29', '02-28')
            if self._search_params.latest_revision and row.revision != module_latest_revision:
                reject.append(module_key)
                continue

            module_data = self._redis_connection.get_module(module_key)
            module_data = json.loads(module_data)
            if not module_data:
                self.logger.error(f'Failed to get module from Redis, but found in Elasticsearch: {module_key}')
                reject.append(module_key)
                self._missing_modules.append(module_key)
                continue
            row.maturity = row.maturity if row.maturity else module_data.get('maturity-level', '')
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
                    self.logger.info(
                        f'Trimmed output row {row.output_row} already exists in response rows - cutting this one out',
                    )
                    continue
                self._row_hashes.append(row_hash)
            response_rows.append(row.output_row)

        self.logger.debug(f'ElkSearch finished with length {len(response_rows)}')
        return response_rows

    def _rejects_mibs_or_versions(self, module_key: str, reject: t.List[str], module_data: dict) -> bool:
        if not self._search_params.include_mibs and 'yang:smiv2:' in module_data.get('namespace', ''):
            reject.append(module_key)
            return True
        if module_data.get('yang-version') not in self._search_params.yang_versions:
            reject.append(module_key)
            return True
        return False


def _escape_reserved_characters(term: str) -> str:
    """If the number of double quotes is odd, the sequence is not closed, so escaping characters is needed."""
    for char in RESERVED_CHARACTERS:
        if term.count(char) % 2 == 1:
            term = term.replace(char, f'\\{char}')
    return term
