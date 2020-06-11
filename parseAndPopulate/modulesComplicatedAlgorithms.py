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
import io
import multiprocessing
import time
from threading import Thread

from pyang import plugin

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"
import json
import os
import sys
from datetime import datetime

import dateutil.parser
import requests
from pyang.plugins.check_update import check_update
from pyang.plugins.tree import emit_tree

from utility import log
from utility.util import find_first_file
from utility.yangParser import create_context


class ModulesComplicatedAlgorithms:

    def __init__(self, log_directory, yangcatalog_api_prefix, credentials, protocol, ip, port,
                 save_file_dir, direc, all_modules, yang_models_dir, temp_dir):
        global LOGGER
        LOGGER = log.get_logger('modulesComplicatedAlgorithms', log_directory + '/parseAndPopulate.log')
        if all_modules is None:
            with open(direc + '/prepare.json', 'r') as f:
                self.__all_modules = json.load(f)
        else:
            self.__all_modules = all_modules
        self.__yangcatalog_api_prefix = yangcatalog_api_prefix
        self.__new_modules = {}
        self.__credentials = credentials
        self.__save_file_dir = save_file_dir
        self.__path = None
        self.__prefix = '{}://{}:{}'.format(protocol, ip, port)
        self.__yang_models = yang_models_dir
        self.temp_dir = temp_dir
        self.recursion_limit = sys.getrecursionlimit()
        self.__direc = direc
        self.__trees = dict()
        LOGGER.info('get all existing modules')
        response = requests.get(self.__yangcatalog_api_prefix + 'search/modules',
                                headers={'Accept': 'application/json'})
        existing_modules = response.json().get('module')
        self.__existing_modules_dict = {}
        for m in existing_modules:
            self.__existing_modules_dict['{}@{}'.format(m['name'], m['revision'])] = m

    def parse_non_requests(self):
        LOGGER.info("parsing tree types")
        sys.setrecursionlimit(10000)
        self.__resolve_tree_type()

    def parse_requests(self):
        LOGGER.info("parsing semantic version")
        process_semver = multiprocessing.Process(target=self.__parse_semver)
        process_semver.start()
        LOGGER.info("parsing dependents")
        process_dependents = multiprocessing.Process(target=self.__parse_dependents)
        process_dependents.start()
        LOGGER.info('parsing expiration')
        process_expire = multiprocessing.Process(target=self.__parse_expire)
        process_expire.start()
        process_expire.join()
        process_dependents.join()
        process_semver.join()
        sys.setrecursionlimit(self.recursion_limit)

    def merge_modules_and_remove_not_updated(self):
        start = time.time()
        ret_modules = {}
        for val in self.__new_modules.values():
            key = '{}@{}'.format(val['name'], val['revision'])
            old_module = self.__existing_modules_dict.get(key)
            if old_module is None:
                ret_modules[key] = val
            else:
                if (old_module.get('tree-type') != val.get('tree-type') or
                        old_module.get('expires') != val.get('expires') or
                        old_module.get('expired') != val.get('expired') or
                        old_module.get('derived-semantic-version') != val.get('derived-semantic-version')):
                    LOGGER.debug('{}@{} tree {} vs {}, expires {} vs {}, expired {} vs {}, semver {} vs {}'
                                 .format(val['name'], val['revision'], old_module.get('tree-type'),
                                         val.get('tree-type'), old_module.get('expires'), val.get('expires'),
                                         old_module.get('expired'), val.get('expired'),
                                         old_module.get('derived-semantic-version'), val.get('derived-semantic-version')
                                         )
                                 )
                    if ret_modules.get(key) is None:
                        ret_modules[key] = val
                    else:
                        ret_modules[key]['name'] = val['name']
                        ret_modules[key]['revision'] = val['revision']
                        ret_modules[key]['organization'] = val['organization']
                        ret_modules[key]['tree-type'] = val.get('tree-type')
                        ret_modules[key]['expires'] = val.get('expires')
                        ret_modules[key]['expired'] = val.get('expired')
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
                            if (dep.get('name') == old_dep.get('name') or
                                    dep.get('revision') == old_dep.get('revision') or
                                    dep.get('schema') == old_dep.get('schema')):
                                found = True
                                break
                        if not found:
                            if ret_modules.get(key) is None:
                                ret_modules[key] = val
                                break
                            if ret_modules[key].get('dependents') is None:
                                ret_modules[key]['dependents'] = []
                            ret_modules[key]['name'] = val['name']
                            ret_modules[key]['revision'] = val['revision']
                            ret_modules[key]['organization'] = val['organization']
                            ret_modules[key]['dependents'].append(dep)
                            LOGGER.debug('dependents {} vs {}'.format(old_module['dependents'], dep))
                            break
        end = time.time()
        LOGGER.debug('time taken to merge and remove {} seconds'.format(end - start))
        return list(ret_modules.values())

    def populate(self):
        LOGGER.info('populate with module complicated data. amount of new data is {}'.format(len(self.__new_modules.values())))
        module_to_populate = self.merge_modules_and_remove_not_updated()
        LOGGER.info('populate with module complicated data after merging. amount of new data is {}'.format(len(module_to_populate)))
        x = -1
        for x in range(0, int(len(module_to_populate) / 250)):
            json_modules_data = json.dumps({'modules': {'module': module_to_populate[x * 250: (x * 250) + 250]}})
            if '{"module": []}' not in json_modules_data:
                url = self.__prefix + '/restconf/data/yang-catalog:catalog/modules/'
                response = requests.patch(url, data=json_modules_data,
                                          auth=(self.__credentials[0],
                                                self.__credentials[1]),
                                          headers={
                                              'Accept': 'application/yang-data+json',
                                              'Content-type': 'application/yang-data+json'})
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
            url = self.__prefix + '/restconf/data/yang-catalog:catalog/modules/'
            response = requests.patch(url, data=json_modules_data,
                                      auth=(self.__credentials[0],
                                            self.__credentials[1]),
                                      headers={
                                          'Accept': 'application/yang-data+json',
                                          'Content-type': 'application/yang-data+json'})
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
            LOGGER.warning('Could not send a load-cache request')

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
            if output.split('\n')[1].endswith('-state'):
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

        def is_transational(rows, output):
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
        for module in self.__all_modules['module']:
            x += 1
            self.__path = '{}/{}@{}.yang'.format(self.__save_file_dir,
                                                 module['name'],
                                                 module['revision'])
            LOGGER.info(
                'Searching tree type for {}. {} out of {}'.format(module['name'], x, len(self.__all_modules['module'])))
            LOGGER.debug(
                'Get tree type from tag from module {}'.format(self.__path))
            if '{}@{}'.format(module['name'], module['revision']) in self.__trees:
                stdout = self.__trees['{}@{}'.format(module['name'], module['revision'])]
            else:
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
                    name_revision = '{}@{}'.format(module['name'], module['revision'])
                    if self.__new_modules.get(name_revision) is None:
                        self.__new_modules[name_revision] = module
                    else:
                        self.__new_modules[name_revision]['tree-type'] = 'unclassified'
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
                    self.__trees['{}@{}'.format(module['name'], module['revision'])] = stdout
                except:
                    module['tree-type'] = 'not-applicable'
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
                elif is_combined(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'nmda-compatible'
                elif is_openconfig(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'openconfig'
                elif is_split(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'split'
                elif is_transational(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'transitional-extra'
                else:
                    module['tree-type'] = 'unclassified'
            name_revision = '{}@{}'.format(module['name'], module['revision'])
            if (self.__existing_modules_dict.get(name_revision) is None or
                    self.__existing_modules_dict[name_revision].get('tree-type') != module['tree-type']):
                if self.__new_modules.get(name_revision) is None:
                    self.__new_modules[name_revision] = module
                else:
                    self.__new_modules[name_revision]['tree-type'] = module['tree-type']

    def __parse_semver(self):
        z = 0
        for module in self.__all_modules['module']:
            z += 1
            data = {}
            for m in self.__existing_modules_dict.values():
                if m['name'] == module['name']:
                    if m['revision'] != module['revision']:
                        data['{}@{}'.format(m['name'], m['revision'])] = m

            LOGGER.info(
                'Searching semver for {}. {} out of {}'.format(module['name'], z, len(self.__all_modules['module'])))
            if len(data) == 0:
                module['derived-semantic-version'] = '1.0.0'
                name_revision = '{}@{}'.format(module['name'], module['revision'])
                if self.__new_modules.get(name_revision) is None:
                    self.__new_modules[name_revision] = module
                else:
                    self.__new_modules[name_revision]['derived-semantic-version'] = module['derived-semantic-version']
            else:
                rev = module['revision'].split('-')
                try:
                    date = datetime(int(rev[0]), int(rev[1]), int(rev[2]))
                except Exception as e:
                    LOGGER.error('Failed to process revision for {}: (rev: {})'.format(module['name'], rev))
                    try:
                        if int(rev[1]) == 2 and int(rev[2]) == 29:
                            date = datetime(int(rev[0]), int(rev[1]), 28)
                        else:
                            date = datetime(1970, 1, 1)
                    except Exception:
                        date = datetime(1970, 1, 1)
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

                for key, mod in mod_list:
                    module_temp = {}
                    revision = mod['revision']
                    if revision == module['revision']:
                        continue
                    rev = revision.split('-')
                    module_temp['revision'] = revision

                    try:
                        module_temp['date'] = datetime(int(rev[0]), int(rev[1]), int(rev[2]))
                    except Exception:
                        LOGGER.warning(
                            'Failed to process revision for {}: (rev: {}) setting it to 28th'.format(module['name'],
                                                                                                     rev))
                        try:
                            if int(rev[1]) == 2 and int(rev[2]) == 29:
                                module_temp['date'] = datetime(int(rev[0]), int(rev[1]), 28)
                            else:
                                module_temp['date'] = datetime(1970, 1, 1)
                        except Exception:
                            module_temp['date'] = datetime(1970, 1, 1)
                    module_temp['name'] = mod['name']
                    module_temp['organization'] = mod.get('organization')
                    module_temp['schema'] = mod.get('schema')
                    module_temp['compilation'] = mod.get('compilation-status', 'PENDING')
                    module_temp['semver'] = mod.get('derived-semantic-version')
                    if module_temp['semver'] is None:
                        semver_exist = False
                    modules.append(module_temp)
                data['{}@{}'.format(module['name'], module['revision'])] = module
                if len(modules) == 1:
                    module['derived-semantic-version'] = '1.0.0'
                    name_revision = '{}@{}'.format(module['name'], module['revision'])
                    if self.__new_modules.get(name_revision) is None:
                        self.__new_modules[name_revision] = module
                    else:
                        self.__new_modules[name_revision]['derived-semantic-version'] = module['derived-semantic-version']
                    continue
                modules = sorted(modules, key=lambda k: k['date'])
                # If we are adding new module to the end (latest revision) of existing modules with this name
                # and all modules with this name have semver already assigned exept the last one
                if modules[-1]['date'] == date and semver_exist:
                    if modules[-1]['compilation'] != 'passed':
                        versions = modules[-2]['semver'].split('.')
                        ver = int(versions[0])
                        ver += 1
                        upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                        module['derived-semantic-version'] = upgraded_version
                        name_revision = '{}@{}'.format(module['name'], module['revision'])
                        if self.__new_modules.get(name_revision) is None:
                            self.__new_modules[name_revision] = module
                        else:
                            self.__new_modules[name_revision]['derived-semantic-version'] = module['derived-semantic-version']
                    else:
                        if modules[-2]['compilation'] != 'passed':
                            versions = modules[-2]['semver'].split('.')
                            ver = int(versions[0])
                            ver += 1
                            upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                            module['derived-semantic-version'] = upgraded_version
                            name_revision = '{}@{}'.format(module['name'], module['revision'])
                            if self.__new_modules.get(name_revision) is None:
                                self.__new_modules[name_revision] = module
                            else:
                                self.__new_modules[name_revision]['derived-semantic-version'] = module['derived-semantic-version']
                            continue
                        else:
                            schema2 = '{}/{}@{}.yang'.format(self.__save_file_dir,
                                                             modules[-2]['name'],
                                                             modules[-2]['revision'])
                            schema1 = '{}/{}@{}.yang'.format(self.__save_file_dir,
                                                             modules[-1]['name'],
                                                             modules[-1]['revision'])
                            plugin.init([])
                            ctx = create_context(
                                '{}:{}'.format(os.path.abspath(self.__yang_models), self.__save_file_dir))
                            ctx.opts.lint_namespace_prefixes = []
                            ctx.opts.lint_modulename_prefixes = []
                            for p in plugin.plugins:
                                p.setup_ctx(ctx)
                            with open(schema1, 'r', errors='ignore') as f:
                                a1 = ctx.add_module(schema1, f.read())
                            ctx.opts.check_update_from = schema2
                            ctx.opts.old_path = [os.path.abspath(self.__yang_models)]
                            ctx.opts.verbose = False
                            ctx.opts.old_path = []
                            ctx.opts.old_deviation = []
                            retry = 5
                            while retry:
                                try:
                                    ctx.validate()
                                    check_update(ctx, schema2, a1)
                                    break
                                except Exception as e:
                                    retry -= 1
                                    if retry == 0:
                                        raise e
                            if len(ctx.errors) == 0:
                                if ('{}@{}'.format(modules[-1]['name'], modules[-1]['revision']) in self.__trees and
                                        '{}@{}'.format(modules[-2]['name'], modules[-2]['revision']) in self.__trees):
                                    stdout = self.__trees['{}@{}'.format(modules[-1]['name'], modules[-1]['revision'])]
                                    stdout2 = self.__trees['{}@{}'.format(modules[-2]['name'], modules[-2]['revision'])]
                                else:
                                    with open(schema2, 'r', errors='ignore') as f:
                                        a2 = ctx.add_module(schema2, f.read())
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
                                        emit_tree(ctx, [a1], f, ctx.opts.tree_depth,
                                                  ctx.opts.tree_line_length, path)
                                        stdout = f.getvalue()
                                    except:
                                        stdout = ""

                                    try:
                                        f = io.StringIO()
                                        emit_tree(ctx, [a2], f, ctx.opts.tree_depth,
                                                  ctx.opts.tree_line_length, path)
                                        stdout2 = f.getvalue()
                                    except:
                                        stdout2 = "2"

                                if stdout == stdout2:
                                    versions = modules[-2]['semver'].split('.')
                                    ver = int(versions[2])
                                    ver += 1
                                    upgraded_version = '{}.{}.{}'.format(versions[0],
                                                                         versions[1],
                                                                         ver)
                                    module['derived-semantic-version'] = upgraded_version
                                    name_revision = '{}@{}'.format(module['name'], module['revision'])
                                    if self.__new_modules.get(name_revision) is None:
                                        self.__new_modules[name_revision] = module
                                    else:
                                        self.__new_modules[name_revision]['derived-semantic-version'] = module[
                                            'derived-semantic-version']
                                    continue
                                else:
                                    versions = modules[-2]['semver'].split('.')
                                    ver = int(versions[1])
                                    ver += 1
                                    upgraded_version = '{}.{}.{}'.format(versions[0],
                                                                         ver, 0)
                                    module['derived-semantic-version'] = upgraded_version
                                    name_revision = '{}@{}'.format(module['name'], module['revision'])
                                    if self.__new_modules.get(name_revision) is None:
                                        self.__new_modules[name_revision] = module
                                    else:
                                        self.__new_modules[name_revision]['derived-semantic-version'] = module[
                                            'derived-semantic-version']
                                    continue
                            else:
                                versions = modules[-2]['semver'].split('.')
                                ver = int(versions[0])
                                ver += 1
                                upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                                module['derived-semantic-version'] = upgraded_version
                                name_revision = '{}@{}'.format(module['name'], module['revision'])
                                if self.__new_modules.get(name_revision) is None:
                                    self.__new_modules[name_revision] = module
                                else:
                                    self.__new_modules[name_revision]['derived-semantic-version'] = module[
                                        'derived-semantic-version']
                                continue
                else:
                    mod = {}
                    mod['name'] = modules[0]['name']
                    mod['revision'] = modules[0]['revision']
                    mod['organization'] = modules[0]['organization']
                    modules[0]['semver'] = '1.0.0'
                    response = data['{}@{}'.format(mod['name'], mod['revision'])]
                    response['derived-semantic-version'] = '1.0.0'
                    name_revision = '{}@{}'.format(response['name'], response['revision'])
                    if self.__new_modules.get(name_revision) is None:
                        self.__new_modules[name_revision] = response
                    else:
                        self.__new_modules[name_revision]['derived-semantic-version'] = response[
                            'derived-semantic-version']
                    for x in range(1, len(modules)):
                        mod = {}
                        mod['name'] = modules[x]['name']
                        mod['revision'] = modules[x]['revision']
                        mod['organization'] = modules[x]['organization']
                        if modules[x]['compilation'] != 'passed':
                            versions = modules[x - 1]['semver'].split('.')
                            ver = int(versions[0])
                            ver += 1
                            upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                            modules[x]['semver'] = upgraded_version
                            response = data['{}@{}'.format(mod['name'], mod['revision'])]
                            response['derived-semantic-version'] = upgraded_version
                            name_revision = '{}@{}'.format(response['name'], response['revision'])
                            if self.__new_modules.get(name_revision) is None:
                                self.__new_modules[name_revision] = response
                            else:
                                self.__new_modules[name_revision]['derived-semantic-version'] = response[
                                    'derived-semantic-version']
                        else:
                            if modules[x - 1]['compilation'] != 'passed':
                                versions = modules[x - 1]['semver'].split('.')
                                ver = int(versions[0])
                                ver += 1
                                upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                                modules[x]['semver'] = upgraded_version
                                response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                response['derived-semantic-version'] = upgraded_version
                                name_revision = '{}@{}'.format(response['name'], response['revision'])
                                if self.__new_modules.get(name_revision) is None:
                                    self.__new_modules[name_revision] = response
                                else:
                                    self.__new_modules[name_revision]['derived-semantic-version'] = response[
                                        'derived-semantic-version']
                                continue
                            else:
                                schema2 = '{}/{}@{}.yang'.format(
                                    self.__save_file_dir,
                                    modules[x]['name'],
                                    modules[x]['revision'])
                                schema1 = '{}/{}@{}.yang'.format(
                                    self.__save_file_dir,
                                    modules[x - 1]['name'],
                                    modules[x - 1]['revision'])
                                plugin.init([])
                                ctx = create_context(
                                    '{}:{}'.format(os.path.abspath(self.__yang_models), self.__save_file_dir))
                                ctx.opts.lint_namespace_prefixes = []
                                ctx.opts.lint_modulename_prefixes = []
                                for p in plugin.plugins:
                                    p.setup_ctx(ctx)
                                with open(schema1, 'r', errors='ignore') as f:
                                    a1 = ctx.add_module(schema1, f.read())
                                ctx.opts.check_update_from = schema2
                                ctx.opts.old_path = [os.path.abspath(self.__yang_models)]
                                ctx.opts.verbose = False
                                ctx.opts.old_path = []
                                ctx.opts.old_deviation = []
                                retry = 5
                                while retry:
                                    try:
                                        ctx.validate()
                                        check_update(ctx, schema2, a1)
                                        break
                                    except Exception as e:
                                        retry -= 1
                                        if retry == 0:
                                            raise e
                                if len(ctx.errors) == 0:
                                    if ('{}@{}'.format(modules[x - 1]['name'], modules[x - 1]['revision']) in self.__trees and
                                            '{}@{}'.format(modules[x]['name'], modules[x]['revision']) in self.__trees):
                                        stdout = self.__trees['{}@{}'.format(modules[-1]['name'], modules[x - 1]['revision'])]
                                        stdout2 = self.__trees['{}@{}'.format(modules[x]['name'], modules[x]['revision'])]
                                    else:
                                        with open(schema2, 'r', errors='ignore') as f:
                                            a2 = ctx.add_module(schema2, f.read())
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
                                            emit_tree(ctx, [a1], f, ctx.opts.tree_depth,
                                                      ctx.opts.tree_line_length, path)
                                            stdout = f.getvalue()
                                        except:
                                            stdout = ""
                                        try:
                                            f = io.StringIO()

                                            emit_tree(ctx, [a2], f, ctx.opts.tree_depth,
                                                      ctx.opts.tree_line_length, path)
                                            stdout2 = f.getvalue()
                                        except:
                                            stdout2 = "2"
                                    if stdout == stdout2:
                                        versions = modules[x - 1]['semver'].split('.')
                                        ver = int(versions[2])
                                        ver += 1
                                        upgraded_version = '{}.{}.{}'.format(versions[0], versions[1], ver)
                                        modules[x]['semver'] = upgraded_version
                                        response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                        response['derived-semantic-version'] = upgraded_version
                                        name_revision = '{}@{}'.format(response['name'], response['revision'])
                                        if self.__new_modules.get(name_revision) is None:
                                            self.__new_modules[name_revision] = response
                                        else:
                                            self.__new_modules[name_revision]['derived-semantic-version'] = response[
                                                'derived-semantic-version']
                                    else:
                                        versions = modules[x - 1]['semver'].split('.')
                                        ver = int(versions[1])
                                        ver += 1
                                        upgraded_version = '{}.{}.{}'.format(versions[0], ver, 0)
                                        modules[x]['semver'] = upgraded_version
                                        response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                        response['derived-semantic-version'] = upgraded_version
                                        name_revision = '{}@{}'.format(response['name'], response['revision'])
                                        if self.__new_modules.get(name_revision) is None:
                                            self.__new_modules[name_revision] = response
                                        else:
                                            self.__new_modules[name_revision]['derived-semantic-version'] = response[
                                                'derived-semantic-version']
                                else:
                                    versions = modules[x - 1]['semver'].split('.')
                                    ver = int(versions[0])
                                    ver += 1
                                    upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                                    modules[x]['semver'] = upgraded_version
                                    response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                    response['derived-semantic-version'] = upgraded_version
                                    name_revision = '{}@{}'.format(response['name'], response['revision'])
                                    if self.__new_modules.get(name_revision) is None:
                                        self.__new_modules[name_revision] = response
                                    else:
                                        self.__new_modules[name_revision]['derived-semantic-version'] = response[
                                            'derived-semantic-version']

    def __parse_dependents(self):
        x = 0
        if self.__existing_modules_dict.values() is not None:
            for mod in self.__all_modules['module']:
                x += 1
                LOGGER.info('Searching dependents for {}. {} out of {}'.format(mod['name'], x,
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
                            if rev is not None:
                                if rev == module['revision']:
                                    new = {'name': name,
                                           'revision': revision,
                                           'schema': mod['schema']}
                                    if module.get('dependents') is None:
                                        module['dependents'] = []
                                    if new not in module['dependents']:
                                        module['dependents'].append(new)
                                        name_revision = '{}@{}'.format(module['name'], module['revision'])
                                        if self.__new_modules.get(name_revision) is None:
                                            self.__new_modules[name_revision] = module
                                        else:
                                            if self.__new_modules[name_revision].get('dependents') is None:
                                                self.__new_modules[name_revision]['dependents'] = module['dependents']
                                            else:
                                                self.__new_modules[name_revision]['dependents'].append(new)
                            else:
                                new = {'name': name,
                                       'revision': revision,
                                       'schema': mod['schema']}
                                if module.get('dependents') is None:
                                    module['dependents'] = []
                                if new not in module['dependents']:
                                    module['dependents'].append(new)
                                    name_revision = '{}@{}'.format(module['name'], module['revision'])
                                    if self.__new_modules.get(name_revision) is None:
                                        self.__new_modules[name_revision] = module
                                    else:
                                        if self.__new_modules[name_revision].get('dependents') is None:
                                            self.__new_modules[name_revision]['dependents'] = module['dependents']
                                        else:
                                            self.__new_modules[name_revision]['dependents'].append(new)

                # add dependents to new modules based on existing modules dependencies
                for module in self.__existing_modules_dict.values():
                    if module.get('dependencies') is not None:
                        for dep in module['dependencies']:
                            n = dep.get('name')
                            if n == name:
                                r = dep.get('revision')
                                if r is not None:
                                    if r == revision:
                                        new = {'name': module['name'],
                                               'revision': module['revision'],
                                               'schema': module['schema']}
                                        if new not in mod['dependents']:
                                            mod['dependents'].append(new)
                                            name_revision = '{}@{}'.format(mod['name'], mod['revision'])
                                            if self.__new_modules.get(name_revision) is None:
                                                self.__new_modules[name_revision] = mod
                                            else:
                                                if self.__new_modules[name_revision].get('dependents') is None:
                                                    self.__new_modules[name_revision]['dependents'] = mod['dependents']
                                                else:
                                                    self.__new_modules[name_revision]['dependents'].append(new)
                                else:
                                    if n == name:
                                        new = {'name': module['name'],
                                               'revision': module['revision'],
                                               'schema': module['schema']}
                                        if new not in mod['dependents']:
                                            mod['dependents'].append(new)
                                            name_revision = '{}@{}'.format(mod['name'], mod['revision'])
                                            if self.__new_modules.get(name_revision) is None:
                                                self.__new_modules[name_revision] = mod
                                            else:
                                                if self.__new_modules[name_revision].get('dependents') is None:
                                                    self.__new_modules[name_revision]['dependents'] = mod['dependents']
                                                else:
                                                    self.__new_modules[name_revision]['dependents'].append(new)

    def __parse_expire(self):
        x = 0
        if self.__existing_modules_dict.values() is not None:
            for mod in self.__all_modules['module']:
                x += 1
                LOGGER.info('Searching expiration for {}. {} out of {}'.format(mod['name'], x,
                                                                               len(self.__all_modules['module'])))
                exists = False
                existing_module = None
                for module in self.__existing_modules_dict.values():
                    if module['name'] == mod['name'] and module['revision'] == mod['revision'] and \
                            module['organization'] == mod['organization']:
                        exists = True
                        existing_module = module
                        break
                expiration_date = None
                if exists:
                    if existing_module.get('reference') and 'datatracker.ietf.org' in existing_module.get('reference'):
                        expiration_date = existing_module.get('expires')
                        if expiration_date:
                            if dateutil.parser.parse(expiration_date).date() < datetime.now().date():
                                expired = True
                            else:
                                expired = False
                        else:
                            expired = 'not-applicable'
                    else:
                        expired = 'not-applicable'
                else:
                    if mod.get('reference') and 'datatracker.ietf.org' in mod.get('reference'):
                        ref = mod.get('reference').split('/')[-1]
                        url = ('https://datatracker.ietf.org/api/v1/doc/document/'
                               + ref + '/?format=json')
                        response = requests.get(url)
                        if response.status_code == 200:
                            data = response.json()
                            expiration_date = data['expires']
                            if dateutil.parser.parse(expiration_date).date() < datetime.now().date():
                                expired = True
                            else:
                                expired = False
                        else:
                            expired = 'not-applicable'
                    else:
                        expired = 'not-applicable'
                if expiration_date is not None:
                    mod['expires'] = expiration_date
                mod['expired'] = expired
                if (existing_module is None or
                        mod['expired'] != existing_module.get('expired') or
                        mod.get('expires') != existing_module.get('expires')):
                    name_revision = '{}@{}'.format(mod['name'], mod['revision'])
                    if self.__new_modules.get(name_revision) is None:
                        self.__new_modules[name_revision] = mod
                    else:
                        if mod.get('expires') is not None:
                            self.__new_modules[name_revision]['expires'] = mod['expires']
                        if mod.get('expired') is not None:
                            self.__new_modules[name_revision]['expired'] = mod['expired']

    def __find_file(self, name, revision='*'):
        yang_file = find_first_file('/'.join(self.__path.split('/')[0:-1]),
                                    name + '.yang'
                                    , name + '@' + revision + '.yang')
        if yang_file is None:
            yang_file = find_first_file(self.__yang_models, name + '.yang',
                                        name + '@' + revision + '.yang')
        return yang_file
