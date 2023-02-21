# Copyright The IETF Trust 2020, All Rights Reserved
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
__copyright__ = 'Copyright The IETF Trust 2020, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import collections
import io
import json
import os
import typing as t
from operator import contains, eq

import jinja2
from flask.blueprints import Blueprint
from flask.globals import request
from flask.wrappers import Response
from flask_deprecate import deprecate_route
from markupsafe import escape
from pyang import plugin
from pyang.plugins.tree import emit_tree
from werkzeug.exceptions import abort

from api.my_flask import app
from utility.yangParser import create_context


class RedisSearch(Blueprint):
    def __init__(
        self,
        name,
        import_name,
        static_folder=None,
        static_url_path=None,
        template_folder=None,
        url_prefix=None,
        subdomain=None,
        url_defaults=None,
        root_path=None,
    ):
        super().__init__(
            name,
            import_name,
            static_folder,
            static_url_path,
            template_folder,
            url_prefix,
            subdomain,
            url_defaults,
            root_path,
        )


bp = RedisSearch('redisSearch', __name__)


@bp.before_request
def set_config():
    global ac
    ac = app.config


@bp.route('/fast', methods=['POST'])
@deprecate_route(message='Use "/yang-search/v2/search" instead')
def fast_search():
    return Response('This endpoint is deprecated. Use "/yang-search/v2/search" instead.')


@bp.route('/search/<path:value>', methods=['GET'])
def search(value: str):
    """Search for a specific leaf from yang-catalog.yang module in modules
    branch. The key searched is defined in @module_keys variable.

    Argument:
        :param value    (str) path that contains one of the @module_keys and
            ends with /value searched for
        :return response to the request.
    """
    path = value
    app.logger.info('Searching for {}'.format(value))
    split = value.split('/')[:-1]
    key = '/'.join(value.split('/')[:-1])
    value = value.split('/')[-1]
    module_keys = [
        'ietf/ietf-wg',
        'maturity-level',
        'document-name',
        'author-email',
        'compilation-status',
        'namespace',
        'conformance-type',
        'module-type',
        'organization',
        'yang-version',
        'name',
        'revision',
        'tree-type',
        'belongs-to',
        'generated-from',
        'expires',
        'expired',
        'prefix',
        'reference',
    ]
    for module_key in module_keys:
        if key == module_key:
            data = modules_data().get('module')
            if data is None:
                abort(404, description='No module found in Redis database')
            passed_data = []
            for module in data:
                count = -1
                process(module, passed_data, value, module, split, count)

            if len(passed_data) > 0:
                modules = json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(json.dumps(passed_data))
                return {'yang-catalog:modules': {'module': modules}}
            else:
                abort(404, description='No module found using provided input data')
    abort(400, description='Search on path {} is not supported'.format(path))


@bp.route('/search-filter/<leaf>', methods=['POST'])
def rpc_search_get_one(leaf: str):
    """Get list of values of specified leaf in filtered set of modules. Filter is specified in body of the request."""
    body = request.json
    if body.get('input') is None:
        abort(400, description='body of request need to start with input')

    recursive = body['input'].get('recursive')
    if recursive:
        body['input'].pop('recursive')

    data = rpc_search(body)
    modules = data['yang-catalog:modules']['module']

    if len(modules) == 0:
        abort(404, description='No module found in Redis database')
    output = set()
    resolved = set()
    for module in modules:
        if recursive:
            search_recursive(output, module, leaf, resolved)
        metadata = module.get(leaf)
        if metadata is not None:
            output.add(metadata)
    if len(output) == 0:
        abort(404, description='No module found using provided input data')
    else:
        return {'output': {leaf: list(output)}}


