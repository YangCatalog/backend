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

import io
import os

import requests
from flask.blueprints import Blueprint
from flask.globals import request
from pyang import error, plugin
from pyang.plugins.tree import emit_tree
from werkzeug.exceptions import abort

from api.my_flask import app
from api.views.redisSearch.redisSearch import rpc_search
from utility.util import context_check_update_from
from utility.yangParser import create_context


class Comparisons(Blueprint):
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


bp = Comparisons('comparisons', __name__)


@bp.before_request
def set_config():
    global ac
    ac = app.config


@bp.route('/services/file1=<name1>@<revision1>/check-update-from/file2=<name2>@<revision2>', methods=['GET'])
def create_update_from(name1: str, revision1: str, name2: str, revision2: str) -> str:
    """Create output from pyang tool with option --check-update-from for two modules with revisions

    Arguments:
        :param name1:            (str) name of the first module
        :param revision1:        (str) revision of the first module in format YYYY-MM-DD
        :param name2:            (str) name of the second module
        :param revision2:        (str) revision of the second module in format YYYY-MM-DD
        :return                  (str) preformatted HTML with corresponding data
    """
    new_schema = os.path.join(ac.d_save_file_dir, f'{name1}@{revision1}.yang')
    old_schema = os.path.join(ac.d_save_file_dir, f'{name2}@{revision2}.yang')
    ctx, _ = context_check_update_from(old_schema, new_schema, ac.d_yang_models_dir, ac.d_save_file_dir)

    errors = []
    for ctx_err in ctx.errors:
        ref = f'{ctx_err[0].ref}:{ctx_err[0].line}:'
        err_message = error.err_to_str(ctx_err[1], ctx_err[2])
        err = f'{ref} {err_message}\n'
        errors.append(err)

    return f'<html><body><pre>{"".join(errors)}</pre></body></html>'


@bp.route('/services/diff-file/file1=<name1>@<revision1>/file2=<name2>@<revision2>', methods=['GET'])
def create_diff_file(name1: str, revision1: str, name2: str, revision2: str) -> str:
    """Create preformated HTML which contains diff between two yang file.
    Dump content of yang files into tempporary schema-file-diff.txt file.
    Make GET request to URL https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1=<file1>&url2=<file2>'.
    Output of rfcdiff tool then represents response of the method.

    Arguments:
        :param name1:            (str) name of the first module
        :param revision1:        (str) revision of the first module in format YYYY-MM-DD
        :param name2:            (str) name of the second module
        :param revision2:        (str) revision of the second module in format YYYY-MM-DD
        :return                  (str) preformatted HTML with corresponding data
    """
    schema1 = os.path.join(ac.d_save_file_dir, f'{name1}@{revision1}.yang')
    schema2 = os.path.join(ac.d_save_file_dir, f'{name2}@{revision2}.yang')
    file_name1 = 'schema1-file-diff.txt'
    yang_file_1_content = ''
    try:
        with open(schema1, 'r', encoding='utf-8', errors='strict') as f:
            yang_file_1_content = f.read()
    except FileNotFoundError:
        app.logger.warn(f'File {name1}@{revision1}.yang was not found.')

    with open(os.path.join(ac.w_save_diff_dir, file_name1), 'w+') as f:
        f.write(f'<pre>{yang_file_1_content}</pre>')

    file_name2 = 'schema2-file-diff.txt'
    yang_file_2_content = ''
    try:
        with open(schema2, 'r', encoding='utf-8', errors='strict') as f:
            yang_file_2_content = f.read()
    except FileNotFoundError:
        app.logger.warn(f'File {name2}@{revision2}.yang was not found.')
    with open(os.path.join(ac.w_save_diff_dir, file_name2), 'w+') as f:
        f.write(f'<pre>{yang_file_2_content}</pre>')
    tree1 = f'{ac.w_my_uri}/compatibility/{file_name1}'
    tree2 = f'{ac.w_my_uri}/compatibility/{file_name2}'
    diff_url = f'https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1={tree1}&url2={tree2}'
    response = requests.get(diff_url)
    os.remove(os.path.join(ac.w_save_diff_dir, file_name1))
    os.remove(os.path.join(ac.w_save_diff_dir, file_name2))
    return f'<html><body>{response.text}</body></html>'


