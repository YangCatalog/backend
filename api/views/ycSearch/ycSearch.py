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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright The IETF Trust 2020, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import collections
import io
import json
import os
import re
import typing as t
from operator import contains, eq

import api.yangSearch.elasticsearchIndex as inde
import jinja2
import requests
from flask import Blueprint, abort, request
from markupsafe import escape
from flask_deprecate import deprecate_route
from pyang import error, plugin
from pyang.plugins.tree import emit_tree

from api.my_flask import app
from utility.util import context_check_update_from
from utility.yangParser import create_context


class YcSearch(Blueprint):

    def __init__(self, name, import_name, static_folder=None, static_url_path=None, template_folder=None,
                 url_prefix=None, subdomain=None, url_defaults=None, root_path=None):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder, url_prefix, subdomain,
                         url_defaults, root_path)


bp = YcSearch('ycSearch', __name__)


@bp.before_request
def set_config():
    global ac
    ac = app.config

### ROUTE ENDPOINT DEFINITIONS ###


@bp.route('/fast', methods=['POST'])
@deprecate_route("Use foo instead")
def fast_search():
    """Search through the YANG keyword index for a given search pattern.
       The arguments are a payload specifying search options and filters.
    """
    if not request.json:
        abort(400, description='No input data')

    limit = 1000000
    payload = request.json
    app.logger.info(payload)
    if 'search' not in payload:
        abort(400, description='You must specify a "search" argument')
    try:
        count = 0
        search_res, limit_reached = inde.do_search(payload, ac.db_es_host,
                                                   ac.db_es_port, ac.db_es_aws, ac.s_elk_credentials,
                                                   app.logger)
        if search_res is None and limit_reached is None:
            abort(400, description='Search is too broad. Please search for something more specific')
        res = []
        found_modules = {}
        rejects = []
        errors = []

        for row in search_res:
            res_row = {}
            res_row['node'] = row['node']
            m_name = row['module']['name']
            m_revision = row['module']['revision']
            m_organization = row['module']['organization']
            mod_sig = '{}@{}/{}'.format(m_name, m_revision, m_organization)
            if mod_sig in rejects:
                continue

            mod_meta = None
            try:
                if mod_sig in found_modules:
                    mod_meta = found_modules[mod_sig]
                else:
                    mod_meta = search_module(m_name, m_revision, m_organization)
                    mod_meta = mod_meta['module'][0]
                    found_modules[mod_sig] = mod_meta

                if 'include-mibs' not in payload or payload['include-mibs'] is False:
                    if re.search('yang:smiv2:', mod_meta.get('namespace')):
                        rejects.append(mod_sig)
                        continue

                if mod_meta is not None and 'yang-versions' in payload and len(payload['yang-versions']) > 0:
                    if mod_meta.get('yang-version') not in payload['yang-versions']:
                        rejects.append(mod_sig)
                        continue

                if mod_meta is not None:
                    if 'filter' not in payload or 'module-metadata' not in payload['filter']:
                        # If the filter is not specified, return all
                        # fields.
                        res_row['module'] = mod_meta
                    elif 'module-metadata' in payload['filter']:
                        res_row['module'] = {}
                        for field in payload['filter']['module-metadata']:
                            if field in mod_meta:
                                res_row['module'][field] = mod_meta[field]
            except Exception as e:
                count -= 1
                if mod_sig not in errors:
                    res_row['module'] = {
                        'error': 'Search failed at {}: {}'.format(mod_sig, e)}
                    errors.append(mod_sig)

            if not filter_using_api(res_row, payload):
                count += 1
                res.append(res_row)
            else:
                rejects.append(mod_sig)
            if count >= limit:
                break
        return {'results': res, 'limit_reched': limit_reached}
    except Exception as e:
        return ({'error': str(e)}, 500)


