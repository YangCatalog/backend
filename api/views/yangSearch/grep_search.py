import json
import os
import subprocess
import typing as t
from configparser import ConfigParser
from datetime import datetime, timedelta

from api.cache.api_cache import cache
from api.views.yangSearch.constants import GREP_SEARCH_CACHE_TIMEOUT
from api.views.yangSearch.response_row import ResponseRow
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from redisConnections.redisConnection import RedisConnection
from utility import log
from utility.create_config import create_config
from utility.staticVariables import ORGANIZATIONS
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
        starting_cursor: int = 0,
    ):
        self.previous_cursor = 0
        self.starting_cursor = self.finishing_cursor = starting_cursor

        self.all_modules_directory = config.get('Directory-Section', 'save-file-dir')
        self.results_per_page = int(config.get('Web-Section', 'grep-search-results-per-page', fallback=500))

        self.listdir_results_cache_key = f'listdir_{self.all_modules_directory}'

        query_path = os.path.join(os.environ['BACKEND'], 'api', 'views', 'yangSearch', 'json', 'grep_search.json')
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
        organizations = list(
            filter(
                lambda org: org in ORGANIZATIONS,
                map(lambda org: org.lower(), organizations),
            ),
        )
        module_names_with_file_extension = self._get_matching_module_names(
            search_string,
            inverted_search,
            case_sensitive,
            organizations,
        )
        if not module_names_with_file_extension:
            return []
        return self._search_modules_in_database(organizations, module_names_with_file_extension)

    def _get_matching_module_names(
        self,
        search_string: str,
        inverted_search: bool,
        case_sensitive: bool,
        organizations: list[str],
    ) -> t.Optional[t.Union[tuple[str], list[str]]]:
        """
        Performs a native pcregrep search of modules in self.all_modules_directory.
        Returns a list of all module names that satisfy the search.

        Arguments:
            :param search_string    (str) actual search string, can include wildcards
            :param inverted_search  (bool) indicates if the result must contain all modules satisfying the search or
            all the modules not satisfying the search
            :param case_sensitive   (bool) indicates if the search must be case-sensitive or not
            :param organizations   (list[str]) names of organizations that modules should be of
        """
        cache_key = (
            f'{search_string}{inverted_search}{case_sensitive}{str(sorted(organizations)) if organizations else ""}'
        )
        if result := self._get_cached_search_results(cache_key):
            return result
        (
            pcregrep_search,
            get_uniq_paths,
            extract_filenames,
            filter_by_organizations,
        ) = self._get_filesystem_search_commands(
            search_string,
            inverted_search,
            case_sensitive,
            organizations,
        )
        try:
            command = filter_by_organizations if filter_by_organizations else extract_filenames
            command_output, error = command.communicate()
        except (OSError, subprocess.SubprocessError) as e:
            raise ValueError(f'Such a search: {search_string}, caused an error: {e}')
        if (
            error
            or (error := pcregrep_search.stderr.read())
            or (error := get_uniq_paths.stderr.read())
            or (filter_by_organizations and (error := extract_filenames.stderr.read()))
        ):
            raise ValueError(f'Such a search: {search_string}, caused an error: {error}')
        elif not command_output and inverted_search:
            self.logger.info(f'All the modules satisfy the inverted search: {search_string}')
            return self._get_modules_from_cursor(self._get_all_modules_with_filename_extension())
        elif not command_output:
            self.logger.info(f'Did not find any modules satisfying such a search: {search_string}')
            return
        module_names_with_file_extension = command_output.decode().split('\n')
        if inverted_search:
            module_names_with_file_extension = tuple(
                set(self._get_all_modules_with_filename_extension()) - set(module_names_with_file_extension),
            )
        self._cache_search_results(cache_key, module_names_with_file_extension)
        return self._get_modules_from_cursor(module_names_with_file_extension)

    def _get_cached_search_results(self, cache_key: str) -> t.Optional[t.Union[list[str], tuple[str]]]:
        cached_pcregrep_search_results = cache.get(cache_key)
        if not cached_pcregrep_search_results:
            return
        cached_pcregrep_search_results = json.loads(cached_pcregrep_search_results)
        cursors = cached_pcregrep_search_results['cursors']
        module_names_with_file_extension = cached_pcregrep_search_results['module_names_with_file_extension']
        timeout_timestamp = cached_pcregrep_search_results['timeout_timestamp']
        try:
            self.previous_cursor = cursors[-2]
        except IndexError:
            pass
        if self.starting_cursor not in cursors:
            cursors.append(self.starting_cursor)
        cached_pcregrep_search_results['cursors'] = cursors
        cache.set(
            cache_key,
            json.dumps(cached_pcregrep_search_results),
            timeout=timeout_timestamp - datetime.now().timestamp(),
        )
        return self._get_modules_from_cursor(module_names_with_file_extension)

    def _get_filesystem_search_commands(
        self,
        search_string: str,
        inverted_search: bool,
        case_sensitive: bool,
        organizations: list[str],
    ) -> tuple[subprocess.Popen, subprocess.Popen, subprocess.Popen, t.Optional[subprocess.Popen]]:
        search_options = f'-{"" if case_sensitive else "i"}lrMe'
        pcregrep_search = subprocess.Popen(
            ['pcregrep', search_options, search_string, self.all_modules_directory],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        get_uniq_paths = subprocess.Popen(
            ['uniq'],
            stdin=pcregrep_search.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        extract_filenames = subprocess.Popen(
            ['awk', '-F/', '{ print $NF }'],
            stdin=get_uniq_paths.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not inverted_search and organizations:
            # in the case of an inverted search, organizations will be resolved in the ES search only
            filter_by_organizations = subprocess.Popen(
                ['grep', '-E', '|'.join(organizations)],
                stdin=extract_filenames.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return pcregrep_search, get_uniq_paths, extract_filenames, filter_by_organizations
        return pcregrep_search, get_uniq_paths, extract_filenames, None

    def _cache_search_results(self, cache_key: str, modules: t.Union[list[str], tuple[str]]):
        cache.set(
            cache_key,
            json.dumps(
                {
                    'timeout_timestamp': (datetime.now() + timedelta(seconds=GREP_SEARCH_CACHE_TIMEOUT)).timestamp(),
                    'module_names_with_file_extension': modules,
                    'cursors': [self.starting_cursor],
                },
            ),
            timeout=GREP_SEARCH_CACHE_TIMEOUT,
        )

    def _get_modules_from_cursor(
        self,
        modules: t.Union[list[str], tuple[str]],
    ) -> t.Optional[t.Union[list[str], tuple[str]]]:
        try:
            return modules[self.starting_cursor :]
        except IndexError:
            return None

    def _get_all_modules_with_filename_extension(self) -> list[str]:
        all_modules = cache.get(self.listdir_results_cache_key)
        if not all_modules:
            all_modules = os.listdir(self.all_modules_directory)
            cache.set(
                self.listdir_results_cache_key,
                all_modules,
                timeout=GREP_SEARCH_CACHE_TIMEOUT,
            )
        return all_modules

    def _search_modules_in_database(
        self,
        organizations: list[str],
        module_names_with_file_extension: tuple[str],
    ) -> list[dict]:
        response = []
        if not organizations:
            self.query['query']['bool']['minimum_should_match'] = 0
        else:
            self.query['query']['bool']['should'] = [
                {'term': {'organization': organization}} for organization in organizations
            ]
            self.query['query']['bool']['minimum_should_match'] = 1
        for module_name in module_names_with_file_extension:
            if len(response) >= self.results_per_page:
                return response
            if not module_name:
                continue
            self.finishing_cursor += 1
            name, revision = module_name.split('.yang')[0].split('@')
            self.query['query']['bool']['must'] = [
                {'term': {'module': name}},
                {'term': {'revision': validate_revision(revision)}},
            ]
            es_response = self._es_manager.generic_search(
                index=self.modules_es_index,
                query=self.query,
                response_size=None,
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