@bp.route('/search-filter', methods=['POST'])
def rpc_search(body: t.Optional[dict] = None):
    """Get all the modules that contains all the leafs with data as provided in body of the request."""
    from_api = False
    if not body:
        body = request.json
        from_api = True
    app.logger.info('Searching and filtering modules based on RPC {}'.format(json.dumps(body)))
    data = modules_data().get('module', {})
    body = body.get('input', {})
    if body:
        matched_modules = []
        operator = contains if body.get('partial') is not None else eq

        def matches(module, body):
            if not isinstance(module, type(body)):
                return False
            if isinstance(body, str):
                return operator(module, body)
            elif isinstance(body, list):
                for i in body:
                    for j in module:
                        if matches(j, i):
                            break
                    else:
                        return False
                return True
            elif isinstance(body, dict):
                for key in body:
                    if not matches(module.get(key), body[key]):
                        break
                else:
                    return True
                return False

        for module in data:
            if matches(module, body):
                matched_modules.append(module)
        if from_api and len(matched_modules) == 0:
            abort(404, description='No modules found with provided input')
        else:
            modules = json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(json.dumps(matched_modules))
            return {'yang-catalog:modules': {'module': modules}}
    else:
        abort(400, description='body request has to start with "input" container')


@bp.route('/contributors', methods=['GET'])
def get_organizations():
    """Loop through all the modules in catalog and create unique set of organizations."""
    orgs = set()
    data = modules_data().get('module', {})
    for module in data:
        if module['organization'] != 'example' and module['organization'] != 'missing element':
            orgs.add(module['organization'])
    orgs = list(orgs)
    return {'contributors': orgs}


@bp.route('/search/vendor/<vendor>', methods=['GET'])
def search_vendor_statistics(vendor: str) -> dict:
    """Search for os-types of <vendor> with corresponding os-versions and platforms.

    Arguments:
        :param vendor   (str) name of the vendor
        :return         (dict) statistics of the vendor's os-types, os-versions and platforms
    """
    app.logger.info('Searching for vendors')
    data = vendors_data(False).get('vendor', {})
    ven_data = None
    for d in data:
        if d['name'] == vendor:
            ven_data = d
            break

    os_type = {}
    if ven_data is not None:
        for plat in ven_data['platforms']['platform']:
            version_list = set()
            os = {}
            for ver in plat['software-versions']['software-version']:
                for flav in ver['software-flavors']['software-flavor']:
                    os[ver['name']] = flav['modules']['module'][0]['os-type']
                    if os[ver['name']] not in os_type:
                        os_type[os[ver['name']]] = {}
                    break
                if ver['name'] not in os_type[os[ver['name']]]:
                    os_type[os[ver['name']]][ver['name']] = set()

                version_list.add(ver['name'])
            for ver in version_list:
                os_type[os[ver]][ver].add(plat['name'])

    result = {}
    for key in os_type.keys():
        result[key] = {}
        for key2 in os_type[key].keys():
            result[key][key2] = list(os_type[key][key2])
    return result


@bp.route('/search/vendors/<path:value>', methods=['GET'])
def search_vendors(value: str) -> dict:
    """Search for a specific vendor, platform, os-type, os-version depending on
    the value sent via API.

    Arguments:
        :param value: (str) path that contains one of the @module_keys and
            ends with /value searched for
        :return       (dict) response to the request.
    """
    original_value = value
    app.logger.info('Searching for specific vendors {}'.format(original_value))
    vendors_data = get_vendors()

    value = '/vendors/{}'.format(value).rstrip('/')
    part_names = ['vendor', 'platform', 'software-version', 'software-flavor']
    parts = {}
    for part_name in part_names[::-1]:
        value, _, parts[part_name] = value.partition('/{}s/{}/'.format(part_name, part_name))
    if not parts['vendor']:
        return vendors_data
    vendors_data = {'vendors': vendors_data}
    previous_part_name = ''
    for part_name in part_names:
        if not (part := parts[part_name]):
            break
        previous_part_name = part_name
        for chunk in vendors_data['{}s'.format(part_name)][part_name]:
            if chunk['name'] == part:
                vendors_data = chunk
                break
        else:
            abort(404, description='No {}s found on path {}'.format(part_name, original_value))
    return {'yang-catalog:{}'.format(previous_part_name): [vendors_data]}