@bp.route('/search/<path:value>', methods=['GET'])
def search(value: str):
    """Search for a specific leaf from yang-catalog.yang module in modules
    branch. The key searched is defined in @module_keys variable.
        Arguments:
            :param value: (str) path that contains one of the @module_keys and
                ends with /value searched for
            :return response to the request.
    """
    path = value
    app.logger.info('Searching for {}'.format(value))
    split = value.split('/')[:-1]
    key = '/'.join(value.split('/')[:-1])
    value = value.split('/')[-1]
    module_keys = ['ietf/ietf-wg', 'maturity-level', 'document-name', 'author-email', 'compilation-status', 'namespace',
                   'conformance-type', 'module-type', 'organization', 'yang-version', 'name', 'revision', 'tree-type',
                   'belongs-to', 'generated-from', 'expires', 'expired', 'prefix', 'reference']
    for module_key in module_keys:
        if key == module_key:
            data = modules_data().get('module')
            if data is None:
                abort(404, description='No module found in ConfD database')
            passed_data = []
            for module in data:
                count = -1
                process(module, passed_data, value, module, split, count)

            if len(passed_data) > 0:
                modules = json.JSONDecoder(object_pairs_hook=collections.OrderedDict) \
                    .decode(json.dumps(passed_data))
                return {
                    'yang-catalog:modules': {
                        'module': modules
                    }
                }
            else:
                abort(404, description='No module found using provided input data')
    abort(400, description='Search on path {} is not supported'.format(path))


@bp.route('/search-filter/<leaf>', methods=['POST'])
def rpc_search_get_one(leaf: str):
    """Get list of values of specified leaf in filtered set of modules. Filter is specified in body of the request.
    """
    body = request.json
    if body is None:
        abort(400, description='body of request is empty')
    if body.get('input') is None:
        abort(400, description='body of request need to start with input')

    recursive = body['input'].get('recursive')
    if recursive:
        body['input'].pop('recursive')

    data = rpc_search(body)
    modules = data['yang-catalog:modules']['module']

    if len(modules) == 0:
        abort(404, description='No module found in ConfD database')
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
def rpc_search(body: dict = {}):
    """Get all the modules that contains all the leafs with data as provided in body of the request.
    """
    from_api = False
    if not body:
        assert request.json is not None
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
            modules = json.JSONDecoder(object_pairs_hook=collections.OrderedDict) \
                .decode(json.dumps(matched_modules))
            return {
                'yang-catalog:modules': {
                    'module': modules
                }
            }
    else:
        abort(400, description='body request has to start with "input" container')


@bp.route('/contributors', methods=['GET'])
def get_organizations():
    """Loop through all the modules in catalog and create unique set of organizations.
    """
    orgs = set()
    data = modules_data().get('module', {})
    for module in data:
        if module['organization'] != 'example' and module['organization'] != 'missing element':
            orgs.add(module['organization'])
    orgs = list(orgs)
    return {'contributors': orgs}


@bp.route('/services/file1=<name1>@<revision1>/check-update-from/file2=<name2>@<revision2>', methods=['GET'])
def create_update_from(name1: str, revision1: str, name2: str, revision2: str):
    """Create output from pyang tool with option --check-update-from for two modules with revisions
        Arguments:
            :param name1:            (str) name of the first module
            :param revision1:        (str) revision of the first module in format YYYY-MM-DD
            :param name2:            (str) name of the second module
            :param revision2:        (str) revision of the second module in format YYYY-MM-DD
            :return preformatted HTML with corresponding data
    """
    new_schema = '{}/{}@{}.yang'.format(ac.d_save_file_dir, name1, revision1)
    old_schema = '{}/{}@{}.yang'.format(ac.d_save_file_dir, name2, revision2)
    ctx, _ = context_check_update_from(old_schema, new_schema, ac.d_yang_models_dir, ac.d_save_file_dir)

    errors = []
    for ctx_err in ctx.errors:
        ref = '{}:{}:'.format(ctx_err[0].ref, ctx_err[0].line)
        err_message = error.err_to_str(ctx_err[1], ctx_err[2])
        err = '{} {}\n'.format(ref, err_message)
        errors.append(err)

    return '<html><body><pre>{}</pre></body></html>'.format(''.join(errors))


