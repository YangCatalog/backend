# Copyright The IETF Trust 202, All Rights Reserved
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
__copyright__ = "Copyright The IETF Trust 202, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import json

import re
from flask import Blueprint, make_response, jsonify, abort

import utility.log as log
from api.globalConfig import yc_gc
from utility.util import get_curr_dir


class YangSearch(Blueprint):

    def __init__(self, name, import_name, static_folder=None, static_url_path=None, template_folder=None,
                 url_prefix=None, subdomain=None, url_defaults=None, root_path=None):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder, url_prefix, subdomain,
                         url_defaults, root_path)
        self.LOGGER = log.get_logger('healthcheck', '{}/healthcheck.log'.format(yc_gc.logs_dir))


app = YangSearch('yangSearch', __name__)


### ROUTE ENDPOINT DEFINITIONS ###
@app.route('/completions/<type>/<pattern>', methods=['GET'])
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
        with open(get_curr_dir(__file__) + '/../../json/es/completion.json', 'r') as f:
            completion = json.load(f)

            completion['query']['bool']['must'][0]['term'] = {type.lower(): pattern.lower()}
            completion['aggs']['groupby_module']['terms']['field'] = '{}.keyword'.format(type.lower())
            rows = yc_gc.es.search(index='modules', doc_type='modules', body=completion,
                                        size=0)['aggregations']['groupby_module']['buckets']

            for row in rows:
                res.append(row['key'])

    except:
        app.LOGGER.exception("Failed to get completions result")
        return make_response(jsonify(res), 400)
    return make_response(jsonify(res), 200)

@app.route('/show-node/<name>/<path:path>', methods=['GET'])
def show_node(name, path):
    """
    View for show_node page, which provides context for show_node.html
    Shows description for yang modules.
    :param name: Takes first argument from url which is module name.
    :param path: Path for node.
    :return: returns json to show node
    """
    return show_node_with_revision(name, path, None)

@app.route('/show-node/<name>/<path:path>/<revision>', methods=['GET'])
def show_node_with_revision(name, path, revision):
    """
    View for show_node page, which provides context for show_node.html
    Shows description for yang modules.
    :param name: Takes first argument from url which is module name.
    :param path: Path for node.
    :param revision: revision for yang module, if specified.
    :return: returns json to show node
    """
    context = dict()
    yc_gc.LOGGER.info('Show node on path - show-node/{}/{}/{}'.format(name, path, revision))
    path = '/{}'.format(path)
    try:
        with open(get_curr_dir(__file__) + '/../../json/es/completion.json', 'r') as f:
            query = json.load(f)

        if name == '':
            abort(400, description='You must specify a "name" argument')

        if path == '':
            abort(400, description='You must specify a "path" argument')

        if revision is None:
            app.LOGGER.warning("Revision not submitted getting latest")

        if not revision:
            revision = get_latest_module(name)
        query['query']['bool']['must'][0]['match_phrase']['module.keyword']['query'] = name
        query['query']['bool']['must'][1]['match_phrase']['path']['query'] = path
        query['query']['bool']['must'][2]['match_phrase']['revision']['query'] = revision
        hits = yc_gc.es.search(index='yindex', doc_type='modules', body=query)['hits']['hits']
        if len(hits) == 0:
            abort(404, description='Could not find data for {}@{} at {}'.format(name, revision, path))
        else:
            result = hits[0]['_source']
            context = result['path']
            properties = json.loads(result['properties'])
    except:
        abort(400, description='Module and path that you specified can not be found')
    return make_response(jsonify(context), 200)


@app.route('/module-details/<module>', methods=['GET'])
def module_details_no_revision(module: str):
    """
    Search for data saved in our datastore (confd/redis) based on specific module with no revision.
    Revision will be the latest one that we have.
    :return: returns json with yang-catalog saved metdata of a specific module
    """
    return module_details(module, None)


@app.route('/module-details/<module>@<revision>', methods=['GET'])
def module_details(module: str, revision:str):
    """
    Search for data saved in our datastore (confd/redis) based on specific module with some revision.
    Revision can be empty called from endpoint /module-details/<module> definition module_details_no_revision.
    :return: returns json with yang-catalog saved metdata of a specific module
    """
    if module == '' or module is None:
        abort(400, description='No module name provided')
    if revision is not None and (len(revision) != 10 or re.match(r'\d{4}[-/]\d{2}[-/]\d{2}', revision) is None):
        abort(400, description='Revision provided has wrong format please use "YYYY-MM-DD" format')

    revisions, organization = get_modules_revision_organization(module, revision)
    if len(revisions) == 0:
        abort(404, description='Provided module does not exist')

    if revision is None:
        # get latest revision of provided module
        revision = revisions[0]

    resp =\
        {
            'current-module': '{}@{}.yang'.format(module, revision),
            'revisions': revisions
        }

    # get module from redis
    module_data = yc_gc.redis.get("{}@{}/{}".format(module, revision, organization))
    if module_data is None:
        abort(404, description='Provided module does not exist')
    else:
        module_data = module_data.decode('utf-8')
        module_data = json.loads(module_data)
    resp['metadata'] = module_data
    return make_response(jsonify(resp), 200)


