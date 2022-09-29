import json
import os
import subprocess
import typing as t
from configparser import ConfigParser

from api.views.yangSearch.response_row import ResponseRow
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from redisConnections.redisConnection import RedisConnection
from utility import log
from utility.create_config import create_config
from utility.util import validate_revision


class GrepSearch:
    """
    Class is used to perform a grep-like search through text of all available modules.
    """

    def __init__(
            self,
            config: ConfigParser = create_config(),
            es_manager: ESManager = ESManager(),
            modules_es_index: ESIndices = ESIndices.YINDEX,
            redis_connection: RedisConnection = RedisConnection(),
    ):
        all_modules_directory = config.get('Directory-Section', 'save-file-dir')
        self.all_modules_directory = (
            all_modules_directory if
            all_modules_directory.endswith('/') else
            f'{all_modules_directory}/'
        )
        query_path = os.path.join(os.environ['BACKEND'], 'api/views/yangSearch/json/grep_search.json')
        with open(query_path) as query_file:
            self.query = json.load(query_file)

        log_file_path = os.path.join(config.get('Directory-Section', 'logs'), 'yang.log')
        self.logger = log.get_logger('yc-elasticsearch', log_file_path)

        self.modules_es_index = modules_es_index
        self._es_manager = es_manager
        self._redis_connection = redis_connection

        self._processed_modules = {}

    def search(
            self,
            organizations: list[str],
            search_string: str,
            inverted_search: bool = False,
            case_sensitive: bool = False,
    ) -> list[dict]:
        module_names = self._get_matching_module_names(search_string, inverted_search, case_sensitive)
        if not module_names:
            return []
        return self._search_modules_in_database(organizations, module_names)

    def _get_matching_module_names(
            self,
            search_string: str,
            inverted_search: bool,
            case_sensitive: bool,
    ) -> t.Optional[tuple[str]]:
        """
        Performs a native pcregrep search of modules in self.all_modules_directory.
        Returns a list of all module names that satisfy the search.

        Arguments:
            :param search_string    (str) actual search string, can include wildcards
            :param inverted_search  (bool) indicates if the result must contain all modules satisfying the search or
            all the modules not satisfying the search
            :param case_sensitive   (bool) indicates if the search must be case-sensitive or not
        """
        module_names_with_format = set()
        pcregrep_shell_command = f'pcregrep -{"" if case_sensitive else "i"}lrMe'
        try:
            pcregrep_result = subprocess.check_output(
                f'{pcregrep_shell_command} \'{search_string}\' {self.all_modules_directory.rstrip("/")}',
                shell=True
            )
            for result in pcregrep_result.decode().split('\n'):
                if not result:
                    continue
                module_name_with_format = result.split(self.all_modules_directory)[1].split(':')[0]
                module_names_with_format.add(module_name_with_format)
        except subprocess.CalledProcessError as e:
            if not e.output and inverted_search:
                self.logger.info(f'All the modules satisfy the inverted search')
            elif not e.output:
                self.logger.info(f'Did not find any modules satisfying such a search: {search_string}')
                return
            else:
                raise ValueError('Invalid search input')
        if inverted_search:
            all_module_names_with_format = set(os.listdir(self.all_modules_directory))
            module_names_with_format = all_module_names_with_format - module_names_with_format
        return tuple(module_names_with_format)

    def _search_modules_in_database(self, organizations: list[str], module_names_with_format: tuple[str]) -> list[dict]:
        response = []
        self.query['query']['bool']['should'] = [
            {'term': {'organization': organization}} for organization in organizations
        ]
        for module_name in module_names_with_format:
            name, revision = module_name.split('.yang')[0].split('@')
            self.query['query']['bool']['must'] = [
                {'term': {'module': name}},
                {'term': {'revision': validate_revision(revision)}},
            ]
            es_response = self._es_manager.generic_search(
                index=self.modules_es_index, query=self.query, response_size=None
            )['hits']['hits']
            for result in es_response:
                response.append(self._create_response_row_for_module(result['_source']))
        return response

    def _create_response_row_for_module(self, module_search_result: dict) -> dict:
        row = ResponseRow(elastic_hit=module_search_result)
        module_key = f'{row.module_name}@{row.revision}/{row.organization}'
        if (module_data := self._processed_modules.get('module_key')) is not None:
            return self._fill_response_row(row, module_data)
        module_data = self._redis_connection.get_module(module_key)
        module_data = json.loads(module_data)
        self._processed_modules[module_key] = module_data
        if not module_data:
            self.logger.error(f'Failed to get module from Redis, but found in Elasticsearch: {module_key}')
        return self._fill_response_row(row, module_data)

    def _fill_response_row(self, row: ResponseRow, module_data: dict) -> dict:
        if not module_data:
            row.create_output(['dependents'])
            return row.output_row
        row.dependents = len(module_data.get('dependents', []))
        row.compilation_status = module_data.get('compilation-status', 'unknown')
        row.create_output([])
        return row.output_row
