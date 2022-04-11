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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import json
import os
import re

import utility.log as log
from api.views.yangSearch.elkSearch import ElkSearch
from flask import Blueprint, abort
from flask import current_app as app
from flask import jsonify, make_response, request
from pyang import plugin
from utility.yangParser import create_context


class YangSearch(Blueprint):

    def __init__(self, name, import_name, static_folder=None, static_url_path=None, template_folder=None,
                 url_prefix=None, subdomain=None, url_defaults=None, root_path=None):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder, url_prefix, subdomain,
                         url_defaults, root_path)
        # ordering important for frontend to show metadata in correct order
        self.order = \
            {
                'name': 1,
                'revision': 2,
                'organization': 3,
                'ietf': 4,
                'ietf-wg': 1,
                'namespace': 5,
                'schema': 6,
                'generated-from': 7,
                'maturity-level': 8,
                'document-name': 9,
                'author-email': 10,
                'reference': 11,
                'module-classification': 12,
                'compilation-status': 13,
                'compilation-result': 14,
                'prefix': 15,
                'yang-version': 16,
                'description': 17,
                'contact': 18,
                'module-type': 19,
                'belongs-to': 20,
                'tree-type': 21,
                'yang-tree': 22,
                'expires': 23,
                'expired': 24,
                'submodule': 25,
                'dependencies': 26,
                'dependents': 27,
                'semantic-version': 28,
                'derived-semantic-version': 29,
                'implementations': 30,
                'implementation': 1,
                'vendor': 1,
                'platform': 2,
                'software-version': 3,
                'software-flavor': 4,
                'os-version': 5,
                'feature-set': 6,
                'os-type': 7,
                'conformance-type': 8
            }


bp = YangSearch('yangSearch', __name__)


@bp.record
def init_logger(state):
    bp.LOGGER = log.get_logger('yang-search', '{}/yang.log'.format(state.app.config.d_logs))


@bp.before_request
def set_config():
    global ac
    ac = app.config

# ROUTE ENDPOINT DEFINITIONS


@bp.route('/tree/<module_name>', methods=['GET'])
def tree_module(module_name):
    """
    Generates yang tree view of the module.
    :param module_name: Module for which we are generating the tree.
    :return: json response with yang tree
    """
    return tree_module_revision(module_name, None)


@bp.route('/tree/<module_name>@<revision>', methods=['GET'])
def tree_module_revision(module_name, revision):
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
            # get latest revision of provided module
            revision = revisions[0]

        path_to_yang = '{}/{}@{}.yang'.format(ac.d_save_file_dir, module_name, revision)
        plugin.plugins = []
        plugin.init([])
        ctx = create_context('{}'.format(ac.d_yang_models_dir))
        ctx.opts.lint_namespace_prefixes = []
        ctx.opts.lint_modulename_prefixes = []

        module_context = {}
        for p in plugin.plugins:
            p.setup_ctx(ctx)
        try:
            with open(path_to_yang, 'r') as f:
                module_context = ctx.add_module(path_to_yang, f.read())
        except Exception:
            msg = 'File {} was not found'.format(path_to_yang)
            bp.LOGGER.exception(msg)
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
        json_ytree = ac.d_json_ytree
        yang_tree_file_path = '{}/{}@{}.json'.format(json_ytree, module_name, revision)
        response['maturity'] = get_module_data('{}@{}/{}'.format(module_name, revision,
                                                                 organization)).get('maturity-level', '').upper()
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
                    jstree_json = dict()
                    jstree_json['data'] = [data_nodes]
                    if json_tree.get('rpcs') is not None:
                        rpcs = dict()
                        rpcs['name'] = json_tree['prefix'] + ':rpcs'
                        rpcs['children'] = json_tree['rpcs']
                        jstree_json['data'].append(build_tree(rpcs, module_name, import_include_map))
                    if json_tree.get('notifications') is not None:
                        notifs = dict()
                        notifs['name'] = json_tree['prefix'] + ':notifs'
                        notifs['children'] = json_tree['notifications']
                        jstree_json['data'].append(build_tree(notifs, module_name, import_include_map))
                    if json_tree.get('augments') is not None:
                        augments = dict()
                        augments['name'] = json_tree['prefix'] + ':augments'
                        augments['children'] = []
                        for aug in json_tree.get('augments'):
                            aug_info = dict()
                            aug_info['name'] = aug['augment_path']
                            aug_info['children'] = aug['augment_children']
                            augments['children'].append(aug_info)
                        jstree_json['data'].append(build_tree(augments, module_name, import_include_map, augments=True))
            except Exception as e:
                alerts.append("Failed to read YANG tree data for {}@{}/{}, {}".format(module_name, revision,
                                                                                      organization, e))
        else:
            alerts.append('YANG Tree data does not exist for {}@{}/{}'.format(module_name, revision, organization))
    if jstree_json is None:
        response['jstree_json'] = dict()
        alerts.append('Json tree could not be generated')
    else:
        response['jstree_json'] = jstree_json

    response['module'] = '{}@{}'.format(module_name, revision)
    response['warning'] = alerts

    return make_response(jsonify(response), 200)


