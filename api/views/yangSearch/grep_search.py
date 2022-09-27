import json
import os
import subprocess
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

    def search(self, organizations: list[str], search_string: str, inverted_search: bool = False) -> list[dict]:
        module_names = self._get_matching_module_names(organizations, search_string, inverted_search)
        return self._search_modules_in_database(module_names)

    def _get_matching_module_names(
            self,
            organizations: list[str],
            search_string: str,
            inverted_search: bool
    ) -> tuple[str]:
        """
        Performs a native grep search of modules in self.all_modules_directory.
        Returns a list of all module names that satisfy the search.

        Arguments:
            :param organizations    (list[str]) list of organizations of modules which to search for
            :param search_string    (str) actual search string, can include wildcards
            :param inverted_search  (bool) use inverted search in grep, "-v" flag
        """
        final_grep_search = ''
        for organization in organizations:
            final_grep_search = (
                f'{final_grep_search}organization ".*{organization}.*"|namespace "urn:{organization}.*";|'
            )
        final_grep_search = f'\'{final_grep_search}{search_string}\''
        module_names = set()
        try:
            grep_result = subprocess.check_output(
                f'grep -ri{"v" if inverted_search else ""} -E {final_grep_search} {self.all_modules_directory}',
                shell=True
            )
            for result in grep_result.decode().split('\n'):
                if not result:
                    continue
                matching_string = result.split('.yang:')[1].lstrip().rstrip()
                if matching_string.startswith('organization "') or matching_string.startswith('namespace "urn:'):
                    continue
                module_name = result.split(self.all_modules_directory)[1].split('.yang')[0]
                module_names.add(module_name)
        except subprocess.CalledProcessError:
            raise ValueError('Invalid search input')
        return tuple(module_names)

    def _search_modules_in_database(self, module_names: tuple[str]) -> list[dict]:
        response = []
        for module_name in module_names:
            name, revision = module_name.split('@')
            self.query['query']['bool']['must'] = [
                {'term': {'module': name}},
                {'term': {'revision': validate_revision(revision)}}
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
