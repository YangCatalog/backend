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
import re
import typing as t
from logging import Logger
from urllib import parse as urllib_parse

from flask.blueprints import Blueprint
from flask.globals import request
from flask.helpers import make_response
from flask.json import jsonify
from pyang import plugin
from werkzeug.exceptions import abort

import utility.log as log
from api.cache.api_cache import cache
from api.my_flask import app
from api.views.yangSearch.constants import GREP_SEARCH_CACHE_TIMEOUT
from api.views.yangSearch.elkSearch import ElkSearch
from api.views.yangSearch.grep_search import GrepSearch
from api.views.yangSearch.search_params import SearchParams
from elasticsearchIndexing.models.es_indices import ESIndices
from elasticsearchIndexing.models.keywords_names import KeywordsNames
from utility.create_config import create_config
from utility.staticVariables import MODULE_PROPERTIES_ORDER, OUTPUT_COLUMNS, SCHEMA_TYPES
from utility.yangParser import create_context


class YangSearch(Blueprint):
    logger: Logger


bp = YangSearch('yangSearch', __name__)


@bp.record
def init_logger(state):
    bp.logger = log.get_logger('yang-search', f'{state.app.config.d_logs}/yang.log')


@bp.before_request
def set_config():
    global app_config
    app_config = app.config


@bp.route('/grep_search', methods=['GET'])
@cache.cached(query_string=True, timeout=GREP_SEARCH_CACHE_TIMEOUT)
def grep_search():
    if not request.query_string:
        abort(400, description='No query parameters were provided')
    query_params = urllib_parse.parse_qs(urllib_parse.unquote(request.query_string))
    search_string = value[0] if (value := query_params.get('search')) else None
    if not search_string:
        abort(400, description='Search cannot be empty')
    organizations = query_params.get('organizations', [])
    inverted_search = value[0].lower() == 'true' if (value := query_params.get('inverted_search')) else False
    case_sensitive = value[0].lower() == 'true' if (value := query_params.get('case_sensitive')) else False
    previous_cursor = int(value[0]) if (value := query_params.get('previous_cursor')) else 0
    cursor = int(value[0]) if (value := query_params.get('cursor')) else 0
    config = create_config()
    try:
        grep_search_instance = GrepSearch(config=config, es_manager=app_config.es_manager, starting_cursor=cursor)
        results = grep_search_instance.search(organizations, search_string, inverted_search, case_sensitive)
    except ValueError as e:
        abort(400, description=str(e))
    response_base_string = f'{config.get("Web-Section", "yangcatalog-api-prefix")}/yang-search/v2/grep_search?'
    query_string = (
        f'search={search_string}'
        f'&organizations={"&organizations=".join(organizations)}'
        f'&inverted_search={"true" if inverted_search else "false"}'
        f'&case_sensitive={"true" if case_sensitive else "false"}'
    )
    if results:
        previous_page_query_string = (
            f'{query_string}&previous_cursor={grep_search_instance.previous_cursor}&cursor={previous_cursor}'
        )
        previous_page = f'{response_base_string}{urllib_parse.quote(previous_page_query_string)}' if cursor > 0 else ''
        next_page_query_string = (
            f'{query_string}&previous_cursor={cursor}&cursor={grep_search_instance.finishing_cursor}'
        )
        next_page = f'{response_base_string}{urllib_parse.quote(next_page_query_string)}'
    else:
        previous_page_query_string = (
            f'{query_string}&previous_cursor={grep_search_instance.previous_cursor}&cursor={previous_cursor}'
        )
        previous_page = f'{response_base_string}{urllib_parse.quote(previous_page_query_string)}' if cursor > 0 else ''
        next_page = ''
    response = {
        'previous_page': previous_page,
        'next_page': next_page,
        'results': results,
    }
    return make_response(jsonify(response))


@bp.route('/tree/<module_name>', methods=['GET'])
def tree_module(module_name: str):
    """
    Generates yang tree view of the module.
    :param module_name: Module for which we are generating the tree.
    :return: json response with yang tree
    """
    return tree_module_revision(module_name, None)