@bp.route('/impact-analysis', methods=['POST'])
def impact_analysis():
    if not request.json:
        abort(400, description='No input data')
    payload = request.json
    bp.LOGGER.info('Running impact analysis with following payload {}'.format(payload))
    name = payload.get('name')
    revision = payload.get('revision')
    allowed_organizations = payload.get('organizations', [])
    rfc_allowed = payload.get('allow-rfc', True)
    submodules_allowed = payload.get('allow-submodules', True)
    graph_directions = ['dependents', 'dependencies']
    graph_direction = payload.get('graph-direction', graph_directions)
    for direction in graph_direction:
        if direction not in graph_directions:
            abort(400, 'only list of [{}] are allowed as graph directions'.format(', '.join(graph_directions)))
    # GET module details
    response = {}

    searched_module = module_details(name, revision, True)['metadata']
    response['name'] = searched_module['name']
    response['revision'] = searched_module['revision']
    response['organization'] = searched_module['organization']
    response['document-name'] = searched_module.get('reference', '')
    response['maturity-level'] = searched_module.get('maturity-level', '')
    response['dependents'] = []
    response['dependencies'] = []
    if 'dependents' in graph_directions:
        for dependent in searched_module.get('dependents', []):
            response['dependents'] += filter(None, [get_dependencies_dependents_data(dependent, submodules_allowed,
                                                                                     allowed_organizations,
                                                                                     rfc_allowed)])

    if 'dependencies' in graph_directions:
        for dependency in searched_module.get('dependencies', []):
            response['dependencies'] += filter(None, [get_dependencies_dependents_data(dependency, submodules_allowed,
                                                                                       allowed_organizations,
                                                                                       rfc_allowed)])

    return make_response(jsonify(response), 200)


@bp.route('/search', methods=['POST'])
def search():
    if not request.json:
        abort(400, description='No input data')
    payload = request.json
    bp.LOGGER.info('Running search with following payload {}'.format(payload))
    searched_term = payload.get('searched-term')
    if searched_term is None or searched_term == '' or len(searched_term) < 2 or not isinstance(searched_term, str):
        abort(400, description='You have to write "searched-term" key containing at least 2 characters')
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
    __output_columns = [
        'name',
        'revision',
        'schema-type',
        'path',
        'module-name',
        'origin',
        'organization',
        'maturity',
        'dependents',
        'compilation-status',
        'description'
    ]
    response = {}
    case_sensitive = isBoolean(payload, 'case-sensitive', False)
    terms_regex = isStringOneOf(payload, 'type', 'term', ['term', 'regexp'])
    include_mibs = isBoolean(payload, 'include-mibs', False)
    latest_revision = isBoolean(payload, 'latest-revision', True)
    searched_fields = isListOneOf(payload, 'searched-fields', ['module', 'argument', 'description'])
    yang_versions = isListOneOf(payload, 'yang-versions', ['1.0', '1.1'])
    schema_types = isListOneOf(payload, 'schema-types', __schema_types)
    output_columns = isListOneOf(payload, 'output-columns', __output_columns)
    sub_search = eachKeyIsOneOf(payload, 'sub-search', __output_columns)
    elk_search = ElkSearch(searched_term, case_sensitive, searched_fields, terms_regex, schema_types, ac.d_logs,
                           ac.es, latest_revision, app.redisConnection, include_mibs, yang_versions, output_columns,
                           __output_columns, sub_search)
    elk_search.construct_query()
    response['rows'] = elk_search.search()
    response['warning'] = elk_search.alerts()
    return make_response(jsonify(response), 200)


