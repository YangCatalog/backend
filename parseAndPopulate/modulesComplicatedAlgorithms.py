# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
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

"""
This is a class of a single module to parse all the more complicated
metadata that we can get out of the module. From this class parse
method is called which will call all the other methods that
will get the rest of the metadata. This is parsed separately to
make sure that metadata that are quickly parsed are already pushed
into the database and these metadata will get there later.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import io
import json
import os
from collections import defaultdict
from copy import deepcopy
from datetime import datetime

import requests
from pyang import plugin
from pyang.plugins.tree import emit_tree
from pyang.plugins.json_tree import emit_tree as emit_json_tree
from utility import log, messageFactory
from utility.staticVariables import confd_headers, json_headers
from utility.util import (context_check_update_from, fetch_module_by_schema,
                          find_first_file)
from utility.yangParser import create_context


class ModulesComplicatedAlgorithms:

    def __init__(self, log_directory, yangcatalog_api_prefix, credentials, confd_prefix,
                 save_file_dir, direc, all_modules, yang_models_dir, temp_dir, ytree_dir):
        global LOGGER
        LOGGER = log.get_logger('modulesComplicatedAlgorithms', '{}/parseAndPopulate.log'.format(log_directory))
        if all_modules is None:
            with open('{}/prepare.json'.format(direc), 'r') as f:
                self.__all_modules = json.load(f)
        else:
            self.__all_modules = all_modules
        self.__yangcatalog_api_prefix = yangcatalog_api_prefix
        self.new_modules = defaultdict(dict)
        self.__credentials = credentials
        self.__save_file_dir = save_file_dir
        self.__path = None
        self.__confd_prefix = confd_prefix
        self.__yang_models = yang_models_dir
        self.temp_dir = temp_dir
        self.ytree_dir = ytree_dir
        self.__direc = direc
        self.__trees = defaultdict(dict)
        self.__unavailable_modules = []
        LOGGER.info('get all existing modules')
        response = requests.get('{}search/modules'.format(self.__yangcatalog_api_prefix),
                                headers=json_headers)
        existing_modules = response.json().get('module', [])
        self.__existing_modules_dict = defaultdict(dict)
        self.__latest_revisions = {}
        for module in existing_modules:
            # Store latest revision of each module - used in resolving tree-type
            latest_revision = self.__latest_revisions.get(module['name'])
            if latest_revision is None:
                self.__latest_revisions[module['name']] = module['revision']
            else:
                self.__latest_revisions[module['name']] = max(module['revision'], latest_revision)

            sem_ver = module.get('derived-semantic-version')
            tree_type = module.get('tree-type')
            if not (sem_ver and tree_type):
                continue
            self.__existing_modules_dict[module['name']][module['revision']] = module

    def parse_non_requests(self):
        LOGGER.info('parsing tree types')
        self.resolve_tree_type(self.__all_modules)

    def parse_requests(self):
        LOGGER.info('parsing semantic version')
        self.parse_semver()
        LOGGER.info('parsing dependents')
        self.parse_dependents()

    def populate(self):
        new_modules = [revision for name in self.new_modules.values() for revision in name.values()]
        LOGGER.info('populate with module complicated data. amount of new data is {}'
                    .format(len(new_modules)))
        x = -1
        chunk_size = 250
        chunks = (len(new_modules) - 1) // chunk_size + 1
        for x in range(chunks):
            payload = {'modules': {'module': new_modules[x * chunk_size: (x * chunk_size) + chunk_size]}}
            json_modules_data = json.dumps(payload)
            if '{"module": []}' not in json_modules_data:
                url = self.__confd_prefix + '/restconf/data/yang-catalog:catalog/modules/'
                response = requests.patch(url, data=json_modules_data,
                                          auth=(self.__credentials[0],
                                                self.__credentials[1]),
                                          headers=confd_headers)
                if response.status_code < 200 or response.status_code > 299:
                    path_to_file = '{}/modulesComplicatedAlgorithms-data-{}'.format(self.__direc, x)
                    with open(path_to_file, 'w') as f:
                        json.dump(json_modules_data, f)
                    LOGGER.error('Request with body {} on path {} failed with {}'.
                                 format(path_to_file, url,
                                        response.text))

        if len(new_modules) > 0:
            url = '{}load-cache'.format(self.__yangcatalog_api_prefix)
            response = requests.post(url, None,
                                     auth=(self.__credentials[0], self.__credentials[1]))
            if response.status_code != 201:
                LOGGER.warning('Could not send a load-cache request. Status code: {} Message: {}'
                               .format(response.status_code, response.text))
            else:
                LOGGER.info('load-cache responded with status code {}'.format(response.status_code))

    def resolve_tree_type(self, all_modules):
        def is_openconfig(rows, output):
            count_config = output.count('+-- config')
            count_state = output.count('+-- state')
            if count_config != count_state:
                return False
            row_number = 0
            skip = []
            for row in rows:
                if 'x--' in row or 'o--' in row:
                    continue
                if '' == row.strip(' '):
                    break
                if '+--rw' in row and row_number != 0 \
                        and row_number not in skip and '[' not in row and \
                        (len(row.replace('|', '').strip(' ').split(
                            ' ')) != 2 or '(' in row):
                    if '->' in row and 'config' in row.split('->')[
                            1] and '+--rw config' not in rows[row_number - 1]:
                        row_number += 1
                        continue
                    if '+--rw config' not in rows[row_number - 1]:
                        if 'augment' in rows[row_number - 1]:
                            if not rows[row_number - 1].endswith(':config:'):
                                return False
                        else:
                            return False
                    length_before = set([len(row.split('+--')[0])])
                    skip = []
                    for x in range(row_number, len(rows)):
                        if 'x--' in rows[x] or 'o--' in rows[x]:
                            continue
                        if len(rows[x].split('+--')[0]) not in length_before:
                            if (len(rows[x].replace('|', '').strip(' ').split(
                                    ' ')) != 2 and '[' not in rows[x]) \
                                    or '+--:' in rows[x] or '(' in rows[x]:
                                length_before.add(len(rows[x].split('+--')[0]))
                            else:
                                break
                        if '+--ro' in rows[x]:
                            return False
                        duplicate = \
                            rows[x].replace('+--rw', '+--ro').split('+--')[1]
                        if duplicate.replace(' ', '') not in output.replace(' ',
                                                                            ''):
                            return False
                        skip.append(x)
                if '+--ro' in row and row_number != 0 and row_number not in skip and '[' not in row and \
                        (len(row.replace('|', '').strip(' ').split(
                            ' ')) != 2 or '(' in row):
                    if '->' in row and 'state' in row.split('->')[
                            1] and '+--ro state' not in rows[row_number - 1]:
                        row_number += 1
                        continue
                    if '+--ro state' not in rows[row_number - 1]:
                        if 'augment' in rows[row_number - 1]:
                            if not rows[row_number - 1].endswith(':state:'):
                                return False
                        else:
                            return False
                    length_before = len(row.split('+--')[0])
                    skip = []
                    for x in range(row_number, len(rows)):
                        if 'x--' in rows[x] or 'o--' in rows[x]:
                            continue
                        if len(rows[x].split('+--')[0]) < length_before:
                            break
                        if '+--rw' in rows[x]:
                            return False
                        skip.append(x)
                row_number += 1
            return True

        def is_combined(rows, output):
            for row in rows:
                if row.endswith('-state') and not ('x--' in row or 'o--' in row):
                    return False
            next_obsolete_or_deprecated = False
            for row in rows:
                if next_obsolete_or_deprecated:
                    if 'x--' in row or 'o--' in row:
                        next_obsolete_or_deprecated = False
                    else:
                        return False
                if 'x--' in row or 'o--' in row:
                    continue
                if '+--rw config' == row.replace('|', '').strip(
                    ' ') or '+--ro state' == row.replace('|', '').strip(
                        ' '):
                    return False
                if len(row.split('+--')[0]) == 4:
                    if '-state' in row and '+--ro' in row:
                        return False
                if 'augment' in row and len(row.split('augment')[0]) == 2:
                    part = row.strip(' ').split('/')[1]
                    if '-state' in part:
                        next_obsolete_or_deprecated = True
                    part = row.strip(' ').split('/')[-1]
                    if ':state:' in part or '/state:' in part \
                            or ':config:' in part or '/config:' in part:
                        next_obsolete_or_deprecated = True
            return True

        def is_transitional(rows, output):
            if output.split('\n')[1].endswith('-state') and output.split('\n')[0].endswith('-state'):
                if '+--rw' in output:
                    return False
                if output.startswith('\n'):
                    name_of_module = output.split('\n')[1].split(': ')[1]
                else:
                    name_of_module = output.split('\n')[0].split(': ')[1]
                name_of_module = name_of_module.split('-state')[0]
                coresponding_nmda_file = self.__find_file(name_of_module)
                if coresponding_nmda_file:
                    name = coresponding_nmda_file.split('/')[-1].split('.')[0]
                    revision = name.split('@')[-1]
                    name = name.split('@')[0]
                    if '{}@{}'.format(name, revision) in self.__trees:
                        stdout = self.__trees['{}@{}'.format(name, revision)]
                        pyang_list_of_rows = stdout.split('\n')[2:]
                    else:
                        plugin.plugins = []
                        plugin.init([])

                        ctx = create_context('{}:{}'.format(os.path.abspath(self.__yang_models), self.__save_file_dir))

                        ctx.opts.lint_namespace_prefixes = []
                        ctx.opts.lint_modulename_prefixes = []
                        for p in plugin.plugins:
                            p.setup_ctx(ctx)
                        with open(coresponding_nmda_file, 'r') as f:
                            a = ctx.add_module(coresponding_nmda_file, f.read())
                        if ctx.opts.tree_path is not None:
                            path = ctx.opts.tree_path.split('/')
                            if path[0] == '':
                                path = path[1:]
                        else:
                            path = None
                        ctx.validate()
                        try:
                            f = io.StringIO()
                            emit_tree(ctx, [a], f, ctx.opts.tree_depth,
                                      ctx.opts.tree_line_length, path)
                            stdout = f.getvalue()
                        except:
                            stdout = ''

                        pyang_list_of_rows = stdout.split('\n')[2:]
                        if len(ctx.errors) != 0 and len(stdout) == 0:
                            return False
                    if stdout == '':
                        return False
                    for x in range(0, len(rows)):
                        if 'x--' in rows[x] or 'o--' in rows[x]:
                            continue
                        if rows[x].strip(' ') == '':
                            break
                        if len(rows[x].split('+--')[0]) == 4:
                            if '-state' in rows[x]:
                                return False
                        if len(rows[x].split('augment')[0]) == 2:
                            part = rows[x].strip(' ').split('/')[1]
                            if '-state' in part:
                                return False
                        if '+--ro ' in rows[x]:
                            leaf = \
                                rows[x].split('+--ro ')[1].split(' ')[0].split(
                                    '?')[0]

                            for y in range(0, len(pyang_list_of_rows)):
                                if leaf in pyang_list_of_rows[y]:
                                    break
                            else:
                                return False
                    return True
                else:
                    return False
            else:
                return False

        def is_split(rows, output):
            failed = False
            row_num = 0
            if output.split('\n')[1].endswith('-state'):
                return False
            for row in rows:
                if 'x--' in row or 'o--' in row:
                    continue
                if '+--rw config' == row.replace('|', '').strip(
                        ' ') or '+--ro state' == row.replace('|', '') \
                        .strip(' '):
                    return False
                if 'augment' in row:
                    part = row.strip(' ').split('/')[-1]
                    if ':state:' in part or '/state:' in part or ':config:' in part or '/config:' in part:
                        return False
            for row in rows:
                if 'x--' in row or 'o--' in row:
                    continue
                if row == '':
                    break
                if (len(row.split('+--')[0]) == 4 and 'augment' not in rows[
                        row_num - 1]) or len(row.split('augment')[0]) == 2:
                    if '-state' in row:
                        if 'augment' in row:
                            part = row.strip(' ').split('/')[1]
                            if '-state' not in part:
                                row_num += 1
                                continue
                        for x in range(row_num + 1, len(rows)):
                            if 'x--' in rows[x] or 'o--' in rows[x]:
                                continue
                            if rows[x].strip(' ') == '' \
                                    or (len(rows[x].split('+--')[
                                        0]) == 4 and 'augment' not in
                                        rows[row_num - 1]) \
                                    or len(row.split('augment')[0]) == 2:
                                break
                            if '+--rw' in rows[x]:
                                failed = True
                                break
                row_num += 1
            if failed:
                return False
            else:
                return True

        x = 0
        for module in all_modules.get('module', []):
            x += 1
            name = module['name']
            revision = module['revision']
            name_revision = '{}@{}'.format(name, revision)
            self.__path = '{}/{}.yang'.format(self.__save_file_dir, name_revision)
            yang_file_exists = self.__check_schema_file(module)
            is_latest_revision = self.check_if_latest_revision(module)
            if not yang_file_exists:
                LOGGER.error('Skipping module: {}'.format(name_revision))
                continue
            LOGGER.info(
                'Searching tree-type for {}. {} out of {}'.format(name_revision, x, len(all_modules['module'])))
            if revision in self.__trees[name]:
                stdout = self.__trees[name][revision]
            else:
                plugin.plugins = []
                plugin.init([])
                ctx = create_context('{}:{}'.format(os.path.abspath(self.__yang_models), self.__save_file_dir))
                ctx.opts.lint_namespace_prefixes = []
                ctx.opts.lint_modulename_prefixes = []
                for p in plugin.plugins:
                    p.setup_ctx(ctx)
                with open(self.__path, 'r', errors='ignore') as f:
                    a = ctx.add_module(self.__path, f.read())
                if a is None:
                    LOGGER.debug(
                        'Could not use pyang to generate tree because of errors on module {}'.
                        format(self.__path))
                    module['tree-type'] = 'unclassified'
                    if revision not in self.new_modules[name]:
                        self.new_modules[name][revision] = module
                    else:
                        self.new_modules[name][revision]['tree-type'] = 'unclassified'
                    continue
                if ctx.opts.tree_path is not None:
                    path = ctx.opts.tree_path.split('/')
                    if path[0] == '':
                        path = path[1:]
                else:
                    path = None
                retry = 5
                while retry:
                    try:
                        ctx.validate()
                        break
                    except Exception as e:
                        retry -= 1
                        if retry == 0:
                            raise e
                try:
                    f = io.StringIO()
                    emit_tree(ctx, [a], f, ctx.opts.tree_depth,
                              ctx.opts.tree_line_length, path)
                    stdout = f.getvalue()
                    self.__trees[name][revision] = stdout
                except:
                    module['tree-type'] = 'not-applicable'
                    LOGGER.exception('not-applicable tree created')
                    continue

            if stdout == '':
                module['tree-type'] = 'not-applicable'
            else:
                if stdout.startswith('\n'):
                    pyang_list_of_rows = stdout.split('\n')[2:]
                else:
                    pyang_list_of_rows = stdout.split('\n')[1:]
                if 'submodule' == module['module-type']:
                    LOGGER.debug('Module {} is a submodule'.format(self.__path))
                    module['tree-type'] = 'not-applicable'
                elif is_latest_revision and is_combined(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'nmda-compatible'
                elif is_split(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'split'
                elif is_openconfig(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'openconfig'
                elif is_transitional(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'transitional-extra'
                else:
                    module['tree-type'] = 'unclassified'
            LOGGER.debug('tree type for module {} is {}'.format(module['name'], module['tree-type']))
            if (revision not in self.__existing_modules_dict[name] or
                    self.__existing_modules_dict.get(name, {}).get(revision, {}).get('tree-type') != module['tree-type']):
                LOGGER.info('tree-type {} vs {} for module {}@{}'.format(
                    self.__existing_modules_dict.get(name, {}).get(revision, {}).get('tree-type'), module['tree-type'],
                    module['name'], module['revision']))
                if revision not in self.new_modules[name]:
                    self.new_modules[name][revision] = module
                else:
                    self.new_modules[name][revision]['tree-type'] = module['tree-type']

    def parse_semver(self):
        def get_revision_datetime(module: dict):
            rev = module['revision'].split('-')
            try:
                date = datetime(int(rev[0]), int(rev[1]), int(rev[2]))
            except Exception:
                LOGGER.error('Failed to process revision for {}: (rev: {})'.format(module['name'], rev))
                try:
                    if int(rev[1]) == 2 and int(rev[2]) == 29:
                        date = datetime(int(rev[0]), int(rev[1]), 28)
                    else:
                        date = datetime(1970, 1, 1)
                except Exception:
                    date = datetime(1970, 1, 1)
            return date

        def increment_semver(old: str, significance: int):
            versions = old.split('.')
            versions = list(map(int, versions))
            versions[significance] += 1
            versions[significance + 1:] = [0] * len(versions[significance + 1:])
            return '{}.{}.{}'.format(*versions)

        def update_semver(old_details: dict, new_module: dict, significance: int):
            upgraded_version = increment_semver(old_details['semver'], significance)
            new_module['derived-semantic-version'] = upgraded_version
            add_to_new_modules(new_module)

        def trees_match(new, old) -> bool:
            if type(new) != type(old):
                return False
            elif isinstance(new, dict):
                new.pop('description', None)
                old.pop('description', None)
                return new.keys() == old.keys() and all((trees_match(new[i], old[i]) for i in new))
            elif isinstance(new, list):
                return len(new) == len(old) and all(any((trees_match(i, j) for j in old)) for i in new)
            elif type(new) in (str, set, bool):
                return new == old


        def get_trees(new: dict, old: dict):
            new_name_revision = '{}@{}'.format(new['name'], new['revision'])
            old_name_revision = '{}@{}'.format(old['name'], old['revision'])
            new_schema = '{}/{}.yang'.format(self.__save_file_dir, new_name_revision)
            old_schema = '{}/{}.yang'.format(self.__save_file_dir, old_name_revision)
            new_schema_exist = self.__check_schema_file(new)
            old_schema_exist = self.__check_schema_file(old)
            new_tree_path = '{}/{}.json'.format(self.ytree_dir, new_name_revision)
            old_tree_path = '{}/{}.json'.format(self.ytree_dir, old_name_revision)

            if old_schema_exist and new_schema_exist:
                ctx, new_schema_ctx = context_check_update_from(old_schema, new_schema,
                                                                self.__yang_models,
                                                                self.__save_file_dir)
                if len(ctx.errors) == 0:
                    if os.path.exists(new_tree_path) and os.path.exists(old_tree_path):
                        with open(new_tree_path) as nf, open(old_tree_path) as of:
                            new_yang_tree = json.load(nf)
                            old_yang_tree = json.load(of)
                    else:
                        with open(old_schema, 'r', errors='ignore') as f:
                            old_schema_ctx = ctx.add_module(old_schema, f.read())
                        if ctx.opts.tree_path is not None:
                            path = ctx.opts.tree_path.split('/')
                            if path[0] == '':
                                path = path[1:]
                        else:
                            path = None
                        retry = 5
                        while retry:
                            try:
                                ctx.validate()
                                break
                            except Exception as e:
                                retry -= 1
                                if retry == 0:
                                    raise e
                        try:
                            f = io.StringIO()
                            emit_json_tree([new_schema_ctx], f, ctx)
                            new_yang_tree = f.getvalue()
                            with open(new_tree_path, 'w') as f:
                                f.write(new_yang_tree)
                        except:
                            new_yang_tree = ''
                        try:
                            f = io.StringIO()
                            emit_json_tree([old_schema_ctx], f, ctx)
                            old_yang_tree = f.getvalue()
                            with open(old_tree_path, 'w') as f:
                                f.write(old_yang_tree)
                        except:
                            old_yang_tree = '2'
                    return (new_yang_tree, old_yang_tree)
                else:
                    raise Exception

        def add_to_new_modules(new_module: dict):
            name = new_module['name']
            revision = new_module['revision']
            if (revision not in self.__existing_modules_dict[name] or
                    self.__existing_modules_dict.get(name, {}).get(revision, {}).get('derived-semantic-version') != new_module['derived-semantic-version']):
                LOGGER.info('semver {} vs {} for module {}@{}'.format(
                    self.__existing_modules_dict.get(name, {}).get(revision, {}).get('derived-semantic-version'),
                    new_module['derived-semantic-version'], name, revision))
                if revision not in self.new_modules[name]:
                    self.new_modules[name][revision] = new_module
                else:
                    self.new_modules[name][revision]['derived-semantic-version'] = new_module['derived-semantic-version']

        z = 0
        for new_module in self.__all_modules.get('module', []):
            z += 1
            name = new_module['name']
            new_revision = new_module['revision']
            name_revision = '{}@{}'.format(name, new_revision)
            data = defaultdict(dict)
            # Get all other available revisions of the module
            for m in self.__existing_modules_dict[new_module['name']].values():
                if m['revision'] != new_module['revision']:
                    data[m['name']][m['revision']] = deepcopy(m)

            LOGGER.info(
                'Searching semver for {}. {} out of {}'.format(name_revision, z, len(self.__all_modules['module'])))
            if len(data) == 0:
                # If there is no other revision for this module
                new_module['derived-semantic-version'] = '1.0.0'
                add_to_new_modules(new_module)
            else:
                # If there is at least one revision for this module
                date = get_revision_datetime(new_module)
                module_temp = {}
                module_temp['name'] = name
                module_temp['revision'] = new_revision
                module_temp['organization'] = new_module['organization']
                module_temp['compilation'] = new_module.get('compilation-status', 'PENDING')
                module_temp['date'] = date
                module_temp['schema'] = new_module['schema']
                mod_details = [module_temp]

                # Loop through all other available revisions of the module
                for mod in [revision for name in data.values() for revision in name.values()]:
                    module_temp = {}
                    revision = mod['revision']
                    if revision == new_module['revision']:
                        continue
                    module_temp['revision'] = revision
                    module_temp['date'] = get_revision_datetime(mod)
                    module_temp['name'] = name
                    module_temp['organization'] = mod.get('organization')
                    module_temp['schema'] = mod.get('schema')
                    module_temp['compilation'] = mod.get('compilation-status', 'PENDING')
                    module_temp['semver'] = mod['derived-semantic-version']
                    mod_details.append(module_temp)
                data[name][new_revision] = new_module
                mod_details = sorted(mod_details, key=lambda k: k['date'])
                # If we are adding a new module to the end (latest revision) of existing modules with this name
                # and all modules with this name have semver already assigned except for the last one
                if mod_details[-1]['date'] == date:
                    if mod_details[-1]['compilation'] != 'passed':
                        versions = mod_details[-2]['semver'].split('.')
                        major_ver = int(versions[0])
                        major_ver += 1
                        upgraded_version = '{}.{}.{}'.format(major_ver, 0, 0)
                        new_module['derived-semantic-version'] = upgraded_version
                        add_to_new_modules(new_module)
                    else:
                        if mod_details[-2]['compilation'] != 'passed':
                            update_semver(mod_details[-2], new_module, 0)
                        else:
                            try:
                                trees = get_trees(mod_details[-1], mod_details[-2])
                                # if schemas do not exist, trees will be None
                                if trees:
                                    new_yang_tree, old_yang_tree = trees
                                    if trees_match(new_yang_tree, old_yang_tree):
                                        # yang trees are the same - update only the patch version
                                        update_semver(mod_details[-2], new_module, 2)
                                    else:
                                        # yang trees have changed - update minor version
                                        update_semver(mod_details[-2], new_module, 1)
                            except:
                                # pyang found an error - update major version
                                update_semver(mod_details[-2], new_module, 0)
                # If we are adding new module in the middle (between two revisions) of existing modules with this name
                else:
                    name = mod_details[0]['name']
                    revision = mod_details[0]['revision']
                    mod_details[0]['semver'] = '1.0.0'
                    response = data[name][revision]
                    response['derived-semantic-version'] = '1.0.0'
                    add_to_new_modules(response)

                    for x in range(1, len(mod_details)):
                        name = mod_details[x]['name']
                        revision = mod_details[x]['revision']
                        module = data[name][revision]
                        if mod_details[x]['compilation'] != 'passed':
                            update_semver(mod_details[x - 1], module, 0)
                            mod_details[x]['semver'] = increment_semver(mod_details[x - 1]['semver'], 0)
                        else:
                            # If the previous revision has the compilation status 'passed'
                            if mod_details[x - 1]['compilation'] != 'passed':
                                update_semver(mod_details[x - 1], module, 0)
                                mod_details[x]['semver'] = increment_semver(mod_details[x - 1]['semver'], 0)
                            else:
                                # Both actual and previous revisions have the compilation status 'passed'
                                try:
                                    trees = get_trees(mod_details[x], mod_details[x - 1])
                                    # if schemas do not exist, trees will be None
                                    if trees:
                                        new_yang_tree, old_yang_tree = trees
                                        if trees_match(new_yang_tree, old_yang_tree):
                                            # yang trees are the same - update only the patch version
                                            update_semver(mod_details[x - 1], module, 2)
                                            mod_details[x]['semver'] = increment_semver(mod_details[x - 1]['semver'],
                                                                                        2)
                                        else:
                                            LOGGER.debug("didn't match")
                                            # yang trees have changed - update minor version
                                            update_semver(mod_details[x - 1], module, 1)
                                            mod_details[x]['semver'] = increment_semver(mod_details[x - 1]['semver'],
                                                                                        1)
                                except:
                                    # pyang found an error - update major version
                                    update_semver(mod_details[x - 1], module, 0)
                                    mod_details[x]['semver'] = increment_semver(mod_details[x - 1]['semver'], 0)

        if len(self.__unavailable_modules) != 0:
            mf = messageFactory.MessageFactory()
            mf.send_unavailable_modules(self.__unavailable_modules)

    def parse_dependents(self):

        def check_latest_revision_and_remove(dependent, dependency):
            for i in range(len(dependency.get('dependents', []))):
                existing_dependent = dependency['dependents'][i]
                if existing_dependent['name'] == dependent['name']:
                    if existing_dependent['revision'] >= dependent['revision']:
                        return True
                    else:
                        dependency['dependents'].pop(i)
                        break
            return False

        def add_dependents(dependents: list, dependencies):
            for dependent in dependents:
                for dep_filter in dependent.get('dependencies', []):
                    name = dep_filter['name']
                    revision = dep_filter.get('revision')
                    if name in dependencies:
                        if revision is None:
                            it = dependencies[name].values()
                        else:
                            if revision in dependencies[name]:
                                it = [dependencies[name][revision]]
                            else:
                                it = []
                        for dependency in it:
                            revision = dependency['revision']
                            if revision in self.new_modules[name]:
                                dependency_copy = self.new_modules[name][revision]
                            elif revision in self.__existing_modules_dict[name]:
                                dependency_copy = deepcopy(self.__existing_modules_dict.get(name, {}).get(revision, {}))
                            else:
                                dependency_copy = dependency
                            if not check_latest_revision_and_remove(dependent, dependency_copy):
                                details = {
                                    'name': dependent['name'],
                                    'revision': dependent['revision'],
                                }
                                if 'schema' in dependent:
                                    details['schema'] = dependent['schema']
                                LOGGER.info('Adding {}@{} as dependent of {}@{}'.format(
                                    dependent['name'], dependent['revision'], name, revision))
                                dependency_copy.setdefault('dependents', []).append(details)
                                self.new_modules[name][revision] = dependency_copy

        all_modules = self.__all_modules.get('module', [])
        all_modules_dict = defaultdict(dict)
        for i in all_modules:
            all_modules_dict[i['name']][i['revision']] = deepcopy(i)
        both_dict = deepcopy(self.__existing_modules_dict)
        for name, revisions in all_modules_dict.items():
            both_dict[name] |= deepcopy(revisions)
        existing_modules = [revision for name in self.__existing_modules_dict.values() for revision in name.values()]
        LOGGER.info('Adding new modules as dependents')
        add_dependents(all_modules, both_dict)
        LOGGER.info('Adding existing modules as dependents')
        add_dependents(existing_modules, all_modules_dict)

    def __find_file(self, name: str, revision: str = '*'):
        yang_name = '{}.yang'.format(name)
        yang_name_rev = '{}@{}.yang'.format(name, revision)
        yang_file = find_first_file('/'.join(self.__path.split('/')[0:-1]), yang_name, yang_name_rev)
        if yang_file is None:
            yang_file = find_first_file(self.__yang_models, yang_name, yang_name_rev)

        return yang_file

    def __check_schema_file(self, module: dict):
        """ Check if the file exists and if not try to get it from Github.

        :param module   (dict) Details of currently parsed module
        :return         Whether the content of the module was obtained or not.
        :rtype  bool
        """
        schema = '{}/{}@{}.yang'.format(self.__save_file_dir, module['name'], module['revision'])
        result = True

        if not os.path.isfile(schema):
            LOGGER.warning('File on path {} not found'.format(schema))
            result = fetch_module_by_schema(module['schema'], schema)
            if result:
                LOGGER.info('File content successfully retrieved from GitHub using module schema')
            else:
                module_name = '{}@{}.yang'.format(module['name'], module['revision'])
                self.__unavailable_modules.append(module_name)
                LOGGER.error('Unable to retrieve file content from GitHub using module schema')

        return result

    def check_if_latest_revision(self, module: dict):
        """ Check if the parsed module is the latest revision.

        Argument:
            :param module   (dict) Details of currently parsed module
        """
        return module.get('revision', '') >= self.__latest_revisions.get(module['name'], '')