@bp.route('/tree/<module_name>@<revision>', methods=['GET'])
def tree_module_revision(module_name: str, revision: t.Optional[str] = None):
    """
    Generates yang tree view of the module.
    :param module_name: Module for which we are generating the tree.
    :param revision   : Revision of the module
    :return: json response with yang tree
    """
    response = {}
    alerts = []
    jstree_json = {}
    nmodule = os.path.basename(module_name)
    if nmodule != module_name:
        abort(400, description='Invalid module name specified')
    else:
        revisions, organization = get_modules_revision_organization(module_name, revision)
        if len(revisions) == 0:
            abort(404, description='Provided module does not exist')

        if revision is None:
            # get the latest revision of provided module
            revision = revisions[0]

        path_to_yang = f'{app_config.d_save_file_dir}/{module_name}@{revision}.yang'
        plugin.plugins = []
        plugin.init([])
        ctx = create_context(app_config.d_yang_models_dir)
        ctx.opts.lint_namespace_prefixes = []
        ctx.opts.lint_modulename_prefixes = []

        for plug in plugin.plugins:
            plug.setup_ctx(ctx)
        try:
            with open(path_to_yang, 'r') as f:
                module_context = ctx.add_module(path_to_yang, f.read())
                assert module_context
        except Exception:
            msg = f'File {path_to_yang} was not found'
            bp.logger.exception(msg)
            abort(400, description=msg)
        imports_includes = []
        imports_includes.extend(module_context.search('import'))
        imports_includes.extend(module_context.search('include'))
        import_include_map = {}
        for imp_inc in imports_includes:
            prefix = imp_inc.search('prefix')
            if len(prefix) == 1:
                prefix = prefix[0].arg
            else:
                prefix = 'None'
            import_include_map[prefix] = imp_inc.arg
        json_ytree = app_config.d_json_ytree
        yang_tree_file_path = f'{json_ytree}/{module_name}@{revision}.json'
        module_key = f'{module_name}@{revision}/{organization}'
        response['maturity'] = get_module_data(module_key).get('maturity-level', '').upper()
        response['import-include'] = import_include_map

        if os.path.isfile(yang_tree_file_path):
            try:
                with open(yang_tree_file_path) as f:
                    json_tree = json.load(f)
                if json_tree is None:
                    alerts.append('Failed to decode JSON data: ')
                else:
                    response['namespace'] = json_tree.get('namespace', '')
                    response['prefix'] = json_tree.get('prefix', '')
                    import_include_map[response['prefix']] = module_name
                    data_nodes = build_tree(json_tree, module_name, import_include_map)
                    jstree_json = {'data': [data_nodes]}
                    if json_tree.get('rpcs') is not None:
                        rpcs = {'name': json_tree['prefix'] + ':rpcs', 'children': json_tree['rpcs']}
                        jstree_json['data'].append(build_tree(rpcs, module_name, import_include_map))
                    if json_tree.get('notifications') is not None:
                        notifs = {'name': json_tree['prefix'] + ':notifs', 'children': json_tree['notifications']}
                        jstree_json['data'].append(build_tree(notifs, module_name, import_include_map))
                    if json_tree.get('augments') is not None:
                        augments = {'name': json_tree['prefix'] + ':augments', 'children': []}
                        for aug in json_tree.get('augments'):
                            aug_info = {'name': aug['augment_path'], 'children': aug['augment_children']}
                            augments['children'].append(aug_info)
                        jstree_json['data'].append(build_tree(augments, module_name, import_include_map, augments=True))
            except Exception as e:
                alerts.append(f'Failed to read YANG tree data for {module_key}, {e}')
        else:
            alerts.append(f'YANG Tree data does not exist for {module_key}')
    if jstree_json is None:
        response['jstree_json'] = {}
        alerts.append('Json tree could not be generated')
    else:
        response['jstree_json'] = jstree_json

    response['module'] = f'{module_name}@{revision}'
    response['warning'] = alerts

    return make_response(jsonify(response), 200)