@bp.route('/completions/<type>/<pattern>', methods=['GET'])
def get_services_list(type: str, pattern: str):
    """
    Provides auto-completions for search bars on web pages impact_analysis
    and module_details.
    :param type: Type of what we are auto-completing, module or org.
    :param pattern: Pattern which we are writing in bar.
    :return: auto-completion results
    """
    res = []

    if type is None or (type != 'organization' and type != 'module'):
        return make_response(jsonify(res), 200)

    if not pattern:
        return make_response(jsonify(res), 200)

    try:
        with open(os.path.join(os.environ['BACKEND'], 'api/json/es/completion.json'), 'r') as f:
            completion = json.load(f)

            completion['query']['bool']['must'][0]['term'] = {type.lower(): pattern.lower()}
            completion['aggs']['groupby_module']['terms']['field'] = '{}.keyword'.format(type.lower())
            rows = ac.es.search(index='modules', body=completion,
                                size=0)['aggregations']['groupby_module']['buckets']

            for row in rows:
                res.append(row['key'])

    except Exception:
        bp.LOGGER.exception('Failed to get completions result')
        return make_response(jsonify(res), 400)
    return make_response(jsonify(res), 200)


@bp.route('/show-node/<name>/<path:path>', methods=['GET'])
def show_node(name, path):
    """
    View for show_node page, which provides context for show_node.html
    Shows description for yang modules.
    :param name: Takes first argument from url which is module name.
    :param path: Path for node.
    :return: returns json to show node
    """
    return show_node_with_revision(name, path, None)


@bp.route('/show-node/<name>/<path:path>/<revision>', methods=['GET'])
def show_node_with_revision(name, path, revision):
    """
    View for show_node page, which provides context for show_node.html
    Shows description for yang modules.
    :param name: Takes first argument from url which is module name.
    :param path: Path for node.
    :param revision: revision for yang module, if specified.
    :return: returns json to show node
    """
    properties = []
    app.logger.info('Show node on path - show-node/{}/{}/{}'.format(name, path, revision))
    path = '/{}'.format(path)
    try:
        with open(os.path.join(os.environ['BACKEND'], 'api/json/es/show_node.json'), 'r') as f:
            query = json.load(f)

        if name == '':
            abort(400, description='You must specify a "name" argument')

        if path == '':
            abort(400, description='You must specify a "path" argument')

        if revision is None:
            bp.LOGGER.warning('Revision not submitted getting latest')

        if not revision:
            revision = get_latest_module(name)
        query['query']['bool']['must'][0]['match_phrase']['module.keyword']['query'] = name
        query['query']['bool']['must'][1]['match_phrase']['path']['query'] = path
        query['query']['bool']['must'][2]['match_phrase']['revision']['query'] = revision
        hits = ac.es.search(index='yindex', body=query)['hits']['hits']
        if len(hits) == 0:
            abort(404, description='Could not find data for {}@{} at {}'.format(name, revision, path))
        else:
            result = hits[0]['_source']
            properties = json.loads(result['properties'])
    except Exception as e:
        abort(400, description='Module and path that you specified can not be found - {}'.format(e))
    return make_response(jsonify(properties), 200)


@bp.route('/module-details/<module>', methods=['GET'])
def module_details_no_revision(module: str):
    """
    Search for data saved in our datastore (ConfD/Redis) based on specific module with no revision.
    Revision will be the latest one that we have.
    :return: returns json with yang-catalog saved metdata of a specific module
    """
    return module_details(module, None)


@bp.route('/module-details/<module>@<revision>', methods=['GET'])
def module_details(module: str, revision: str, json_data=False, warnings=False):
    """
    Search for data saved in our datastore (ConfD/Redis) based on specific module with some revision.
    Revision can be empty called from endpoint /module-details/<module> definition module_details_no_revision.
    :return: returns json with yang-catalog saved metdata of a specific module
    """
    if module == '' or module is None:
        abort(400, description='No module name provided')
    if revision is not None and (len(revision) != 10 or re.match(r'\d{4}[-/]\d{2}[-/]\d{2}', revision) is None):
        abort(400, description='Revision provided has wrong format - please use "YYYY-MM-DD" format')

    elk_response = get_modules_revision_organization(module, None, warnings)
    if 'warning' in elk_response:
        return elk_response
    else:
        revisions, organization = elk_response
    if len(revisions) == 0:
        if warnings:
            return {'warning': 'module {} does not exists in API'.format(module)}
        else:
            abort(404, description='Provided module does not exist')

    if revision is None:
        # get latest revision of provided module
        revision = revisions[0]

    resp = \
        {
            'current-module': '{}@{}.yang'.format(module, revision),
            'revisions': revisions
        }

    # get module from Redis
    module_key = '{}@{}/{}'.format(module, revision, organization)
    module_data = app.redisConnection.get_module(module_key)
    if module_data == '{}':
        if warnings:
            return {'warning': 'module {} does not exists in API'.format(module_key)}
        else:
            abort(404, description='Provided module does not exist')
    else:
        module_data = json.loads(module_data)
    resp['metadata'] = module_data
    if json_data:
        return resp
    else:
        return make_response(jsonify(resp), 200)