@bp.route('/search/modules/<name>,<revision>,<organization>', methods=['GET'])
def search_module(name: str, revision: str, organization: str) -> dict:
    """Search for a specific module defined with name, revision and organization

    Arguments:
        :param name:            (str) name of the module
        :param revision:        (str) revision of the module in format YYYY-MM-DD
        :param organization:    (str) organization of the module
        :return                 (dict) response to the request with job_id that user can use to
            see if the job is still on or Failed or Finished successfully
    """
    app.logger.info('Searching for module {}, {}, {}'.format(name, revision, organization))
    module_data_redis = app.redisConnection.get_module('{}@{}/{}'.format(name, revision, organization))
    if module_data_redis != '{}':
        return {'module': [json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(module_data_redis)]}
    abort(404, description='Module {}@{}/{} not found'.format(name, revision, organization))


@bp.route('/search/modules', methods=['GET'])
def get_modules():
    """Search for all the modules populated in Redis
    :return response to the request with all the modules
    """
    app.logger.info('Searching for modules')
    data = modules_data()
    if data is None or data == {}:
        abort(404, description='No module is loaded')
    return data


@bp.route('/search/vendors', methods=['GET'])
def get_vendors():
    """Search for all the vendors populated in Redis
    :return response to the request with all the vendors
    """
    app.logger.info('Searching for vendors')
    data = vendors_data()
    if data is None or data == {}:
        abort(404, description='No vendor is loaded')
    return data


@bp.route('/search/catalog', methods=['GET'])
def get_catalog():
    """Search for a all the data populated in Redis
    :return response to the request with all the data (modules and vendors)
    """
    app.logger.info('Searching for catalog data')
    data = catalog_data()
    if data is None or data == {}:
        abort(404, description='No data loaded to YangCatalog')
    else:
        return data


@bp.route('/services/tree/<name>@<revision>.yang', methods=['GET'])
def create_tree(name: str, revision: str) -> str:
    """
    Return yang tree representation of yang module with corresponding module name and revision.

    Arguments:
        :param name     (str) name of the module
        :param revision (str) revision of the module in format YYYY-MM-DD
        :return         (str) preformatted HTML with corresponding data
    """
    path_to_yang = '{}/{}@{}.yang'.format(ac.d_save_file_dir, name, revision)
    plugin.plugins = []
    plugin.init([])
    ctx = create_context('{}:{}'.format(ac.d_yang_models_dir, ac.d_save_file_dir))
    ctx.opts.lint_namespace_prefixes = []
    ctx.opts.lint_modulename_prefixes = []

    for p in plugin.plugins:
        p.setup_ctx(ctx)
    try:
        with open(path_to_yang, 'r') as f:
            a = ctx.add_module(path_to_yang, f.read())
    except FileNotFoundError:
        abort(400, description='File {} was not found'.format(path_to_yang))
    if ctx.opts.tree_path is not None:
        path = ctx.opts.tree_path.split('/')
        if path[0] == '':
            path = path[1:]
    else:
        path = None

    ctx.validate()
    f = io.StringIO()
    emit_tree(ctx, [a], f, ctx.opts.tree_depth, ctx.opts.tree_line_length, path)
    stdout = f.getvalue()
    context = {'title': 'YANG Tree {}@{}'.format(name, revision)}
    if stdout == '' and len(ctx.errors) != 0:
        context['message'] = 'This yang file contains major errors and therefore tree can not be created.'
        return create_bootstrap(context, 'danger.html')
    elif stdout != '' and len(ctx.errors) != 0:
        context['message'] = 'This yang file contains some errors, but tree was created.'
        context['text'] = stdout
        return create_bootstrap(context, 'warning.html')
    elif stdout == '' and len(ctx.errors) == 0:
        context['message'] = 'This yang file does not contain any tree.'
        return create_bootstrap(context, 'info.html')
    else:
        context['text'] = stdout
        return create_bootstrap(context, 'tree.html')