@bp.route('/services/diff-file/file1=<name1>@<revision1>/file2=<name2>@<revision2>', methods=['GET'])
def create_diff_file(name1: str, revision1: str, name2: str, revision2: str):
    """Create preformated HTML which contains diff between two yang file.
    Dump content of yang files into tempporary schema-file-diff.txt file.
    Make GET request to URL https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1=<file1>&url2=<file2>'.
    Output of rfcdiff tool then represents response of the method.
        Arguments:
            :param name1:            (str) name of the first module
            :param revision1:        (str) revision of the first module in format YYYY-MM-DD
            :param name2:            (str) name of the second module
            :param revision2:        (str) revision of the second module in format YYYY-MM-DD
            :return preformatted HTML with corresponding data
    """
    schema1 = '{}/{}@{}.yang'.format(ac.d_save_file_dir, name1, revision1)
    schema2 = '{}/{}@{}.yang'.format(ac.d_save_file_dir, name2, revision2)
    file_name1 = 'schema1-file-diff.txt'
    yang_file_1_content = ''
    try:
        with open(schema1, 'r', encoding='utf-8', errors='strict') as f:
            yang_file_1_content = f.read()
    except FileNotFoundError:
        app.logger.warn('File {}@{}.yang was not found.'.format(name1, revision1))

    with open('{}/{}'.format(ac.w_save_diff_dir, file_name1), 'w+') as f:
        f.write('<pre>{}</pre>'.format(yang_file_1_content))

    file_name2 = 'schema2-file-diff.txt'
    yang_file_2_content = ''
    try:
        with open(schema2, 'r', encoding='utf-8', errors='strict') as f:
            yang_file_2_content = f.read()
    except FileNotFoundError:
        app.logger.warn('File {}@{}.yang was not found.'.format(name2, revision2))
    with open('{}/{}'.format(ac.w_save_diff_dir, file_name2), 'w+') as f:
        f.write('<pre>{}</pre>'.format(yang_file_2_content))
    tree1 = '{}/compatibility/{}'.format(ac.w_my_uri, file_name1)
    tree2 = '{}/compatibility/{}'.format(ac.w_my_uri, file_name2)
    diff_url = ('https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1={}&url2={}'
                .format(tree1, tree2))
    response = requests.get(diff_url)
    os.remove('{}/{}'.format(ac.w_save_diff_dir, file_name1))
    os.remove('{}/{}'.format(ac.w_save_diff_dir, file_name2))
    return '<html><body>{}</body></html>'.format(response.text)


@bp.route('/services/diff-tree/file1=<name1>@<revision1>/file2=<file2>@<revision2>', methods=['GET'])
def create_diff_tree(name1: str, revision1: str, file2: str, revision2: str):
    """Create preformated HTML which contains diff between two yang trees.
    Dump content of yang files into tempporary schema-tree-diff.txt file.
    Make GET request to URL https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1=<file1>&url2=<file2>'.
    Output of rfcdiff tool then represents response of the method.
        Arguments:
            :param name1:            (str) name of the first module
            :param revision1:        (str) revision of the first module in format YYYY-MM-DD
            :param name2:            (str) name of the second module
            :param revision2:        (str) revision of the second module in format YYYY-MM-DD
            :return preformatted HTML with corresponding data
    """
    schema1 = '{}/{}@{}.yang'.format(ac.d_save_file_dir, name1, revision1)
    schema2 = '{}/{}@{}.yang'.format(ac.d_save_file_dir, file2, revision2)
    plugin.plugins = []
    plugin.init([])
    ctx = create_context('{}:{}'.format(ac.d_yang_models_dir, ac.d_save_file_dir))
    ctx.opts.lint_namespace_prefixes = []
    ctx.opts.lint_modulename_prefixes = []
    ctx.lax_quote_checks = True
    ctx.lax_xpath_checks = True
    for p in plugin.plugins:
        p.setup_ctx(ctx)

    with open(schema1, 'r') as ff:
        a = ctx.add_module(schema1, ff.read())
    ctx.errors = []
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
    file_name1 = 'schema1-tree-diff.txt'
    full_path_file1 = '{}/{}'.format(ac.w_save_diff_dir, file_name1)
    with open(full_path_file1, 'w+') as ff:
        ff.write('<pre>{}</pre>'.format(stdout))
    with open(schema2, 'r') as ff:
        a = ctx.add_module(schema2, ff.read())
    ctx.validate()
    f = io.StringIO()
    emit_tree(ctx, [a], f, ctx.opts.tree_depth, ctx.opts.tree_line_length, path)
    stdout = f.getvalue()
    file_name2 = 'schema2-tree-diff.txt'
    full_path_file2 = '{}/{}'.format(ac.w_save_diff_dir, file_name2)
    with open(full_path_file2, 'w+') as ff:
        ff.write('<pre>{}</pre>'.format(stdout))
    tree1 = '{}/compatibility/{}'.format(ac.w_my_uri, file_name1)
    tree2 = '{}/compatibility/{}'.format(ac.w_my_uri, file_name2)
    diff_url = ('https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1={}&url2={}'
                .format(tree1, tree2))
    response = requests.get(diff_url)
    os.unlink(full_path_file1)
    os.unlink(full_path_file2)
    return '<html><body>{}</body></html>'.format(response.text)