@bp.route('/yang-catalog-help', methods=['GET'])
def get_yang_catalog_help():
    """
    Iterate through all the different descriptions of the yang-catalog yang module and provide
    json with key as an argument of the container/list/leaf and value containing help-text. If
    there is something inside of container/list that container will not only contain help-text
    but other container/list/leaf under this statement again as a dictionary
    :return: returns json with yang-catalog help text
    """
    revision = get_latest_module('yang-catalog')
    query = json.load(open(os.path.join(os.environ['BACKEND'], 'api/json/es/get_yang_catalog_yang.json'), 'r'))
    query['query']['bool']['must'][1]['match_phrase']['revision']['query'] = revision
    yang_catalog_module = ac.es.search(index='yindex', body=query, size=10000)['hits']['hits']
    module_details_data = {}
    skip_statement = ['typedef', 'grouping', 'identity']
    for m in yang_catalog_module:
        help_text = ''
        m = m['_source']
        paths = m['path'].split('/')[4:]
        if 'yc:vendors?container/' in m['path'] or m['statement'] in skip_statement or len(paths) == 0 \
                or 'platforms' in m['path']:
            continue
        if m.get('argument') is not None:
            if m.get('description') is not None:
                help_text = m.get('description').replace('\\n', '\n')
            nprops = json.loads(m['properties'])
            for prop in nprops:
                if prop.get('type') is not None:
                    if prop.get('type')['has_children']:
                        for child in prop['type']['children']:
                            if child.get('enum') and child['enum']['has_children']:
                                for echild in child['enum']['children']:
                                    if echild.get('description') is not None:
                                        description = echild['description']['value'].replace('\\n', '\n').replace('\n', "<br/>\r\n")
                                        help_text += '<br/>\r\n<br/>\r\n{}: {}'.format(child['enum']['value'],
                                                                                       description)

                break
        paths.reverse()

        update_dictionary_recursively(module_details_data, paths, help_text)
    return make_response(jsonify(module_details_data), 200)


# HELPER DEFINITIONS
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
        module_details_data[last_path_data] = {'ordering': bp.order.get(last_path_data, '')}
        update_dictionary_recursively(module_details_data[last_path_data], path_to_populate, help_text)


def get_modules_revision_organization(module_name, revision=None, warnings=False):
    """
    Get list of revision of module_name that we have in our database and organization as well
    :param module_name: module name of searched module
    :param revision: revision of searched module (can be None)
    :return: tuple (list of revisions and organization) of specified module name
    """
    try:
        if revision is None:
            query = elasticsearch_descending_module_querry(module_name)
        else:
            query = \
                {
                    "query": {
                        "bool": {
                            "must": [{
                                "match_phrase": {
                                    "module.keyword": {
                                        "query": module_name
                                    }
                                }
                            }, {
                                "match_phrase": {
                                    "revision": {
                                        "query": revision
                                    }
                                }
                            }]
                        }
                    }
                }
        hits = ac.es.search(index='modules', body=query, size=100)['hits']['hits']
        organization = hits[0]['_source']['organization']
        revisions = []
        for hit in hits:
            hit = hit['_source']
            revisions.append(hit['revision'])
        return revisions, organization
    except Exception:
        name_rev = '{}@{}'.format(module_name, revision) if revision else module_name
        bp.LOGGER.exception('Failed to get revisions and organization for {}'.format(name_rev))
        if warnings:
            return {'warning': 'Failed to find module {} in Elasticsearch'.format(name_rev)}
        else:
            abort(404, 'Failed to get revisions and organization for {} - please use module that exists'
                  .format(name_rev))


def get_latest_module(module_name):
    """
    Gets latest version of module.
    :param module_name: module name of searched module
    :return: latest revision
    """
    try:
        query = elasticsearch_descending_module_querry(module_name)
        rev_org = ac.es.search(index='modules', body=query)['hits']['hits'][0]['_source']
        return rev_org['revision']
    except Exception as e:
        bp.LOGGER.exception('Failed to get revision for {}'.format(module_name))
        abort(400, 'Failed to get revision for {} - please use module that exists'.format(module_name))