@bp.route('/services/reference/<name>@<revision>.yang', methods=['GET'])
def create_reference(name: str, revision: str) -> str:
    """
    Return reference of yang file with corresponding module name and revision.

    Arguments:
        :param name     (str) name of the module
        :param revision (str) revision of the module in format YYYY-MM-DD
        :return         (str) preformatted HTML with corresponding data
    """
    path_to_yang = '{}/{}@{}.yang'.format(ac.d_save_file_dir, name, revision)
    context = {'title': 'Reference {}@{}'.format(name, revision)}
    try:
        with open(path_to_yang, 'r', encoding='utf-8', errors='strict') as f:
            yang_file_content = escape(f.read())
    except FileNotFoundError:
        context['message'] = 'File {}@{}.yang was not found.'.format(name, revision)
        return create_bootstrap(context, 'danger.html')

    return '<html><body><pre>{}</pre></body></html>'.format(yang_file_content)


# HELPER DEFINITIONS
def filter_using_api(res_row, payload):
    try:
        if 'filter' not in payload or 'module-metadata-filter' not in payload['filter']:
            reject = False
        else:
            reject = False
            keywords = payload['filter']['module-metadata-filter']
            for key, value in keywords.items():
                # Module doesn not contain such key as searched for, then reject
                if res_row['module'].get(key) is None:
                    reject = True
                    break
                if isinstance(res_row['module'][key], dict):
                    # This means the key is either implementations or ietf (for WG)
                    if key == 'implementations':
                        exists = True
                        if res_row['module'][key].get('implementations') is not None:
                            for val in value['implementation']:
                                val_found = False
                                for impl in res_row['module'][key]['implementations']['implementation']:
                                    vendor = impl.get('vendor')
                                    software_version = impl.get('software_version')
                                    software_flavor = impl.get('software_flavor')
                                    platform = impl.get('platform')
                                    os_version = impl.get('os_version')
                                    feature_set = impl.get('feature_set')
                                    os_type = impl.get('os_type')
                                    conformance_type = impl.get('conformance_type')
                                    local_exist = True
                                    if val.get('vendor') is not None:
                                        if vendor != val['vendor']:
                                            local_exist = False
                                    if val.get('software-version') is not None:
                                        if software_version != val['software-version']:
                                            local_exist = False
                                    if val.get('software-flavor') is not None:
                                        if software_flavor != val['software-flavor']:
                                            local_exist = False
                                    if val.get('platform') is not None:
                                        if platform != val['platform']:
                                            local_exist = False
                                    if val.get('os-version') is not None:
                                        if os_version != val['os-version']:
                                            local_exist = False
                                    if val.get('feature-set') is not None:
                                        if feature_set != val['feature-set']:
                                            local_exist = False
                                    if val.get('os-type') is not None:
                                        if os_type != val['os-type']:
                                            local_exist = False
                                    if val.get('conformance-type') is not None:
                                        if conformance_type != val['conformance-type']:
                                            local_exist = False
                                    if local_exist:
                                        val_found = True
                                        break
                                if not val_found:
                                    exists = False
                                    break
                            if not exists:
                                reject = True
                                break
                        else:
                            # No implementations that is searched for, reject
                            reject = True
                            break
                    elif key == 'ietf':
                        values = value.split(',')
                        reject = True
                        for val in values:
                            if res_row['module'][key].get('ietf-wg') is not None:
                                if res_row['module'][key]['ietf-wg'] == val['ietf-wg']:
                                    reject = False
                                    break
                        if reject:
                            break
                elif isinstance(res_row['module'][key], list):
                    # this means the key is either dependencies or dependents
                    exists = True
                    for val in value:
                        val_found = False
                        for dep in res_row['module'][key]:
                            name = dep.get('name')
                            rev = dep.get('revision')
                            schema = dep.get('schema')
                            local_exist = True
                            if val.get('name') is not None:
                                if name != val['name']:
                                    local_exist = False
                            if val.get('revision') is not None:
                                if rev != val['revision']:
                                    local_exist = False
                            if val.get('schema') is not None:
                                if schema != val['schema']:
                                    local_exist = False
                            if local_exist:
                                val_found = True
                                break
                        if not val_found:
                            exists = False
                            break
                    if not exists:
                        reject = True
                        break
                else:
                    # Module key has different value then serached for then reject
                    values = value.split(',')
                    reject = True
                    for val in values:
                        if res_row['module'].get(key) is not None:
                            if res_row['module'][key] == val:
                                reject = False
                                break
                    if reject:
                        break

        return reject
    except Exception as e:
        res_row['module'] = {'error': 'Metadata search failed with: {}'.format(e)}
        return False