@bp.route('/get-common', methods=['POST'])
def get_common():
    """Get all the common modules out of two different filtering by leafs with data provided by in body of the request.
    """
    body = request.json
    if body is None:
        abort(400, description='body of request is empty')
    if body.get('input') is None:
        abort(400, description='body of request need to start with input')
    if body['input'].get('first') is None or body['input'].get('second') is None:
        abort(400, description='body of request need to contain first and second container')
    response_first = rpc_search({'input': body['input']['first']})
    response_second = rpc_search({'input': body['input']['second']})

    modules_first = response_first['yang-catalog:modules']['module']
    modules_second = response_second['yang-catalog:modules']['module']

    if len(modules_first) == 0 or len(modules_second) == 0:
        abort(404, description='No hits found either in first or second input')

    output_modules_list = []
    names = []
    for mod_first in modules_first:
        for mod_second in modules_second:
            if mod_first['name'] == mod_second['name']:
                if mod_first['name'] not in names:
                    names.append(mod_first['name'])
                    output_modules_list.append(mod_first)
    if len(output_modules_list) == 0:
        abort(404, description='No common modules found within provided input')
    return {'output': output_modules_list}


@bp.route('/compare', methods=['POST'])
def compare():
    """Compare and find different modules out of two different filtering by leafs with data provided by in body of the request.
    Output contains module metadata with 'reason-to-show' data as well which can be showing either 'New module' or 'Different revision'.
    """
    body = request.json
    if body is None:
        abort(400, description='body of request is empty')
    if body.get('input') is None:
        abort(400, description='body of request need to start with input')
    if body['input'].get('old') is None or body['input'].get('new') is None:
        abort(400, description='body of request need to contain new and old container')
    response_new = rpc_search({'input': body['input']['new']})
    response_old = rpc_search({'input': body['input']['old']})

    modules_new = response_new['yang-catalog:modules']['module']
    modules_old = response_old['yang-catalog:modules']['module']

    if len(modules_new) == 0 or len(modules_old) == 0:
        abort(404, description='No hits found either in old or new input')

    new_mods = []
    for mod_new in modules_new:
        new_rev = mod_new['revision']
        new_name = mod_new['name']
        found = False
        new_rev_found = False
        for mod_old in modules_old:
            old_rev = mod_old['revision']
            old_name = mod_old['name']
            if new_name == old_name and new_rev == old_rev:
                found = True
                break
            if new_name == old_name and new_rev != old_rev:
                new_rev_found = True
        if not found:
            mod_new['reason-to-show'] = 'New module'
            new_mods.append(mod_new)
        if new_rev_found:
            mod_new['reason-to-show'] = 'Different revision'
            new_mods.append(mod_new)
    if len(new_mods) == 0:
        abort(404, description='No new modules or modules with different revisions found')
    output = {'output': new_mods}
    return output