@bp.route('/impact-analysis', methods=['POST'])
def impact_analysis():
    if not request.json:
        abort(400, description='No input data')
    payload = request.json
    bp.logger.info(f'Running impact analysis with following payload:\n{payload}')
    name = payload.get('name')
    revision = payload.get('revision')
    allowed_organizations = payload.get('organizations', [])
    rfc_allowed = payload.get('allow-rfc', True)
    submodules_allowed = payload.get('allow-submodules', True)
    graph_directions = payload.get('graph-direction', ['dependents', 'dependencies'])
    for direction in graph_directions:
        if direction not in ['dependents', 'dependencies']:
            abort(400, f'Only list of {graph_directions} are allowed as graph directions')

    # GET module details
    response = {}
    details = module_details(name, revision, True)
    assert isinstance(details, dict)
    if 'warning' in details:
        return jsonify(details)
    searched_module = details['metadata']
    assert isinstance(searched_module, dict)
    response = {
        'name': searched_module['name'],
        'revision': searched_module['revision'],
        'organization': searched_module['organization'],
        'reference': searched_module.get('reference', ''),
        'maturity-level': searched_module.get('maturity-level', ''),
        'dependents': [],
        'dependencies': [],
    }
    # this file is created and updated on yangParser exceptions
    try:
        with open(os.path.join(app_config.d_var, 'unparsable-modules.json')) as f:
            unparsable_modules = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        unparsable_modules = []

    def unparsable(module):
        if 'revision' in module and f'{module["name"]}@{module["revision"]}.yang' in unparsable_modules:
            return True
        return False

    for direction in graph_directions:
        response[direction] = list(
            filter(
                None,
                (
                    get_dependencies_dependents_data(module, submodules_allowed, allowed_organizations, rfc_allowed)
                    for module in searched_module.get(direction, [])
                    if not unparsable(module)
                ),
            ),
        )

    return jsonify(response)


@bp.route('/search', methods=['POST'])
def search():
    if not request.json:
        abort(400, description='No input data')
    payload = request.json
    bp.logger.info(f'Running search with following payload {payload}')
    searched_term = payload.get('searched-term')
    if not searched_term or not isinstance(searched_term, str):
        abort(400, description='You have to define "searched_term" as a string')
    if len(searched_term) < 2:
        abort(400, description='You have to define "searched-term" containing at least 2 characters')

    search_params = SearchParams(
        case_sensitive=is_boolean(payload, 'case-sensitive', False),
        use_synonyms=is_boolean(payload, 'use-synonyms', True),
        query_type=is_string_in(payload, 'type', 'term', ['term', 'regexp']),
        include_mibs=is_boolean(payload, 'include-mibs', False),
        latest_revision=is_boolean(payload, 'latest-revision', True),
        include_drafts=is_boolean(payload, 'include-drafts', True),
        searched_fields=is_list_in(payload, 'searched-fields', ['module', 'argument', 'description']),
        yang_versions=is_list_in(payload, 'yang-versions', ['1.0', '1.1']),
        schema_types=is_list_in(payload, 'schema-types', SCHEMA_TYPES),
        output_columns=is_list_in(payload, 'output-columns', OUTPUT_COLUMNS),
        sub_search=each_key_in(payload, 'sub-search', OUTPUT_COLUMNS),
    )
    elk_search = ElkSearch(searched_term, app_config.d_logs, app_config.es_manager, app.redisConnection, search_params)
    elk_search.construct_query()
    response = {}
    response['rows'], response['max-hits'] = elk_search.search()
    response['warning'] = elk_search.alerts()
    response['timeout'] = elk_search.timeout
    return make_response(jsonify(response), 200)


@bp.route('/completions/<keyword>/<pattern>', methods=['GET'])
def get_services_list(keyword: str, pattern: str):
    """
    Provides autocompletion for search bars on web pages of impact_analysis
    and module_details.

    Arguments:
        :param keyword  (str) Type of what we are autocompleting 'module', 'organization' or 'draft'
        :param pattern  (str) Searched string - input from user
    :return: list of autocompletion results
    """
    result = []
    if not pattern:
        return make_response(jsonify(result), 200)

    if keyword == 'organization':
        result = app_config.es_manager.autocomplete(ESIndices.AUTOCOMPLETE, KeywordsNames.ORGANIZATION, pattern)
    if keyword == 'module':
        result = app_config.es_manager.autocomplete(ESIndices.AUTOCOMPLETE, KeywordsNames.NAME, pattern)
    if keyword == 'draft':
        result = app_config.es_manager.autocomplete(ESIndices.DRAFTS, KeywordsNames.DRAFT, pattern)

    return make_response(jsonify(result), 200)


