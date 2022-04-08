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

import hashlib
import json

import gevent
import gevent.queue
from elasticsearch import ConnectionTimeout, Elasticsearch
from redisConnections.redisConnection import RedisConnection
from utility import log


class ElkSearch:
    """
    Serves distinctly for yangcatalog search. This class will create a query that is sent to elasticsearch
    which returns output that needs to be processed. We process this into a list which is displayed as rows
    in a grid of yangcatalog search.
    """
    # TODO this should end up being in some kind of file since different SDOs may come in future and we dont want to
    # keep changing the code
    SDOS = [
        'ietf',
        'ieee',
        'bbf',
        'odp',
        'mef'
    ]

    def __init__(self, searched_term: str, case_sensitive: bool, searched_fields: list, type: str,
                 schema_types: list, logs_dir: str, es: Elasticsearch, latest_revision: bool,
                 redisConnection: RedisConnection, include_mibs: bool, yang_versions: list, needed_output_colums: list,
                 all_output_columns: list, sub_search: list) -> None:
        """
        Initialization of search under elasticsearch engine. We need to prepare a query
        that will be used to search in elasticsearch.

        :param searched_term:   (str) String that we are searching for
        :param case_sensitive:  (boolean) Whether we want search to be case sensitive or not
        :param searched_fields: (list) Fields under which we are searching (it can be [argument, description, module])
        :param type:            (str) Can be only regex or term
        :param schema_types     (list) In which schema types do we search for (typedef, leaf, leaflist, container, etc.)
        :param logs_dir         (str) Directory to log files
        :param es               (ElasticSearch) Elasticsearch engine
        :param latest_revision  (boolean) Whether we want to search only for latest revision of found modules.
        :param redisConnection  (RedisConnection) Redis connection to modules db (db=1)
        :param include_mibs     (boolean) Whether we want to search for MIBs as well from the searched modules
        :param yang_versions    (list) List of yang version that we search for
        :param needed_output_colums (list) output columns that are going to be used within response json
        :param all_output_columns   (list) all existing output columns so we can get diff which we need to remove
        :param sub_search       (list of dic) search for specific part of text from output received from elasticsearch
        """
        self.__response_size = 2000
        self.query = \
            {
                'query': {
                    'bool': {
                        'must': [{
                            'bool': {
                                'must': {
                                    'terms': {
                                        'statement': schema_types
                                    }
                                }
                            }
                        }, {
                            'bool': {
                                'should': []
                            }
                        }]
                    }
                },
                'aggs': {
                    'groupby': {
                        'terms': {
                            'field': 'module.keyword',
                            'size': self.__response_size
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
        self.__case_sensitive = case_sensitive
        self.__searched_fields = searched_fields
        self.__searched_term = searched_term
        self.__type = type
        self.__es = es
        self.__redisConnection = redisConnection
        self.__latest_revision = latest_revision
        self.__include_mibs = include_mibs
        self.__yang_versions = yang_versions
        self.__sub_search = sub_search
        self.__current_scroll_id = None
        self.__latest_revisions = {}
        self.__output_columns = needed_output_colums
        self.__remove_columns = list(set(all_output_columns) - set(needed_output_colums))
        self.__row_hashes = []
        self.__missing_modules = []
        self.LOGGER = log.get_logger('yc-elasticsearch', '{}/yang.log'.format(logs_dir))

    def alerts(self):
        """
        Process and return all alerts to user. At the moment it is processing only missing modules
        :return: missing modules from redis
        """
        alerts = []
        for missing in self.__missing_modules:
            alerts.append('Module {} metadata does not exist in yangcatalog'.format(missing))
        return alerts

    def construct_query(self):
        """
        Create a json query that is then sent to elasticsearch. This query looks as follows
        Changes being made while creating query:
        - statement is a list of schema types. It is one or more or all of ['typedef', 'grouping', 'feature',
        'identity', 'extension', 'rpc', 'container', 'list', 'leaf-list', 'leaf', 'notification', 'action']
        - Under query -> bool -> must -> bool -> should -> are 3 different bool -> must -> whcih can contain
        either term if we are searching specific text or regex if we are searching for regular expression
        - The 3 different bools mentioned above are constructed dynamicly where at least one must exist and
        all three may exist
        - lowercase may be changed with sensitive giving us an option to search for case sensitive text. If we
        use lowercase everything will be automatically put to lowercase and so we don t care about case sensitivity.
        - aggs (or aggregations) are used to find latest revisions of a module if we are searching for latest
        revisions only.

        {
            "query":{
                "bool":{
                    "must":[
                        {
                            "bool":{
                                "must":{
                                    "terms":{
                                        "statement":[
                                            "leaf",
                                            "container"
                                        ]
                                    }
                                }
                            }
                        },
                        {
                            "bool":{
                                "should":[
                                    {
                                        "bool":{
                                            "must":{
                                                "term":{
                                                    "argument.lowercase":"foo"
                                                }
                                            }
                                        }
                                    },
                                    {
                                        "bool":{
                                            "must":{
                                                "term":{
                                                    "description.lowercase":"foo"
                                                }
                                            }
                                        }
                                    },
                                    {
                                        "bool":{
                                            "must":{
                                                "term":{
                                                    "module":"foo"
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            },
            "aggs":{
                "groupby":{
                    "terms":{
                        "field":"module.keyword",
                        "size": 2000
                    },
                    "aggs":{
                        "latest-revision":{
                            "max":{
                                "field":"revision"
                            }
                        }
                    }
                }
            }
        }
        """
        sensitive = 'lowercase'
        if self.__case_sensitive:
            sensitive = 'sensitive'
        else:
            self.__searched_term = self.__searched_term.lower()
        search_in = self.query['query']['bool']['must'][1]['bool']['should']
        for searched_field in self.__searched_fields:
            should_query = \
                {
                    'bool': {
                        'must': {
                            self.__type: {}
                        }
                    }
                }
            if searched_field == 'module':
                should_query['bool']['must'][self.__type][searched_field] = self.__searched_term
            else:
                should_query['bool']['must'][self.__type][
                    '{}.{}'.format(searched_field, sensitive)] = self.__searched_term
            search_in.append(should_query)
        self.LOGGER.debug('query:  {}'.format(self.query))

    def search(self):
        """
        Search using query produced. This search is done in parallel. We are making two searches at the same time.
        One search is being done as a scroll search. Elastic search does not allow us to get more then some number
        of results per search. If we want to search through all the results we have to use scroll but this does not
        give us an output of aggregations. That is why we have to create second normal search where we don t care about
        finding of search but we get only get aggregations from response. These two searches may run in parallel.

        Next we have to process the given response in self.__process_hits definition. And while processing it we can
        use scroll search to get next batch of result from search to process if it will be needed.

        :return list of rows containing dictionary that is filled with output for each column for yangcatalog search
        """
        hits = gevent.queue.JoinableQueue()
        process_first_search = gevent.spawn(self.__first_scroll, hits)

        self.LOGGER.debug('Running first search in parallel')
        if self.__latest_revision:
            self.LOGGER.debug('Processing aggregations search in parallel')
            self.__resolve_aggregations()
            self.LOGGER.debug('Aggregations processed joining the search')
        process_first_search.join()
        processed_rows = self.__process_hits(hits.get(), [])
        if self.__current_scroll_id is not None:
            self.__es.clear_scroll(body={'scroll_id': [self.__current_scroll_id]}, ignore=(404,))
        return processed_rows

    def __process_hits(self, hits: list, response_rows: list, reject=None):
        if reject is None:
            reject = []
        if hits is None or len(hits) == 0:
            return response_rows
        secondary_hits = gevent.queue.JoinableQueue()
        process_scroll_search = gevent.spawn(self.__continue_scrolling, secondary_hits)
        for hit in hits:
            row = {}
            source = hit['_source']
            name = source['module']
            revision = source['revision'].replace('02-28', '02-29')
            organization = source['organization']
            module_index = '{}@{}/{}'.format(name, revision, organization)
            if module_index in reject:
                continue
            if not self.__latest_revision or revision == self.__latest_revisions.get(name, '').replace('02-28', '02-29'):
                # we need argument, description, path and statement out of the elk response
                argument = source['argument']
                description = source['description']
                statement = source['statement']
                path = source['path']
                module_data = self.__redisConnection.get_module(module_index)
                if module_data != '{}':
                    module_data = json.loads(module_data)
                else:
                    self.LOGGER.error('Failed to get module from redis but found in elasticsearch {}'
                                      .format(module_index))
                    reject.append(module_index)
                    self.__missing_modules.append(module_index)
                    continue
                if self.__rejects_mibs_or_versions(module_index, reject, module_data):
                    continue
                row['name'] = argument
                row['revision'] = revision
                row['schema-type'] = statement
                row['path'] = path
                row['module-name'] = name

                if organization in self.SDOS:
                    row['origin'] = 'Industry Standard'
                elif organization == 'N/A':
                    row['origin'] = organization
                else:
                    row['origin'] = 'Vendor-Specific'
                row['organization'] = organization
                row['maturity'] = module_data.get('maturity-level', '')
                row['dependents'] = len(module_data.get('dependents', []))
                row['compilation-status'] = module_data.get('compilation-status', 'unknown')
                row['description'] = description
                if not self.__found_in_sub_search(row):
                    continue
                self.__trim_and_hash_row_by_columns(row, response_rows)
                if len(response_rows) >= self.__response_size or self.__current_scroll_id is None:
                    self.LOGGER.debug('elk search finished with len {} and scroll id {}'
                                      .format(len(response_rows), self.__current_scroll_id))
                    process_scroll_search.kill()
                    return response_rows
            else:
                reject.append(module_index)

        process_scroll_search.join()
        return self.__process_hits(secondary_hits.get(), response_rows, reject)

    def __first_scroll(self, hits):
        elk_response = {}
        try:
            query_no_agg = self.query.copy()
            query_no_agg.pop('aggs', '')
            elk_response = self.__es.search(index='yindex', doc_type='modules', body=query_no_agg, request_timeout=20,
                                            scroll=u'2m', size=self.__response_size)
        except ConnectionTimeout as e:
            self.LOGGER.error('Failed to connect to elasticsearch database with error - {}'.format(e))
            elk_response['hits'] = {'hits': []}
        self.LOGGER.debug('search complete with {} hits'.format(len(elk_response['hits']['hits'])))
        self.__current_scroll_id = elk_response.get('_scroll_id')
        hits.put(elk_response['hits']['hits'])

    def __continue_scrolling(self, hits):
        if self.__current_scroll_id is None:
            hits.put([])
            return
        elk_response = {}
        try:
            elk_response = self.__es.scroll(self.__current_scroll_id, scroll=u'2m', request_timeout=20)
        except ConnectionTimeout as e:
            self.LOGGER.error('Failed to connect to elasticsearch database with error - {}'.format(e))
            elk_response['hits'] = {'hits': []}
        self.__current_scroll_id = elk_response.get('_scroll_id')
        hits.put(elk_response['hits']['hits'])

    def __resolve_aggregations(self):
        response = {'aggregations': {'groupby': {'buckets': []}}}
        try:
            response = self.__es.search(index='yindex', doc_type='modules', body=self.query, size=0)
        except ConnectionTimeout as e:
            self.LOGGER.error('Failed to connect to elasticsearch database with error - {}'.format(e))
        aggregations = response['aggregations']['groupby']['buckets']
        for agg in aggregations:
            self.__latest_revisions[agg['key']] = agg['latest-revision']['value_as_string'].split('T')[0]

    def __rejects_mibs_or_versions(self, module_index, reject, module_data):
        if not self.__include_mibs and 'yang:smiv2:' in module_data.get('namespace', ''):
            reject.append(module_index)
            return True
        if module_data.get('yang-version') not in self.__yang_versions:
            reject.append(module_index)
            return True
        return False

    def __trim_and_hash_row_by_columns(self, row: dict, response_rows: list):
        if len(self.__remove_columns) == 0:
            response_rows.append(row)
        else:
            # if we are removing some columns we need to make sure that we trim the output if it is same.
            # This actually happens only if name description or path is being removed
            if 'name' in self.__remove_columns or 'description' in self.__remove_columns \
                    or 'path' in self.__remove_columns:
                row_hash = hashlib.sha256()
                for key, value in row.items():
                    if key in self.__output_columns:
                        row_hash.update(str(value).encode('utf-8'))
                        if key == 'name':
                            # if we use key as well
                            row_hash.update(str(row['path']).encode('utf-8'))
                row_hexadecimal = row_hash.hexdigest()

                for key in self.__remove_columns:
                    # remove keys that we do not want to be provided in output
                    row.pop(key, '')

                    if row_hexadecimal in self.__row_hashes:
                        self.LOGGER.info(
                            'Trimmed output row {} already exists in response rows. Cutting this one out'.format(row))
                    else:
                        self.__row_hashes.append(row_hexadecimal)
                        response_rows.append(row)
            else:
                for key in self.__remove_columns:
                    # remove keys that we do not want to be provided in output
                    row.pop(key, '')
                response_rows.append(row)

    def __found_in_sub_search(self, row):
        """
        The following json as an example might come here:
          "sub-search": [
            {
              "name": [
                "shared",
                "leafs"
              ],
              "organization": [
                "ietf"
              ]
            },
            {
              "name": [
                "organization"
              ]
            }
          ]
        Which means - name has to contain words 'shared' AND 'leafs' AND has to have
        organization 'ietf' OR name can be also contain only word 'organization'
        """
        if len(self.__sub_search) == 0:
            return True
        for search in self.__sub_search:
            passed = True
            for key, value in search.items():
                if not passed:
                    break
                if isinstance(value, list):
                    for v in value:
                        if v.lower() in str(row[key]).lower():
                            passed = True
                        else:
                            passed = False
                            break
                else:
                    if value.lower() in str(row[key]).lower():
                        passed = True
                    else:
                        passed = False
            if passed:
                return True
        return False