@bp.route('/check-semantic-version', methods=['POST'])
# @cross_origin(headers='Content-Type')
def check_semver():
    """Get output from pyang tool with option '--check-update-from' for all the modules between and filter.
    I. If module compilation failed it will give you only link to get diff in between two yang modules.
    II. If check-update-from has an output it will provide tree diff and output of the pyang together with diff between two files.
    """
    body = request.json
    if body is None:
        abort(400, description='body of request is empty')
    if body.get('input') is None:
        abort(400, description='body of request need to start with input')
    if body['input'].get('old') is None or body['input'].get('new') is None:
        abort(400, description='body of request need to contain new and old container')
    response_new = rpc_search({'input': body['input']['new']})
    response_old = rpc_search({'input': body['input']['old']})

    modules_new = response_new['yang-catalog:modules']['module']
    modules_old = response_old['yang-catalog:modules']['module']

    if len(modules_new) == 0 or len(modules_old) == 0:
        abort(404, description='No hits found either in old or new input')

    output_modules_list = []
    for mod_old in modules_old:
        name_new = None
        semver_new = None
        revision_new = None
        status_new = None
        name_old = mod_old['name']
        revision_old = mod_old['revision']
        organization_old = mod_old['organization']
        status_old = mod_old['compilation-status']
        for mod_new in modules_new:
            name_new = mod_new['name']
            revision_new = mod_new['revision']
            organization_new = mod_new['organization']
            status_new = mod_new['compilation-status']
            if name_new == name_old and organization_new == organization_old:
                if revision_old == revision_new:
                    break
                semver_new = mod_new.get('derived-semantic-version')
                break
        if semver_new:
            semver_old = mod_old.get('derived-semantic-version')
            if semver_old:
                if semver_new != semver_old:
                    output_mod = {}
                    if status_old != 'passed' and status_new != 'passed':
                        reason = 'Both modules failed compilation'
                    elif status_old != 'passed' and status_new == 'passed':
                        reason = 'Older module failed compilation'
                    elif status_new != 'passed' and status_old == 'passed':
                        reason = 'Newer module failed compilation'
                    else:
                        file_name = ('{}services/file1={}@{}/check-update-from/file2={}@{}'
                                     .format(ac.yangcatalog_api_prefix, name_new,
                                             revision_new, name_old,
                                             revision_old))
                        reason = ('pyang --check-update-from output: {}'.
                                  format(file_name))

                    diff = (
                        '{}services/diff-tree/file1={}@{}/file2={}@{}'.
                        format(ac.yangcatalog_api_prefix, name_old,
                               revision_old, name_new, revision_new))

                    output_mod['yang-module-pyang-tree-diff'] = diff

                    output_mod['name'] = name_old
                    output_mod['revision-old'] = revision_old
                    output_mod['revision-new'] = revision_new
                    output_mod['organization'] = organization_old
                    output_mod['old-derived-semantic-version'] = semver_old
                    output_mod['new-derived-semantic-version'] = semver_new
                    output_mod['derived-semantic-version-results'] = reason
                    diff = ('{}services/diff-file/file1={}@{}/file2={}@{}'
                            .format(ac.yangcatalog_api_prefix, name_old,
                                    revision_old, name_new, revision_new))
                    output_mod['yang-module-diff'] = diff
                    output_modules_list.append(output_mod)
    if len(output_modules_list) == 0:
        abort(404, description='No different semantic versions with provided input')
    output = {'output': output_modules_list}
    return output


@bp.route('/search/vendor/<vendor>', methods=['GET'])
def search_vendor_statistics(vendor: str):
    """Search for os-types of <vendor> with corresponding os-versions and platforms.
        Arguments:
            :param vendor   (str) name of the vendor
            :return statistics of the vendor's os-types, os-versions and platforms
            :rtype dict
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
def search_vendors(value: str):
    """Search for a specific vendor, platform, os-type, os-version depending on
    the value sent via API.
        Arguments:
            :param value: (str) path that contains one of the @module_keys and
                ends with /value searched for
            :return response to the request.
    """
    app.logger.info('Searching for specific vendors {}'.format(value))
    vendors_data = get_vendors()

    if 'vendor/' in value:
        found = False
        vendor_name = value.split('vendor/')[-1].split('/')[0]
        for vendor in vendors_data['vendor']:
            if vendor['name'] == vendor_name:
                vendors_data = vendor
                found = True
        if found == False:
            abort(404, description='No vendors found on path {}'.format(value))
    else:
        return vendors_data

    if 'platform/' in value:
        found = False
        platform_name = value.split('platform/')[-1].split('/')[0]
        for platform in vendors_data.get('platforms', {}).get('platform', []):
            if platform['name'] == platform_name:
                vendors_data = platform
                found = True
        if found == False:
            abort(404, description='No platform found on path {}'.format(value))
    else:
        vendors_data = {'yang-catalog:vendor': [vendors_data]}
        return vendors_data

    if 'software-version/' in value:
        found = False
        software_version_name = value.split('software-version/')[-1].split('/')[0]
        for software_version in vendors_data.get('software-versions', {}).get('software-version', []):
            if software_version['name'] == software_version_name:
                vendors_data = software_version
                found = True
        if found == False:
            abort(404, description='No software-version found on path {}'.format(value))
    else:
        vendors_data = {'yang-catalog:platform': [vendors_data]}
        return vendors_data

    if 'software-flavor/' in value:
        found = False
        software_flavor_name = value.split('software-flavor/')[-1].split('/')[0]
        for software_flavor in vendors_data.get('software-flavors', {}).get('software-flavor', []):
            if software_flavor['name'] == software_flavor_name:
                vendors_data = software_flavor
                found = True
        if found == False:
            abort(404, description='No software-flavor found on path {}'.format(value))
        else:
            vendors_data = {'yang-catalog:software-flavor': [vendors_data]}
            return vendors_data
    else:
        vendors_data = {'yang-catalog:software-version': [vendors_data]}
        return vendors_data


@bp.route('/search/modules/<name>,<revision>,<organization>', methods=['GET'])
def search_module(name: str, revision: str, organization: str):
    """Search for a specific module defined with name, revision and organization
            Arguments:
                :param name:            (str) name of the module
                :param revision:        (str) revision of the module in format YYYY-MM-DD
                :param organization:    (str) organization of the module
                :return response to the request with job_id that user can use to
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
    """Search for all the vendors populated in ConfD
        :return response to the request with all the vendors
    """
    app.logger.info('Searching for vendors')
    data = vendors_data()
    if data is None or data == {}:
        abort(404, description='No vendor is loaded')
    return data