@bp.route('/show-node/<name>/<path:path>', methods=['GET'])
def show_node(name: str, path: str):
    """
    View for show_node page, which provides context for show_node.html
    Shows description for yang modules.

    Arguments:
        :param name     (str) Takes first argument from URL which is module name
        :param path     (str) Path for node
    :return: returns json to show node
    """
    return show_node_with_revision(name, path)


@bp.route('/show-node/<name>/<path:path>/<revision>', methods=['GET'])
def show_node_with_revision(name: str, path: str, revision: t.Optional[str] = None):
    """
    View for show_node page, which provides context for show_node.html
    Shows description for yang modules.

    Arguments:
        :param name     (str) Takes first argument from URL which is module name
        :param path     (str) Path for node
        :param revision (str) Revision of YANG module - if specified
    :return: returns json to show node
    """
    if not name:
        abort(400, description='You must specify a "name" argument')
    if not path:
        abort(400, description='You must specify a "path" argument')

    properties = []
    app.logger.info(f'Show node on path - show-node/{name}/{path}/{revision}')
    path = f'/{path}'
    try:
        if not revision:
            bp.logger.warning('Revision not submitted - getting latest')
            revision = get_latest_module_revision(name)

        module = {'name': name, 'revision': revision, 'path': path}
        hits = app_config.es_manager.get_node(module)['hits']['hits']

        if not hits:
            abort(404, description=f'Could not find data for {name}@{revision} at {path}')
        result = hits[0]['_source']
        properties = json.loads(result['properties'])
    except Exception as e:
        abort(400, description=f'Module and path that you specified can not be found - {e}')
    return make_response(jsonify(properties), 200)


@bp.route('/module-details/<module>', methods=['GET'])
def module_details_no_revision(module: str):
    """
    Search for data saved in our datastore (ConfD/Redis) based on specific module with no revision.
    Revision will be the latest one that we have.
    :return: returns json with yang-catalog saved metdata of a specific module
    """
    return jsonify(module_details(module, None))


@bp.route('/module-details/<module>@<revision>', methods=['GET'])
def module_details(module: str, revision: t.Optional[str] = None, warnings: bool = False):
    """
    Search for data saved in our datastore (= Redis) based on specific module with some revision.
    Revision can be empty called from endpoint /module-details/<module> (= module_details_no_revision() method).

    Arguments:
        :param module           (str) Name of the searched module
        :param revision         (str) (Optional) Revision of the searched module (can be None)
        :param warnings         (bool) Whether return with warnings or not
    :return: returns json with yang-catalog saved metdata of a specific module
    """
    if not module:
        abort(400, description='No module name provided')
    if revision is not None and (len(revision) != 10 or re.match(r'\d{4}[-/]\d{2}[-/]\d{2}', revision) is None):
        abort(400, description='Revision provided has wrong format - please use "YYYY-MM-DD" format')

    elk_response = get_modules_revision_organization(module, None, warnings)
    if 'warning' in elk_response:
        return elk_response
    revisions, organization = elk_response
    if len(revisions) == 0:
        if warnings:
            return {'warning': f'module {module} does not exists in API'}
        abort(404, description='Provided module does not exist')

    # get the latest revision of provided module if revision not defined
    revision = revisions[0] if not revision else revision

    response = {'current-module': f'{module}@{revision}.yang', 'revisions': revisions}

    # get module from Redis
    module_key = f'{module}@{revision}/{organization}'
    module_data = app.redisConnection.get_module(module_key)
    if module_data == '{}':
        if warnings:
            return {'warning': f'module {module_key} does not exists in API'}
        abort(404, description='Provided module does not exist')
    module_data = json.loads(module_data)
    response['metadata'] = module_data
    return response