@app.route('/yang-catalog-help', methods=['GET'])
def get_yang_catalog_help():
    """
    Iterate through all the different descriptions of the yang-catalog yang module and provide
    json with key as an argument of the container/list/leaf and value containing help-text. If
    there is something inside of container/list that container will not only contain help-text
    but other container/list/leaf under this statement again as a dictionary
    :return: returns json with yang-catalog help text
    """
    revision = get_latest_module('yang-catalog')
    query = json.load(open('search/json/get_yang_catalog_yang.json', 'r'))
    query['query']['bool']['must'][1]['match_phrase']['revision']['query'] = revision
    yang_catalog_module = yc_gc.es.search(index='yindex', doc_type='modules', body=query, size=10000)['hits']['hits']
    module_details = {}
    skip_statement = ['typedef', 'grouping', 'identity']
    for m in yang_catalog_module:
        help_text = ''
        m = m['_source']
        paths = m['path'].split('/')[4:]
        if 'yc:vendors?container/' in m['path'] or m['statement'] in skip_statement or len(paths) == 0\
                or 'platforms' in m['path']:
            continue
        if m.get('argument') is not None:
            if m.get('description') is not None:
                help_text = m.get('description')
            nprops = json.loads(m['properties'])
            for prop in nprops:
                if prop.get('type') is not None:
                    if prop.get('type')['has_children']:
                        for child in prop['type']['children']:
                            if child.get('enum') and child['enum']['has_children']:
                                for echild in child['enum']['children']:
                                    if echild.get('description') is not None:
                                        description = echild['description']['value'].replace('\n', "<br/>\r\n")
                                        help_text += "<br/>\r\n<br/>\r\n{} : {}".format(child['enum']['value'],
                                                                                        description)

                break
        paths.reverse()

        update_dictionary_recursively(module_details, paths, help_text)
    return make_response(jsonify(module_details), 200)


### HELPER DEFINITIONS ###
def update_dictionary_recursively(module_details: dict, path_to_populate: list, help_text: str):
    """
    Update dictionary. Recursively create dictionary of dictionaries based on the path which are
    nested keys of dictionary and each key has a sibling help-text key which contains the help_text
    string
    :param module_details: dictionary that we are currently updating recursively
    :param path_to_populate: list of keys used in dictionary
    :param help_text: text describing each module detail
    """
    if len(path_to_populate) == 0:
        module_details['help-text'] = help_text
        return
    pop = path_to_populate.pop()
    pop = pop.split(":")[-1].split('?')[0]
    if module_details.get(pop):
        update_dictionary_recursively(module_details[pop], path_to_populate, help_text)
    else:
        module_details[pop] = {}
        update_dictionary_recursively(module_details[pop], path_to_populate, help_text)

def get_modules_revision_organization(module_name, revision=None):
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
        hits = yc_gc.es.search(index='modules', doc_type='modules', body=query, size=100)['hits']['hits']
        organization = hits[0]['_source']['organization']
        revisions = []
        for hit in hits:
            hit = hit['_source']
            revisions.append(hit)
        return revisions, organization
    except Exception as e:
        raise Exception("Failed to get revisions and organization for {}@{}: {}".format(module_name, revision, e))


def get_latest_module(module_name):
    """
    Gets latest version of module.
    :param module_name: module name of searched module
    :return: latest revision
    """
    try:
        query = elasticsearch_descending_module_querry(module_name)
        rev_org = yc_gc.es.search(index='modules', doc_type='modules', body=query)['hits']['hits'][0]['_source']
        return rev_org['revision']
    except Exception as e:
        raise Exception("Failed to get revision for {}: {}".format(module_name, e))


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
    pop = pop.split(":")[-1].split('?')[0]
    if updated_dictionary.get(pop):
        update_dictionary(updated_dictionary[pop], list_dictionaries, help_text)
    else:
        updated_dictionary[pop] = {}
        update_dictionary(updated_dictionary[pop], list_dictionaries, help_text)