@bp.route('/services/diff-tree/file1=<name1>@<revision1>/file2=<file2>@<revision2>', methods=['GET'])
def create_diff_tree(name1: str, revision1: str, file2: str, revision2: str) -> str:
    """Create preformated HTML which contains diff between two yang trees.
    Dump content of yang files into tempporary schema-tree-diff.txt file.
    Make GET request to URL https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1=<file1>&url2=<file2>'.
    Output of rfcdiff tool then represents response of the method.

    Arguments:
        :param name1:            (str) name of the first module
        :param revision1:        (str) revision of the first module in format YYYY-MM-DD
        :param name2:            (str) name of the second module
        :param revision2:        (str) revision of the second module in format YYYY-MM-DD
        :return                  (str) preformatted HTML with corresponding data
    """
    schema1 = os.path.join(ac.d_save_file_dir, f'{name1}@{revision1}.yang')
    schema2 = os.path.join(ac.d_save_file_dir, f'{file2}@{revision2}.yang')
    plugin.plugins = []
    plugin.init([])
    ctx = create_context(f'{ac.d_yang_models_dir}:{ac.d_save_file_dir}')
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
    full_path_file1 = os.path.join(ac.w_save_diff_dir, file_name1)
    with open(full_path_file1, 'w+') as ff:
        ff.write(f'<pre>{stdout}</pre>')
    with open(schema2, 'r') as ff:
        a = ctx.add_module(schema2, ff.read())
    ctx.validate()
    f = io.StringIO()
    emit_tree(ctx, [a], f, ctx.opts.tree_depth, ctx.opts.tree_line_length, path)
    stdout = f.getvalue()
    file_name2 = 'schema2-tree-diff.txt'
    full_path_file2 = f'{ac.w_save_diff_dir}/{file_name2}'
    with open(full_path_file2, 'w+') as ff:
        ff.write(f'<pre>{stdout}</pre>')
    tree1 = f'{ac.w_my_uri}/compatibility/{file_name1}'
    tree2 = f'{ac.w_my_uri}/compatibility/{file_name2}'
    diff_url = f'https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1={tree1}&url2={tree2}'
    response = requests.get(diff_url)
    os.unlink(full_path_file1)
    os.unlink(full_path_file2)
    return f'<html><body>{response.text}</body></html>'


@bp.route('/get-common', methods=['POST'])
def get_common():
    """
    Get all the common modules out of two different filtering by leafs with data provided by in body of the request.
    """
    body = request.json
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
    """
    Compare and find different modules out of two different filtering by leafs with data
    provided by in body of the request.
    Output contains module metadata with 'reason-to-show' data as well which can be showing either 'New module' or
    'Different revision'.
    """
    body = request.json
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
    II. If check-update-from has an output it will provide tree diff and output of the pyang together with diff
    between two files.
    """
    body = request.json
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
                        file_name = (
                            f'{ac.w_yangcatalog_api_prefix}/services/file1={name_new}@{revision_new}'
                            f'/check-update-from/file2={name_old}@{revision_old}'
                        )
                        reason = f'pyang --check-update-from output: {file_name}'

                    diff = (
                        f'{ac.w_yangcatalog_api_prefix}/services/diff-tree'
                        f'/file1={name_old}@{revision_old}/file2={name_new}@{revision_new}'
                    )
                    output_mod['yang-module-pyang-tree-diff'] = diff

                    output_mod['name'] = name_old
                    output_mod['revision-old'] = revision_old
                    output_mod['revision-new'] = revision_new
                    output_mod['organization'] = organization_old
                    output_mod['old-derived-semantic-version'] = semver_old
                    output_mod['new-derived-semantic-version'] = semver_new
                    output_mod['derived-semantic-version-results'] = reason
                    diff = (
                        f'{ac.w_yangcatalog_api_prefix}/services/diff-file'
                        f'/file1={name_old}@{revision_old}/file2={name_new}@{revision_new}'
                    )
                    output_mod['yang-module-diff'] = diff
                    output_modules_list.append(output_mod)
    if len(output_modules_list) == 0:
        abort(404, description='No different semantic versions with provided input')
    output = {'output': output_modules_list}
    return output