@bp.route('/yang-catalog-help', methods=['GET'])
def get_yang_catalog_help():
    """
    Iterate through all the different descriptions of the yang-catalog yang module and provide
    json with key as an argument of the container/list/leaf and value containing help-text. If
    there is something inside of container/list that container will not only contain help-text
    but other container/list/leaf under this statement again as a dictionary
    :return: returns json with yang-catalog help text
    """
    revision = get_latest_module_revision('yang-catalog')
    module = {'name': 'yang-catalog', 'revision': revision}
    hits = app_config.es_manager.get_module_by_name_revision(ESIndices.YINDEX, module)
    module_details_data = {}
    skip_statement = ['typedef', 'grouping', 'identity']
    for hit in hits:
        help_text = ''
        hit = hit['_source']
        paths = hit['path'].split('/')[4:]
        if (
            'yc:vendors?container/' in hit['path']
            or hit['statement'] in skip_statement
            or len(paths) == 0
            or 'platforms' in hit['path']
        ):
            continue
        if not hit.get('argument'):
            continue
        if hit.get('description'):
            help_text = hit.get('description').replace('\\n', '\n')
        properties = json.loads(hit.get('properties'))
        for prop in properties:
            if not prop.get('type'):
                continue
            if not prop.get('type', {}).get('has_children'):
                continue
            for child in prop['type']['children']:
                if not child.get('enum', {}).get('has_children'):
                    continue
                for echild in child['enum']['children']:
                    if not echild['description']:
                        continue
                    description = echild['description']['value'].replace('\\n', '\n').replace('\n', '<br/>\r\n')
                    help_text += f'<br/>\r\n<br/>\r\n{child.get("enum")["value"]}: {description}'
            break

        paths.reverse()
        update_dictionary_recursively(module_details_data, paths, help_text)

    return make_response(jsonify(module_details_data), 200)


def update_dictionary_recursively(module_details_data: dict, path_to_populate: list, help_text: str):
    """
    Update dictionary. Recursively create dictionary of dictionaries based on the path which are
    nested keys of dictionary and each key has a sibling help-text key which contains the help_text
    string
    :param module_details_data: dictionary that we are currently updating recursively
    :param path_to_populate: list of keys used in dictionary
    :param help_text: text describing each module detail
    """
    if len(path_to_populate) == 0:
        module_details_data['help-text'] = help_text
        return
    last_path_data = path_to_populate.pop()
    last_path_data = last_path_data.split(':')[-1].split('?')[0]
    if module_details_data.get(last_path_data):
        update_dictionary_recursively(module_details_data[last_path_data], path_to_populate, help_text)
    else:
        module_details_data[last_path_data] = {'ordering': MODULE_PROPERTIES_ORDER.get(last_path_data, '')}
        update_dictionary_recursively(module_details_data[last_path_data], path_to_populate, help_text)


def get_modules_revision_organization(module_name: str, revision: t.Optional[str] = None, warnings: bool = False):
    """
    Get list of revisions and organization of the module give by 'module_name'.

    Arguments:
        :param module_name      (str) Name of the searched module
        :param revision         (str) Revision of the searched module (can be None)
        :param warnings         (bool) Whether return with warnings or not
    :return: tuple (list of revisions and organization) of specified module name
    """
    try:
        if revision is None:
            hits = app_config.es_manager.get_sorted_module_revisions(ESIndices.AUTOCOMPLETE, module_name)
        else:
            module = {'name': module_name, 'revision': revision}
            hits = app_config.es_manager.get_module_by_name_revision(ESIndices.AUTOCOMPLETE, module)

        organization = hits[0]['_source']['organization']
        revisions = []
        for hit in hits:
            hit = hit['_source']
            revisions.append(hit['revision'])
        return revisions, organization
    except IndexError:
        name_rev = f'{module_name}@{revision}' if revision else module_name
        bp.logger.warning(f'Failed to get revisions and organization for {name_rev}')
        if warnings:
            return {'warning': f'Failed to find module {name_rev}'}
        abort(404, f'Failed to get revisions and organization for {name_rev}')


def get_latest_module_revision(module_name: str) -> str:
    """
    Gets latest revision of the module.

    Argument:
        :param module_name      (str) Name of the searched module
    :return: latest revision of the module
    """
    try:
        es_result = app_config.es_manager.get_sorted_module_revisions(ESIndices.AUTOCOMPLETE, module_name)
        return es_result[0]['_source']['revision']
    except IndexError:
        bp.logger.exception(f'Failed to get revision for {module_name}')
        abort(400, f'Failed to get revision for {module_name} - please use module that exists')