def search_recursive(output: set, module: dict, leaf: str, resolved: set):
    """Look for all dependencies of the module and search for data in those modules too."""
    r_name = module['name']
    if r_name not in resolved:
        resolved.add(r_name)
        response = rpc_search({'input': {'dependencies': [{'name': r_name}]}})
        modules = response.get('yang-catalog:modules')
        if modules is None:
            return
        modules = modules.get('module')
        if modules is None:
            return
        for mod in modules:
            search_recursive(output, mod, leaf, resolved)
            meta_data = mod.get(leaf)
            output.add(meta_data)


def process(data, passed_data, value, module, split, count) -> bool:
    """Iterates recursively through the data to find only modules
    that are searched for

    Arguments:
        :param data:        (dict) module that is searched
        :param passed_data: (list) data that contain value searched
            for are saved in this variable
        :param value:       (str) value searched for
        :param module:      (dict) module that is searched
        :param split:       (str) key value that conatins value searched for
        :param count:       (int) if split contains '/' then we need to know
            which part of the path are we searching.
        :return             (bool) whether a match was found
    """
    if isinstance(data, str):
        if data == value:
            passed_data.append(module)
            return True
    elif isinstance(data, list):
        for part in data:
            if process(part, passed_data, value, module, split, count):
                break
    elif isinstance(data, dict):
        if data:
            count += 1
            return process(data.get(split[count]), passed_data, value, module, split, count)
    return False


def modules_data():
    """
    Get all the modules data from Redis.
    Empty dictionary is returned if no data is stored under specified key.
    """
    data = app.redisConnection.get_all_modules()
    if data != '{}':
        modules = json.loads(data)
        modules_list = list(modules.values())
        data = json.dumps({'module': modules_list})
    return json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(data)


def vendors_data(clean_data=True):
    """Get all the vendors data from Redis.
    Empty dictionary is returned if no data is stored under specified key.
    """
    data = app.redisConnection.get_all_vendors()

    if clean_data:
        json_data = json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(data)
    else:
        json_data = json.loads(data)
    return json_data


def catalog_data():
    """Get all the catalog data (modules and vendors) from Redis.
    Empty dictionary is returned if no data is stored under specified key.
    """
    modules_list = modules_data().get('module')
    vendors_list = vendors_data().get('vendor')
    catalog_data = {}

    if modules_list is not None:
        catalog_data['modules'] = {'module': modules_list}

    if vendors_list is not None:
        catalog_data['vendors'] = {'vendor': vendors_list}

    if catalog_data != {}:
        catalog_data = {'yang-catalog:catalog': catalog_data}

    return json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(json.dumps(catalog_data))


def create_bootstrap(context: dict, template: str):
    app.logger.info('Rendering bootstrap with {} template'.format(template))
    path = os.path.join(os.environ['BACKEND'], 'api/template')

    return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')).get_template(template).render(context)
