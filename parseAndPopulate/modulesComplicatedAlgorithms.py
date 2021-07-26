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
import sys
import time
from copy import deepcopy
from datetime import datetime

import requests
from pyang import plugin
from pyang.plugins.tree import emit_tree
from utility import log, messageFactory
from utility.staticVariables import confd_headers, json_headers
from utility.util import (context_check_update_from, fetch_module_by_schema,
                          find_first_file)
from utility.yangParser import create_context


class ModulesComplicatedAlgorithms:

    def __init__(self, log_directory, yangcatalog_api_prefix, credentials, confd_prefix,
                 save_file_dir, direc, all_modules, yang_models_dir, temp_dir):
        global LOGGER
        LOGGER = log.get_logger('modulesComplicatedAlgorithms', '{}/parseAndPopulate.log'.format(log_directory))
        if all_modules is None:
            with open('{}/prepare.json'.format(direc), 'r') as f:
                self.__all_modules = json.load(f)
        else:
            self.__all_modules = all_modules
        self.__yangcatalog_api_prefix = yangcatalog_api_prefix
        self.new_modules = {}
        self.__credentials = credentials
        self.__save_file_dir = save_file_dir
        self.__path = None
        self.__confd_prefix = confd_prefix
        self.__yang_models = yang_models_dir
        self.temp_dir = temp_dir
        self.__direc = direc
        self.__trees = dict()
        self.__unavailable_modules = []
        LOGGER.info('get all existing modules')
        response = requests.get('{}search/modules'.format(self.__yangcatalog_api_prefix),
                                headers=json_headers)
        existing_modules = response.json().get('module', [])
        self.__existing_modules_dict = {}
        self.__latest_revisions = {}
        for module in existing_modules:
            # Store latest revision of each module - used in resolving tree-type
            latest_revision = self.__latest_revisions.get(module['name'])
            if latest_revision is None:
                self.__latest_revisions[module['name']] = module['revision']
            else:
                self.__latest_revisions[module['name']] = module['revision'] if latest_revision < module['revision'] else latest_revision

            sem_ver = module.get('derived-semantic-version')
            tree_type = module.get('tree-type')
            if sem_ver is None or sem_ver == '' or tree_type is None or tree_type == '':
                continue
            self.__existing_modules_dict['{}@{}'.format(module['name'], module['revision'])] = module

    def parse_non_requests(self):
        LOGGER.info("parsing tree types")
        self.__resolve_tree_type()

    def parse_requests(self):
        LOGGER.info("parsing semantic version")
        self.parse_semver()
        LOGGER.info("parsing dependents")
        self.__parse_dependents()

    def merge_modules_and_remove_not_updated(self):
        start = time.time()
        ret_modules = {}
        for val in self.new_modules.values():
            key = '{}@{}'.format(val['name'], val['revision'])
            old_module = self.__existing_modules_dict.get(key)
            if old_module is None:
                ret_modules[key] = val
            else:
                if (old_module.get('tree-type') != val.get('tree-type') or
                        old_module.get('derived-semantic-version') != val.get('derived-semantic-version')):
                    LOGGER.debug('{} tree {} vs {}, semver {} vs {}'.format(
                        key, old_module.get('tree-type'), val.get('tree-type'),
                        old_module.get('derived-semantic-version'), val.get('derived-semantic-version'))
                    )
                    if ret_modules.get(key) is None:
                        ret_modules[key] = val
                    else:
                        ret_modules[key]['name'] = val['name']
                        ret_modules[key]['revision'] = val['revision']
                        ret_modules[key]['organization'] = val['organization']
                        ret_modules[key]['tree-type'] = val.get('tree-type')
                        ret_modules[key]['derived-semantic-version'] = val.get('derived-semantic-version')
                if val.get('dependents') is not None and len(val.get('dependents')) != 0:
                    if old_module.get('dependents') is None:
                        if ret_modules.get(key) is None:
                            ret_modules[key] = val
                            LOGGER.debug('dependents {} vs {}'.format(None, val['dependents']))
                            continue
                        ret_modules[key]['name'] = val['name']
                        ret_modules[key]['revision'] = val['revision']
                        ret_modules[key]['organization'] = val['organization']
                        ret_modules[key]['dependents'] = val['dependents']
                        LOGGER.debug('dependents {} vs {}'.format(None, val['dependents']))
                        continue
                    for dep in val['dependents']:
                        found = False
                        for old_dep in old_module['dependents']:
                            if (dep.get('name') == old_dep.get('name') and
                                    dep.get('revision') == old_dep.get('revision') and
                                    dep.get('schema') == old_dep.get('schema')):
                                break
                        else:
                            if ret_modules.get(key) is None:
                                ret_modules[key] = val
                            elif ret_modules[key].get('dependents') is None:
                                ret_modules[key]['dependents'] = []
                            ret_modules[key]['name'] = val['name']
                            ret_modules[key]['revision'] = val['revision']
                            ret_modules[key]['organization'] = val['organization']
                            ret_modules[key]['dependents'].append(dep)
                            LOGGER.debug('dependents {} vs {}'.format(old_module['dependents'], dep))
        end = time.time()
        LOGGER.debug('time taken to merge and remove {} seconds'.format(int(end - start)))
        return list(ret_modules.values())

    def populate(self):
        LOGGER.info('populate with module complicated data. amount of new data is {}'.format(len(self.new_modules.values())))
        module_to_populate = self.merge_modules_and_remove_not_updated()
        LOGGER.info('populate with module complicated data after merging. amount of new data is {}'.format(len(module_to_populate)))
        x = -1
        for x in range(0, int(len(module_to_populate) / 250)):
            json_modules_data = json.dumps({'modules': {'module': module_to_populate[x * 250: (x * 250) + 250]}})
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

        json_modules_data = json.dumps(
            {'modules': {'module': module_to_populate[(x * 250) + 250:]}})
        if '{"module": []}' not in json_modules_data:
            url = self.__confd_prefix + '/restconf/data/yang-catalog:catalog/modules/'
            response = requests.patch(url, data=json_modules_data,
                                      auth=(self.__credentials[0],
                                            self.__credentials[1]),
                                      headers=confd_headers)
            if response.status_code < 200 or response.status_code > 299:
                path_to_file = '{}/modulesComplicatedAlgorithms-data-rest'.format(self.__direc)
                with open(path_to_file, 'w') as f:
                    json.dump(json_modules_data, f)
                LOGGER.error('Request with body {} on path {} failed with {}'.
                             format(path_to_file, url,
                                    response.text))
        url = (self.__yangcatalog_api_prefix + 'load-cache')
        response = requests.post(url, None,
                                 auth=(self.__credentials[0],
                                       self.__credentials[1]))
        if response.status_code != 201:
            LOGGER.warning('Could not send a load-cache request. Status code: {} Message: {}'
                           .format(response.status_code, response.text))

    def __resolve_tree_type(self):
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
            if output.split('\n')[1].endswith('-state'):
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
                            stdout = ""

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

                            dataExist = False
                            for y in range(0, len(pyang_list_of_rows)):
                                if leaf in pyang_list_of_rows[y]:
                                    dataExist = True
                            if not dataExist:
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
        for module in self.__all_modules.get('module', []):
            x += 1
            name_revision = '{}@{}'.format(module['name'], module['revision'])
            self.__path = '{}/{}.yang'.format(self.__save_file_dir, name_revision)
            yang_file_exists = self.__check_schema_file(module)
            is_latest_revision = self.__check_if_latest_revision(module)
            if not yang_file_exists:
                LOGGER.error('Skipping module: {}'.format(name_revision))
                continue
            LOGGER.info(
                'Searching tree-type for {}. {} out of {}'.format(name_revision, x, len(self.__all_modules['module'])))
            if name_revision in self.__trees:
                stdout = self.__trees[name_revision]
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
                    if self.new_modules.get(name_revision) is None:
                        self.new_modules[name_revision] = module
                    else:
                        self.new_modules[name_revision]['tree-type'] = 'unclassified'
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
                    self.__trees[name_revision] = stdout
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
            LOGGER.info('tree type for module {} is {}'.format(module['name'], module['tree-type']))
            if (self.__existing_modules_dict.get(name_revision) is None or
                    self.__existing_modules_dict[name_revision].get('tree-type') != module['tree-type']):
                if self.new_modules.get(name_revision) is None:
                    self.new_modules[name_revision] = module
                else:
                    self.new_modules[name_revision]['tree-type'] = module['tree-type']

    def parse_semver(self):
        def __get_revision_datetime(module: dict):
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

        z = 0
        for module in self.__all_modules.get('module', []):
            z += 1
            name_revision = '{}@{}'.format(module['name'], module['revision'])
            data = {}
            # Get all other available revisions of the module
            for m in self.__existing_modules_dict.values():
                if m['name'] == module['name']:
                    if m['revision'] != module['revision']:
                        data['{}@{}'.format(m['name'], m['revision'])] = deepcopy(m)

            LOGGER.info(
                'Searching semver for {}. {} out of {}'.format(name_revision, z, len(self.__all_modules['module'])))
            if len(data) == 0:
                # If there is no other revision for this module
                module['derived-semantic-version'] = '1.0.0'
                if self.new_modules.get(name_revision) is None:
                    self.new_modules[name_revision] = module
                else:
                    self.new_modules[name_revision]['derived-semantic-version'] = module['derived-semantic-version']
            else:
                # If there is at least one revision for this module
                date = __get_revision_datetime(module)
                module_temp = {}
                module_temp['name'] = module['name']
                module_temp['revision'] = module['revision']
                module_temp['organization'] = module['organization']
                module_temp['compilation'] = module.get('compilation-status', 'PENDING')
                module_temp['date'] = date
                module_temp['schema'] = module['schema']
                modules = [module_temp]
                semver_exist = True
                if sys.version_info >= (3, 4):
                    mod_list = data.items()
                else:
                    mod_list = data.iteritems()

                # Loop through all other available revisions of the module
                for key, mod in mod_list:
                    module_temp = {}
                    revision = mod['revision']
                    if revision == module['revision']:
                        continue
                    module_temp['revision'] = revision
                    module_temp['date'] = __get_revision_datetime(mod)
                    module_temp['name'] = mod['name']
                    module_temp['organization'] = mod.get('organization')
                    module_temp['schema'] = mod.get('schema')
                    module_temp['compilation'] = mod.get('compilation-status', 'PENDING')
                    module_temp['semver'] = mod.get('derived-semantic-version')
                    if module_temp['semver'] is None:
                        semver_exist = False
                    modules.append(module_temp)
                data[name_revision] = module
                # NOTE: Can the following IF branch ever be True?
                if len(modules) == 1:
                    module['derived-semantic-version'] = '1.0.0'
                    if self.new_modules.get(name_revision) is None:
                        self.new_modules[name_revision] = module
                    else:
                        self.new_modules[name_revision]['derived-semantic-version'] = module['derived-semantic-version']
                    continue
                modules = sorted(modules, key=lambda k: k['date'])
                # If we are adding new module to the end (latest revision) of existing modules with this name
                # and all modules with this name have semver already assigned except for the last one
                if modules[-1]['date'] == date and semver_exist:
                    if modules[-1]['compilation'] != 'passed':
                        versions = modules[-2]['semver'].split('.')
                        major_ver = int(versions[0])
                        major_ver += 1
                        upgraded_version = '{}.{}.{}'.format(major_ver, 0, 0)
                        module['derived-semantic-version'] = upgraded_version
                        if self.new_modules.get(name_revision) is None:
                            self.new_modules[name_revision] = module
                        else:
                            self.new_modules[name_revision]['derived-semantic-version'] = module['derived-semantic-version']
                    else:
                        if modules[-2]['compilation'] != 'passed':
                            versions = modules[-2]['semver'].split('.')
                            major_ver = int(versions[0])
                            major_ver += 1
                            upgraded_version = '{}.{}.{}'.format(major_ver, 0, 0)
                            module['derived-semantic-version'] = upgraded_version
                            if self.new_modules.get(name_revision) is None:
                                self.new_modules[name_revision] = module
                            else:
                                self.new_modules[name_revision]['derived-semantic-version'] = module['derived-semantic-version']
                            continue
                        else:
                            new_schema = '{}/{}@{}.yang'.format(self.__save_file_dir, modules[-1]['name'], modules[-1]['revision'])
                            old_schema = '{}/{}@{}.yang'.format(self.__save_file_dir, modules[-2]['name'], modules[-2]['revision'])
                            old_schema_exist = self.__check_schema_file(modules[-2])
                            new_schema_exist = self.__check_schema_file(modules[-1])

                            if old_schema_exist and new_schema_exist:
                                ctx, new_schema_ctx = context_check_update_from(old_schema, new_schema, self.__yang_models, self.__save_file_dir)
                                if len(ctx.errors) == 0:
                                    if ('{}@{}'.format(modules[-1]['name'], modules[-1]['revision']) in self.__trees and
                                            '{}@{}'.format(modules[-2]['name'], modules[-2]['revision']) in self.__trees):
                                        new_yang_tree = self.__trees['{}@{}'.format(modules[-1]['name'], modules[-1]['revision'])]
                                        old_yang_tree = self.__trees['{}@{}'.format(modules[-2]['name'], modules[-2]['revision'])]
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
                                            emit_tree(ctx, [new_schema_ctx], f, ctx.opts.tree_depth,
                                                      ctx.opts.tree_line_length, path)
                                            new_yang_tree = f.getvalue()
                                        except:
                                            new_yang_tree = ''

                                        try:
                                            f = io.StringIO()
                                            emit_tree(ctx, [old_schema_ctx], f, ctx.opts.tree_depth,
                                                      ctx.opts.tree_line_length, path)
                                            old_yang_tree = f.getvalue()
                                        except:
                                            old_yang_tree = '2'

                                    if old_yang_tree == new_yang_tree:
                                        # yang trees are the same - update only the patch version
                                        versions = modules[-2]['semver'].split('.')
                                        patch_ver = int(versions[2])
                                        patch_ver += 1
                                        upgraded_version = '{}.{}.{}'.format(versions[0], versions[1], patch_ver)
                                        module['derived-semantic-version'] = upgraded_version
                                        if self.new_modules.get(name_revision) is None:
                                            self.new_modules[name_revision] = module
                                        else:
                                            self.new_modules[name_revision]['derived-semantic-version'] = module[
                                                'derived-semantic-version']
                                        continue
                                    else:
                                        # yang trees have changed - update minor version
                                        versions = modules[-2]['semver'].split('.')
                                        minor_ver = int(versions[1])
                                        minor_ver += 1
                                        upgraded_version = '{}.{}.{}'.format(versions[0], minor_ver, 0)
                                        module['derived-semantic-version'] = upgraded_version
                                        if self.new_modules.get(name_revision) is None:
                                            self.new_modules[name_revision] = module
                                        else:
                                            self.new_modules[name_revision]['derived-semantic-version'] = module[
                                                'derived-semantic-version']
                                        continue
                                else:
                                    # pyang found an error - update major version
                                    versions = modules[-2]['semver'].split('.')
                                    major_ver = int(versions[0])
                                    major_ver += 1
                                    upgraded_version = '{}.{}.{}'.format(major_ver, 0, 0)
                                    module['derived-semantic-version'] = upgraded_version
                                    if self.new_modules.get(name_revision) is None:
                                        self.new_modules[name_revision] = module
                                    else:
                                        self.new_modules[name_revision]['derived-semantic-version'] = module[
                                            'derived-semantic-version']
                                    continue
                else:
                    # If we are adding new module in the middle (between two revisions) of existing modules with this name
                    mod = {}
                    mod['name'] = modules[0]['name']
                    mod['revision'] = modules[0]['revision']
                    mod['organization'] = modules[0]['organization']
                    modules[0]['semver'] = '1.0.0'
                    response = data['{}@{}'.format(mod['name'], mod['revision'])]
                    response['derived-semantic-version'] = '1.0.0'
                    name_revision = '{}@{}'.format(response['name'], response['revision'])
                    if self.new_modules.get(name_revision) is None:
                        self.new_modules[name_revision] = response
                    else:
                        self.new_modules[name_revision]['derived-semantic-version'] = response[
                            'derived-semantic-version']
                    for x in range(1, len(modules)):
                        mod = {}
                        mod['name'] = modules[x]['name']
                        mod['revision'] = modules[x]['revision']
                        mod['organization'] = modules[x]['organization']
                        if modules[x]['compilation'] != 'passed':
                            versions = modules[x - 1]['semver'].split('.')
                            major_ver = int(versions[0])
                            major_ver += 1
                            upgraded_version = '{}.{}.{}'.format(major_ver, 0, 0)
                            modules[x]['semver'] = upgraded_version
                            response = data['{}@{}'.format(mod['name'], mod['revision'])]
                            response['derived-semantic-version'] = upgraded_version
                            name_revision = '{}@{}'.format(response['name'], response['revision'])
                            if self.new_modules.get(name_revision) is None:
                                self.new_modules[name_revision] = response
                            else:
                                self.new_modules[name_revision]['derived-semantic-version'] = response[
                                    'derived-semantic-version']
                        else:
                            # If the previous revision has the compilation status 'passed'
                            if modules[x - 1]['compilation'] != 'passed':
                                versions = modules[x - 1]['semver'].split('.')
                                major_ver = int(versions[0])
                                major_ver += 1
                                upgraded_version = '{}.{}.{}'.format(major_ver, 0, 0)
                                modules[x]['semver'] = upgraded_version
                                response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                response['derived-semantic-version'] = upgraded_version
                                name_revision = '{}@{}'.format(response['name'], response['revision'])
                                if self.new_modules.get(name_revision) is None:
                                    self.new_modules[name_revision] = response
                                else:
                                    self.new_modules[name_revision]['derived-semantic-version'] = response[
                                        'derived-semantic-version']
                                continue
                            else:
                                # Both actual and previous revisions have the compilation status 'passed'
                                new_schema = '{}/{}@{}.yang'.format(self.__save_file_dir, modules[x]['name'], modules[x]['revision'])
                                old_schema = '{}/{}@{}.yang'.format(self.__save_file_dir, modules[x - 1]['name'], modules[x - 1]['revision'])
                                old_schema_exist = self.__check_schema_file(modules[x - 1])
                                new_schema_exist = self.__check_schema_file(modules[x])

                                if old_schema_exist and new_schema_exist:
                                    ctx, new_schema_ctx = context_check_update_from(old_schema, new_schema, self.__yang_models, self.__save_file_dir)
                                    if len(ctx.errors) == 0:
                                        if ('{}@{}'.format(modules[x - 1]['name'], modules[x - 1]['revision']) in self.__trees and
                                                '{}@{}'.format(modules[x]['name'], modules[x]['revision']) in self.__trees):
                                            old_yang_tree = self.__trees['{}@{}'.format(modules[x - 1]['name'], modules[x - 1]['revision'])]
                                            new_yang_tree = self.__trees['{}@{}'.format(modules[x]['name'], modules[x]['revision'])]
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
                                                emit_tree(ctx, [new_schema_ctx], f, ctx.opts.tree_depth,
                                                          ctx.opts.tree_line_length, path)
                                                new_yang_tree = f.getvalue()
                                            except:
                                                new_yang_tree = ''
                                            try:
                                                f = io.StringIO()

                                                emit_tree(ctx, [old_schema_ctx], f, ctx.opts.tree_depth,
                                                          ctx.opts.tree_line_length, path)
                                                old_yang_tree = f.getvalue()
                                            except:
                                                old_yang_tree = '2'
                                        if old_yang_tree == new_yang_tree:
                                            # yang trees are the same - update only the patch version
                                            versions = modules[x - 1]['semver'].split('.')
                                            patch_ver = int(versions[2])
                                            patch_ver += 1
                                            upgraded_version = '{}.{}.{}'.format(versions[0], versions[1], patch_ver)
                                            modules[x]['semver'] = upgraded_version
                                            response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                            response['derived-semantic-version'] = upgraded_version
                                            name_revision = '{}@{}'.format(response['name'], response['revision'])
                                            if self.new_modules.get(name_revision) is None:
                                                self.new_modules[name_revision] = response
                                            else:
                                                self.new_modules[name_revision]['derived-semantic-version'] = response[
                                                    'derived-semantic-version']
                                        else:
                                            # yang trees have changed - update minor version
                                            versions = modules[x - 1]['semver'].split('.')
                                            minor_ver = int(versions[1])
                                            minor_ver += 1
                                            upgraded_version = '{}.{}.{}'.format(versions[0], minor_ver, 0)
                                            modules[x]['semver'] = upgraded_version
                                            response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                            response['derived-semantic-version'] = upgraded_version
                                            name_revision = '{}@{}'.format(response['name'], response['revision'])
                                            if self.new_modules.get(name_revision) is None:
                                                self.new_modules[name_revision] = response
                                            else:
                                                self.new_modules[name_revision]['derived-semantic-version'] = response[
                                                    'derived-semantic-version']
                                    else:
                                        # pyang found an error - update major version
                                        versions = modules[x - 1]['semver'].split('.')
                                        major_ver = int(versions[0])
                                        major_ver += 1
                                        upgraded_version = '{}.{}.{}'.format(major_ver, 0, 0)
                                        modules[x]['semver'] = upgraded_version
                                        response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                        response['derived-semantic-version'] = upgraded_version
                                        name_revision = '{}@{}'.format(response['name'], response['revision'])
                                        if self.new_modules.get(name_revision) is None:
                                            self.new_modules[name_revision] = response
                                        else:
                                            self.new_modules[name_revision]['derived-semantic-version'] = response[
                                                'derived-semantic-version']

        if len(self.__unavailable_modules) != 0:
            mf = messageFactory.MessageFactory()
            mf.send_unavailable_modules(self.__unavailable_modules)

    def __parse_dependents(self):
        x = 0
        if self.__existing_modules_dict.values() is not None:
            for mod in self.__all_modules.get('module', []):
                name_revision = '{}@{}'.format(mod['name'], mod['revision'])
                x += 1
                LOGGER.info('Searching dependents for {}. {} out of {}'.format(name_revision, x,
                                                                               len(self.__all_modules['module'])))
                name = mod['name']
                revision = mod['revision']
                new_dependencies = mod.get('dependencies', [])
                mod['dependents'] = mod.get('dependents', [])
                # add dependents to already existing modules based on new dependencies from new modules
                for new_dep in new_dependencies:
                    if new_dep.get('revision'):
                        search = {'name': new_dep['name'], 'revision': new_dep['revision']}
                    else:
                        search = {'name': new_dep['name']}
                    for module in self.__existing_modules_dict.values():
                        if module['name'] == search['name']:
                            rev = search.get('revision')
                            if rev is None or rev == module['revision']:
                                new = {'name': name,
                                       'revision': revision,
                                       'schema': mod['schema']}
                                if module.get('dependents') is None:
                                    module['dependents'] = []
                                if new not in module['dependents']:
                                    module['dependents'].append(new)
                                    name_revision = '{}@{}'.format(module['name'], module['revision'])
                                    if self.new_modules.get(name_revision) is None:
                                        self.new_modules[name_revision] = module
                                    else:
                                        if self.new_modules[name_revision].get('dependents') is None:
                                            self.new_modules[name_revision]['dependents'] = module['dependents']
                                        else:
                                            self.new_modules[name_revision]['dependents'].append(new)

                # add dependents to new modules based on existing modules dependencies
                for module in self.__existing_modules_dict.values():
                    if module.get('dependencies') is not None:
                        for dependency in module['dependencies']:
                            n = dependency.get('name')
                            if n == name:
                                r = dependency.get('revision')
                                if r is not None:
                                    if r == revision:
                                        new = {'name': module['name'],
                                               'revision': module['revision'],
                                               'schema': module['schema']}
                                        if new not in mod['dependents']:
                                            mod['dependents'].append(new)
                                            name_revision = '{}@{}'.format(mod['name'], mod['revision'])
                                            if self.new_modules.get(name_revision) is None:
                                                self.new_modules[name_revision] = mod
                                            else:
                                                if self.new_modules[name_revision].get('dependents') is None:
                                                    self.new_modules[name_revision]['dependents'] = mod['dependents']
                                                else:
                                                    self.new_modules[name_revision]['dependents'].append(new)
                                else:
                                    if n == name:
                                        new = {'name': module['name'],
                                               'revision': module['revision'],
                                               'schema': module['schema']}
                                        if new not in mod['dependents']:
                                            mod['dependents'].append(new)
                                            name_revision = '{}@{}'.format(mod['name'], mod['revision'])
                                            if self.new_modules.get(name_revision) is None:
                                                self.new_modules[name_revision] = mod
                                            else:
                                                if self.new_modules[name_revision].get('dependents') is None:
                                                    self.new_modules[name_revision]['dependents'] = mod['dependents']
                                                else:
                                                    self.new_modules[name_revision]['dependents'].append(new)

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

    def __check_if_latest_revision(self, module: dict):
        """ Check if the parsed module is the latest revision.

        Argument:
            :param module   (dict) Details of currently parsed module
        """
        return module.get('revision', '') >= self.__latest_revisions.get(module['name'], '')