def update_dictionary(updated_dictionary: dict, list_dictionaries: list, help_text: str):
    """
    This definition serves to automatically fill in dictionary with helper texts. This is done recursively,
    since path on which helper text occurred may be under some other dictionary. Example - we have name as a
    name of the module but also name under specific submodule or name under implementation software-flavor.
    :param updated_dictionary: dictionary that we are updating
    :param list_dictionaries: reversed list that we search through dictionary - if name doesn't exist we create such
        a key with value of empty dictionary
    :param help_text: help text for specific container list or leaf
    """
    if len(list_dictionaries) == 0:
        updated_dictionary['help-text'] = help_text
        return
    pop = list_dictionaries.pop()
    pop = pop.split(':')[-1].split('?')[0]
    if updated_dictionary.get(pop):
        update_dictionary(updated_dictionary[pop], list_dictionaries, help_text)
    else:
        updated_dictionary[pop] = {}
        update_dictionary(updated_dictionary[pop], list_dictionaries, help_text)


def is_boolean(payload: dict, key: str, default: bool):
    obj = payload.get(key, default)
    if not isinstance(obj, bool):
        abort(400, f'Value of key "{key}" must be boolean')
    return obj


def is_string_in(payload: dict, key: str, default: str, one_of: t.List[str]):
    obj = payload.get(key, default)
    if not isinstance(obj, str) or obj not in one_of:
        abort(400, f'Value of key "{key}" must be string from following list: {one_of}')
    return obj


def is_list_in(payload: dict, key: str, default: t.List[str]):
    objs = payload.get(key, default)
    if str(objs).lower() == 'all':
        return default
    one_of = default
    if not isinstance(objs, list):
        abort(400, f'Value of key "{key}" must be string from following list: {one_of}')
    if len(objs) == 0:
        return default
    for obj in objs:
        if obj not in one_of:
            abort(400, f'Value of key "{key}" must be string from following list: {one_of}')
    return objs


def each_key_in(payload: dict, payload_key: str, keys: t.List[str]):
    rows = payload.get(payload_key, [])
    if not isinstance(rows, list):
        abort(400, f'Value of key "{payload_key}" must be string from following list: {keys}')
    for row in rows:
        for key in row.keys():
            if key not in keys:
                abort(400, f'Key {key} must be string from following list: {keys} in {payload_key}')
    return rows


def get_module_data(module_key: str):
    bp.logger.info(f'searching for module {module_key}')
    module_data = app.redisConnection.get_module(module_key)
    if module_data == '{}':
        abort(404, description='Provided module does not exist')
    module_data = json.loads(module_data)
    return module_data