def elasticsearch_descending_module_querry(module_name):
    """
    Return query to search for specific module in descending order in elasticsearch based on module name
    """
    return {
        "query": {
            "bool": {
                "must": [{
                    "match_phrase": {
                        "module.keyword": {
                            "query": module_name
                        }
                    }
                }]
            }
        },
        "sort": [
            {"revision": {"order": "desc"}}
        ]
    }


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


def isBoolean(payload, key, default):
    obj = payload.get(key, default)
    if isinstance(obj, bool):
        return obj
    else:
        abort(400, 'Value of key {} must be boolean'.format(key))


def isStringOneOf(payload, key, default, one_of):
    obj = payload.get(key, default)
    if isinstance(obj, str):
        if obj not in one_of:
            abort(400, 'Value of key {} must be string from following list {}'.format(key, one_of))
        return obj
    else:
        abort(400, 'Value of key {} must be string from following list {}'.format(key, one_of))


def isListOneOf(payload, key, default):
    objs = payload.get(key, default)
    if str(objs).lower() == 'all':
        return default
    one_of = default
    if isinstance(objs, list):
        if len(objs) == 0:
            return default
        for obj in objs:
            if obj not in one_of:
                abort(400, 'Value of key {} must be string from following list {}'.format(key, one_of))
        return objs
    else:
        abort(400, 'Value of key {} must be string from following list {}'.format(key, one_of))


def eachKeyIsOneOf(payload, payload_key, keys):
    rows = payload.get(payload_key, [])
    if isinstance(rows, list):
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    abort(400, 'key {} must be string from following list {} in {}'.format(key, keys, payload_key))
    else:
        abort(400, 'Value of key {} must be string from following list {}'.format(payload_key, keys))
    return rows


def get_module_data(module_key: str):
    bp.LOGGER.info('searching for module {}'.format(module_key))
    module_data = app.redisConnection.get_module(module_key)
    if module_data == '{}':
        abort(404, description='Provided module does not exist')
    else:
        module_data = json.loads(module_data)
    return module_data


def build_tree(jsont: dict, module: str, imp_inc_map, pass_on_schemas=None, augments=False):
    """ Builds data for yang_tree.html, takes json and recursively writes out it's children.

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
                path = '{}/{}?{}'.format(path, path_list[schema[0]].split('?')[0], schema[1])
            return path

    node = dict()
    node['data'] = {
        'schema': '',
        'type': '',
        'flags': '',
        'opts': '',
        'status': '',
        'path': '',
        'text': '',
        'description': ''
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
            path = '{}/{}'.format(path, path_part.split('?')[0])
        node['data']['path'] = path
        last = None
        sensor_path = path
        for prefix in re.findall(r'/[^:]+:', sensor_path):
            if prefix != last:
                last = prefix
                sensor_path = sensor_path.replace(prefix, '/{}:'.format(imp_inc_map.get(prefix[1:-1], '/')), 1)
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
                    path = '{}/{}?{}'.format(path, path_list[schema[0]].split('?')[0], schema[1])
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
                type_str += ' {} {} {}'.format('{', ','.join([str(i) for i in val]), '}')
            else:
                type_str += ' {} {} {}'.format('{', val, '}')
    return type_str


def get_dependencies_dependents_data(module_data, submodules_allowed, allowed_organizations, rfc_allowed):
    module_detail = module_details(module_data['name'], module_data.get('revision'), True, True)
    if 'warning' in module_detail:
        return module_detail
    else:
        module_detail = module_detail['metadata']
    module_type = module_detail.get('module-type', '')
    if module_type == '':
        bp.LOGGER.warning('module {}@{} does not container module type'.format(module_detail.get('name'),
                                                                               module_detail.get('revision')))
    if module_type == 'submodule' and not submodules_allowed:
        return None
    child = {}
    child['name'] = module_detail['name']
    child['revision'] = module_detail['revision']
    child['organization'] = module_detail['organization']
    if len(allowed_organizations) > 0 and child['organization'] not in allowed_organizations:
        return None
    if not rfc_allowed and module_detail.get('maturity-level', '') == 'ratified':
        return None
    child['document-name'] = module_detail.get('reference', '')
    child['maturity-level'] = module_detail.get('maturity-level', '')
    return child
