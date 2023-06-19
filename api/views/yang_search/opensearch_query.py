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

from opensearchpy import ConnectionTimeout

import api.views.yang_search.search_params as sp
from api.views.yang_search.response_row import ResponseRow
from opensearch_indexing.models.opensearch_indices import OpenSearchIndices
from opensearch_indexing.opensearch_manager import OpenSearchManager
from redisConnections.redisConnection import RedisConnection
from utility import log
from utility.staticVariables import OUTPUT_COLUMNS

RESPONSE_SIZE = 2000
RESERVED_CHARACTERS = ['"', '<']


class OpenSearchQuery:
    """
    Serves distinctly for yangcatalog search. This class will create a query that is sent to OpenSearch
    which returns output that needs to be processed. We process this into a list which is displayed as rows
    in a grid of yangcatalog search.
    """

    def __init__(
        self,
        logs_dir: str,
        opensearch_manager: OpenSearchManager,
        redis_connection: RedisConnection,
        search_params: sp.SearchParams,
    ) -> None:
        """
        Initialization of search under OpenSearch engine. We need to prepare a query
        that will be used to search in OpenSearch.

        Arguments:
            :param searched_term    (str) String that we are searching for
            :param logs_dir         (str) Directory to log files
            :param opensearch_manager       (OpenSearchManager) OpenSearch manager
            :param redis_connection (RedisConnection) Redis connection to modules db (db=1)
            :param search_params    (SearchParams) Contains search parameters
        """
        self._search_params = search_params
        search_query_path = os.path.join(os.environ['BACKEND'], 'api/views/yang_search/json/search.json')
        with open(search_query_path, encoding='utf-8') as reader:
            self.query: dict = json.load(reader)
        self._opensearch_manager = opensearch_manager
        self._redis_connection = redis_connection
        self._latest_revisions = {}
        self._remove_columns = list(set(OUTPUT_COLUMNS) - set(self._search_params.output_columns))
        self._row_hashes = set()
        self._missing_modules = []
        self.timeout = False
        log_file_path = os.path.join(logs_dir, 'yang.log')
        self.logger = log.get_logger('yc-opensearch', log_file_path)
        self._construct_query()

    def alerts(self):
        """
        Process and return all alerts to user. At the moment it is processing only missing modules
        :return: missing modules from redis
        """
        alerts = []
        for missing in self._missing_modules:
            alerts.append(f'Module {missing} metadata does not exist in yangcatalog')
        return alerts

    def _construct_query(self):
        """
        Create a json query that is then sent to OpenSearch.
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
        should_query = self.query['query']['bool']['should']
        must_query = self.query['query']['bool']['must']
        for sub in self._search_params.subqueries:
            if sub.must:
                bool_subquery = must_query
                self.query['query']['bool']['minimum_should_match'] = 0
            else:
                bool_subquery = should_query
            string = sub.string

            selected_query_type = 'regexp' if getattr(sub, 'regex', False) else 'term'
            if selected_query_type == 'regexp':
                string = _escape_reserved_characters(string)

            sub_type = type(sub)
            field = sub.field
            assert sub_type is not sp.Subquery
            if sub_type in (sp.Name, sp.ModuleName):
                bool_subquery.append({selected_query_type: {field: {'value': string}}})
            elif sub_type in (sp.Revision, sp.Organization, sp.Maturity):
                bool_subquery.append({'term': {field: {'value': string}}})
            elif isinstance(sub, sp.Path):
                bool_subquery.append({'wildcard': {'path': {'value': string}}})
            elif isinstance(sub, sp.Description):
                case_insensitive = sub.case_insensitive
                use_synonyms = sub.use_synonyms
                if selected_query_type == 'regexp':
                    bool_subquery.append(
                        {
                            'regexp': {
                                'description.keyword': {
                                    'value': f'.*{string}.*',
                                    'case_insensitive': case_insensitive,
                                },
                            },
                        },
                    )
                else:
                    analyzer = 'description'
                    if case_insensitive:
                        analyzer += '_lowercase'
                    if use_synonyms:
                        analyzer += '_synonym'
                    if case_insensitive:
                        field += '.lowercase'
                    bool_subquery.append(
                        {
                            'match': {
                                field: {
                                    'query': string,
                                    'analyzer': analyzer,
                                    'minimum_should_match': '4<80%',
                                },
                            },
                        },
                    )
                    should_query.append(
                        {
                            # boost results that contain the words in the same order
                            'match_phrase': {field: {'query': string, 'analyzer': analyzer, 'boost': 2}},
                        },
                    )

    def search(self) -> tuple[list[dict], bool]:
        """
        Search using the query we've constructed.

        :return list of rows containing dictionary that is filled with output for each column for yangcatalog search
        """
        self.logger.debug('Running search')
        hits = self._retrieve_results(self._search_params.latest_revision)
        processed_rows = self._process_hits(hits)
        return processed_rows, len(hits) == RESPONSE_SIZE

    def _retrieve_results(self, latest_revisions: bool) -> list[dict]:
        self.logger.debug(f'latest revision: {latest_revisions}')
        query = self.query.copy()
        if not latest_revisions:
            query.pop('aggs')
        try:
            self.logger.debug(json.dumps(query, indent=2))
            response = self._opensearch_manager.generic_search(
                OpenSearchIndices.YINDEX,
                query,
                response_size=RESPONSE_SIZE,
            )
        except ConnectionTimeout:
            self.logger.exception('Error while searching in OpenSearch')
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
        reject: set[str] = set()
        for hit in hits:
            row = ResponseRow(source=hit['_source'])
            module_key = f'{row.module_name}@{row.revision}/{row.organization}'
            if module_key in reject:
                continue

            module_latest_revision = self._latest_revisions.get(row.module_name, '')
            if self._search_params.latest_revision and row.revision != module_latest_revision:
                reject.add(module_key)
                continue

            module_data = self._redis_connection.get_module(module_key)
            module_data = json.loads(module_data)
            if not module_data:
                self.logger.error(f'Failed to get module from Redis, but found in OpenSearch: {module_key}')
                reject.add(module_key)
                self._missing_modules.append(module_key)
                continue
            row.maturity = row.maturity if row.maturity else module_data.get('maturity-level', '')
            row.dependents = len(module_data.get('dependents', []))
            row.compilation_status = module_data.get('compilation-status', 'unknown')
            row.create_representation()

            if self._rejects_mibs_or_versions(module_data):
                reject.add(module_key)
                continue

            row.create_output(self._remove_columns)
            if self._remove_columns:
                row_hash = row.get_row_hash_by_columns()
                if row_hash in self._row_hashes:
                    self.logger.info(
                        f'Trimmed output row {row.output_row} already exists in response rows - cutting this one out',
                    )
                    continue
                self._row_hashes.add(row_hash)
            response_rows.append(row.output_row)

        self.logger.debug(f'OpenSearch finished with length {len(response_rows)}')
        return response_rows

    def _rejects_mibs_or_versions(self, module_data: dict) -> bool:
        if not self._search_params.include_mibs and 'yang:smiv2:' in module_data.get('namespace', ''):
            return True
        if module_data['yang-version'] not in self._search_params.yang_versions:
            return True
        return False


def _escape_reserved_characters(term: str) -> str:
    """If the number of double quotes is odd, the sequence is not closed, so escaping characters is needed."""
    for char in RESERVED_CHARACTERS:
        if term.count(char) % 2 == 1:
            term = term.replace(char, f'\\{char}')
    return term