@bp.route('/search/catalog', methods=['GET'])
def get_catalog():
    """Search for a all the data populated in Redis/ConfD
        :return response to the request with all the data (modules and vendors)
    """
    app.logger.info('Searching for catalog data')
    data = catalog_data()
    if data is None or data == {}:
        abort(404, description='No data loaded to YangCatalog')
    else:
        return data


@bp.route('/services/tree/<name>@<revision>.yang', methods=['GET'])
def create_tree(name: str, revision: str):
    """
    Return yang tree representation of yang module with corresponding module name and revision.
    Arguments:
        :param name     (str) name of the module
        :param revision (str) revision of the module in format YYYY-MM-DD
        :return preformatted HTML with corresponding data
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
    except:
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
    if stdout == '' and len(ctx.errors) != 0:
        message = 'This yang file contains major errors and therefore tree can not be created.'
        return create_bootstrap_danger(message)
    elif stdout != '' and len(ctx.errors) != 0:
        message = 'This yang file contains some errors, but tree was created.'
        return create_bootstrap_warning(stdout, message)
    elif stdout == '' and len(ctx.errors) == 0:
        return create_bootstrap_info()
    else:
        return '<html><body><pre>{}</pre></body></html>'.format(stdout)


@bp.route('/services/reference/<name>@<revision>.yang', methods=['GET'])
def create_reference(name: str, revision: str):
    """
    Return reference of yang file with corresponding module name and revision.
    Arguments:
        :param name     (str) name of the module
        :param revision (str) revision of the module in format YYYY-MM-DD
        :return preformatted HTML with corresponding data
    """
    path_to_yang = '{}/{}@{}.yang'.format(ac.d_save_file_dir, name, revision)
    try:
        with open(path_to_yang, 'r', encoding='utf-8', errors='strict') as f:
            yang_file_content = escape(f.read())
    except FileNotFoundError:
        message = 'File {}@{}.yang was not found.'.format(name, revision)
        return create_bootstrap_danger(message)

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
    """Look for all dependencies of the module and search for data in those modules too.
    """
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


def process(data, passed_data, value, module, split, count):
    """Iterates recursively through the data to find only modules
    that are searched for
            Arguments:
                :param data: (dict) module that is searched
                :param passed_data: (list) data that contain value searched
                    for are saved in this variable
                :param value: (str) value searched for
                :param module: (dict) module that is searched
                :param split: (str) key value that conatins value searched for
                :param count: (int) if split contains '/' then we need to know
                    which part of the path are we searching.
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
    """Get all the modules data from Redis.
    Empty dictionary is returned if no data is stored under specified key.
    """
    data = app.redisConnection.get_all_modules()
    if data != '{}':
        modules = json.loads(data)
        modules_list = [module for module in modules.values()]
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


def create_bootstrap_info():
    with open(os.path.join(os.environ['BACKEND'], 'api/template/info.html'), 'r') as f:
        template = f.read()
    return template


def create_bootstrap_warning(text: str, message: str):
    app.logger.info('Rendering bootstrap warning data')
    context = {'warn_text': text, 'warn_message': message}
    path = os.path.join(os.environ['BACKEND'], 'api/template')
    filename = 'warning.html'

    return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')
                              ).get_template(filename).render(context)


def create_bootstrap_danger(message: str):
    app.logger.info('Rendering bootstrap danger data')
    context = {'danger_message': message}
    path = os.path.join(os.environ['BACKEND'], 'api/template')
    filename = 'danger.html'

    return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')
                              ).get_template(filename).render(context)