def build_tree(jsont: dict, module: str, imp_inc_map, pass_on_schemas=None, augments=False):
    """Builds data for yang_tree.html, takes json and recursively writes out it's children.

    Arguments:
        :param jsont        (dict) input json
        :param module       (str) module name
    :return: (dict) with all nodes and their parameters
    """

    def _create_node_path(jsont_path: str):
        if augments:
            return jsont_path
        else:
            path_list = jsont_path.split('/')[1:]
            path = ''
            for schema in enumerate(pass_on_schemas):
                path = f'{path}/{path_list[schema[0]].split("?")[0]}?{schema[1]}'
            return path

    node = {
        'data': {
            'schema': '',
            'type': '',
            'flags': '',
            'opts': '',
            'status': '',
            'path': '',
            'text': '',
            'description': '',
        },
    }
    node['data']['text'] = jsont['name']
    if jsont.get('description') is not None:
        node['data']['description'] = jsont['description'].replace('\\n', '\n')
    else:
        node['data']['description'] = jsont['name']
    if pass_on_schemas is None:
        pass_on_schemas = []
    if jsont.get('name') == module:
        node['data']['schema'] = 'module'
    elif jsont.get('schema_type') is not None:
        node['data']['schema'] = jsont['schema_type']
        if jsont['schema_type'] not in ['choice', 'case']:
            pass_on_schemas.append(jsont['schema_type'])
    if jsont.get('type') is not None:
        node['data']['type'] = jsont['type']
    elif jsont.get('schema_type') is not None:
        node['data']['type'] = jsont['schema_type']
    if jsont.get('flags') is not None and jsont['flags'].get('config') is not None:
        if jsont['flags']['config']:
            node['data']['flags'] = 'config'
        else:
            node['data']['flags'] = 'no config'
    if jsont.get('options') is not None:
        node['data']['opts'] = jsont['options']
    if jsont.get('status') is not None:
        node['data']['status'] = jsont['status']
    if jsont.get('path') is not None:
        path_list = jsont['path'].split('/')[1:]
        path = ''
        for path_part in path_list:
            path = f'{path}/{path_part.split("?")[0]}'
        node['data']['path'] = path
        last = None
        sensor_path = path
        for prefix in re.findall(r'/[^:]+:', sensor_path):
            if prefix != last:
                last = prefix
                sensor_path = sensor_path.replace(prefix, f'/{imp_inc_map.get(prefix[1:-1], "/")}:', 1)
                sensor_path = sensor_path.replace(prefix, '/')
        node['data']['sensor_path'] = sensor_path
    if jsont['name'] != module and jsont.get('children') is None or len(jsont['children']) == 0:
        if jsont.get('path') is not None:
            if augments:
                node['data']['show_node_path'] = jsont['path']
            else:
                path_list = jsont['path'].split('/')[1:]
                path = ''
                for schema in enumerate(pass_on_schemas):
                    path = f'{path}/{path_list[schema[0]].split("?")[0]}?{schema[1]}'
                node['data']['show_node_path'] = path
                pass_on_schemas.pop()
    elif jsont.get('children') is not None:
        if jsont.get('path') is not None:
            node['data']['show_node_path'] = _create_node_path(jsont.get('path'))
        node['children'] = []
        for child in jsont['children']:
            node['children'].append(build_tree(child, module, imp_inc_map, pass_on_schemas, augments))
        if len(pass_on_schemas) != 0 and jsont.get('schema_type') not in ['choice', 'case']:
            pass_on_schemas.pop()

    return node


def get_type_str(json):
    """
    Recreates json as str
    :param json: input json
    :return: json string.
    """
    type_str = ''
    if json.get('type') is not None:
        type_str += json['type']
    for key, val in json.items():
        if key == 'type':
            continue
        if key == 'typedef':
            type_str += get_type_str(val)
        else:
            if isinstance(val, list) or isinstance(val, dict):
                type_str += f' {"{"} {",".join(str(i) for i in val)} {"}"}'
            else:
                type_str += f' {"{"} {val} {"}"}'
    return type_str


def get_dependencies_dependents_data(
    module_data: dict,
    submodules_allowed: bool,
    allowed_organizations: list,
    rfc_allowed: bool,
):
    """
    Get data saved in our datastore (= Redis) based on values defined in 'module_data' dict.
    After getting module detail apply filter which are defined by other method arguments.

    Arguments:
        :param module_data              (dict) Dictionary with basic module details (name, revision, schema)
        :param submodules_allowed       (bool) Whether submodules are allowed
        :param allowed_organizations    (list) List of allowed organizations
        :param rfc_allowed              (bool) Whether RFCs are allowed
    """
    module_detail = module_details(module_data['name'], module_data.get('revision'), True)
    assert isinstance(module_detail, dict)
    if 'warning' in module_detail:
        return module_detail
    module_detail = module_detail['metadata']
    assert isinstance(module_detail, dict)
    module_type = module_detail.get('module-type')
    if not module_type:
        bp.logger.warning(
            f'module {module_detail.get("name")}@{module_detail.get("revision")} does not contain module-type',
        )
    if module_type == 'submodule' and not submodules_allowed:
        return None
    if len(allowed_organizations) > 0 and module_detail['organization'] not in allowed_organizations:
        return None
    if module_detail.get('maturity-level', '') == 'ratified' and not rfc_allowed:
        return None

    child = {
        'name': module_detail['name'],
        'revision': module_detail['revision'],
        'organization': module_detail['organization'],
        'reference': module_detail.get('reference', ''),
        'maturity-level': module_detail.get('maturity-level', ''),
    }
    return child
