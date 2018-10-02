"""
This is a class of a single module to parse all the more complicated
metadata that we can get out of the module. From this class parse
method is called which will call all the other methods that
will get the rest of the metadata. This is parsed separately to
make sure that metadata that are quickly parsed are already pushed
into the database and these metadata will get there later.
"""
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
import os
import sys

from pyang.plugins.check_update import check_update
from pyang.plugins.tree import emit_tree

from utility.yangParser import create_context

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import json
from datetime import datetime

import requests

from utility import log
from utility.util import find_first_file


class ModulesComplicatedAlgorithms:

    def __init__(self, log_directory, yangcatalog_api_prefix, credentials, protocol, ip, port,
                 save_file_dir, direc, all_modules, yang_models_dir, temp_dir):
        global LOGGER
        LOGGER = log.get_logger('modulesComplicatedAlgorithms', log_directory + '/parseAndPopulate.log')
        if all_modules is None:
            with open('../parseAndPopulate/' + direc + '/prepare.json', 'r') as f:
                self.__all_modules = json.load(f)
        else:
            self.__all_modules = all_modules
        self.__yangcatalog_api_prefix = yangcatalog_api_prefix
        self.__new_modules = []
        self.__credentials = credentials
        self.__save_file_dir = save_file_dir
        self.__path = None
        self.__prefix = '{}://{}:{}'.format(protocol, ip, port)
        self.__yang_models = yang_models_dir
        self.temp_dir = temp_dir

    def parse_non_requests(self):
        LOGGER.info("parsing tree types")
        self.__resolve_tree_type()

    def parse_requests(self):
        LOGGER.info('get all modules for semver and dependents algorithm')
        response = requests.get(self.__yangcatalog_api_prefix + 'search/modules',
                                headers={'Accept': 'application/json'})
        modules = response.json().get('module')
        LOGGER.info("parsing semantic version")
        self.__parse_semver(modules)
        LOGGER.info("parsing dependents")
        self.__parse_dependents(modules)

    def populate(self):
        LOGGER.info('populate with module complicated data. amount of new data is {}'.format(len(self.__new_modules)))
        mod = len(self.__new_modules) % 250
        for x in range(0, int(len(self.__new_modules) / 250)):
            json_modules_data = json.dumps({'modules': {'module': self.__new_modules[x * 250: (x * 250) + 250]}})
            if '{"module": []}' not in json_modules_data:
                url = self.__prefix + '/api/config/catalog/modules/'
                response = requests.patch(url, data=json_modules_data,
                                          auth=(self.__credentials[0],
                                                self.__credentials[1]),
                                          headers={
                                              'Accept': 'application/vnd.yang.data+json',
                                              'Content-type': 'application/vnd.yang.data+json'})
                if response.status_code < 200 or response.status_code > 299:
                    LOGGER.error('Request with body on path {} failed with {}'.
                                 format(json_modules_data, url,
                                        response.text))
        rest = int(len(self.__new_modules) / 250) * 250
        json_modules_data = json.dumps(
            {'modules': {'module': self.__new_modules[rest: rest + mod]}})
        if '{"module": []}' not in json_modules_data:
            url = self.__prefix + '/api/config/catalog/modules/'
            response = requests.patch(url, data=json_modules_data,
                                      auth=(self.__credentials[0],
                                            self.__credentials[1]),
                                      headers={
                                          'Accept': 'application/vnd.yang.data+json',
                                          'Content-type': 'application/vnd.yang.data+json'})
            if response.status_code < 200 or response.status_code > 299:
                LOGGER.error('Request with body on path {} failed with {}'.
                             format(json_modules_data, url,
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
                if len(row.split('augment')[0]) == 2:
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
                    ctx = create_context('{}:{}'.format(os.path.abspath(self.__yang_models), self.__save_file_dir))
                    with open(coresponding_nmda_file, 'r') as f:
                        a = ctx.add_module(coresponding_nmda_file, f.read())
                    if ctx.opts.tree_path is not None:
                        path = ctx.opts.tree_path.split('/')
                        if path[0] == '':
                            path = path[1:]
                    else:
                        path = None
                    with open('{}/pyang_temp.txt'.format(self.temp_dir), 'w')as f:
                        emit_tree(ctx, [a], f, ctx.opts.tree_depth,
                                  ctx.opts.tree_line_length, path)
                    with open('{}/pyang_temp.txt'.format(self.temp_dir), 'r')as f:
                        stdout = f.read()
                    os.unlink('{}/pyang_temp.txt'.format(self.temp_dir))

                    pyang_list_of_rows = stdout.split('\n')[2:]
                    if len(ctx.errors) != 0 and len(stdout) == 0:
                        return False
                    elif stdout == '':
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
            LOGGER.info('Searching tree type for {}. {} out of {}'.format(module['name'], x, len(self.__all_modules['module'])))
            LOGGER.debug(
                'Get tree type from tag from module {}'.format(self.__path))
            ctx = create_context('{}:{}'.format(os.path.abspath(self.__yang_models), self.__save_file_dir))
            with open(self.__path, 'r') as f:
                a = ctx.add_module(self.__path, f.read())
            if ctx.opts.tree_path is not None:
                path = ctx.opts.tree_path.split('/')
                if path[0] == '':
                    path = path[1:]
            else:
                path = None
            with open('{}/pyang_temp.txt'.format(self.temp_dir), 'w')as f:
                emit_tree(ctx, [a], f, ctx.opts.tree_depth,
                          ctx.opts.tree_line_length, path)
            with open('{}/pyang_temp.txt'.format(self.temp_dir), 'r')as f:
                stdout = f.read()
            os.unlink('{}/pyang_temp.txt'.format(self.temp_dir))

            if len(ctx.errors) != 0 and len(stdout) == 0:
                LOGGER.debug(
                    'Could not use pyang to generate tree because of errors on module {}'.
                        format(self.__path))
                module['tree-type'] = 'unclassified'
            elif stdout == '':
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
                elif is_transational(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'transitional-extra'
                elif is_openconfig(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'openconfig'
                elif is_split(pyang_list_of_rows, stdout):
                    module['tree-type'] = 'split'
                else:
                    module['tree-type'] = 'unclassified'
            self.__new_modules.append(module)

    def __parse_semver(self, existing_modules):
        z = 0
        for module in self.__all_modules['module']:
            z += 1
            data = {}
            for m in existing_modules:
                if m['name'] == module['name']:
                    if m['revision'] != module['revision']:
                        data['{}@{}'.format(m['name'], m['revision'])] = m

            LOGGER.info('Searching semver for {}. {} out of {}'.format(module['name'], z, len(self.__all_modules['module'])))
            if len(data) == 0:
                module['derived-semantic-version'] = '1.0.0'
                self.__new_modules.append(module)
            else:
                rev = module['revision'].split('-')
                try:
                    date = datetime(int(rev[0]), int(rev[1]), int(rev[2]))
                except Exception as e:
                    LOGGER.error('Failed to process revision for {}: (rev: {})'.format(module['name'], rev))
                    if int(rev[1]) == 2 and int(rev[2]) == 29:
                        date = datetime(int(rev[0]), int(rev[1]), 28)
                    else:
                        raise Exception(e)
                module_temp = {}
                module_temp['name'] = module['name']
                module_temp['revision'] = module['revision']
                module_temp['organization'] = module['organization']
                module_temp['compilation'] = module['compilation-status']
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
                        LOGGER.warning('Failed to process revision for {}: (rev: {}) setting it to 28th'.format(module['name'], rev))
                        if int(rev[1]) == 2 and int(rev[2]) == 29:
                            module_temp['date'] = datetime(int(rev[0]), int(rev[1]), 28)
                    module_temp['name'] = mod['name']
                    module_temp['organization'] = mod['organization']
                    module_temp['schema'] = mod.get('schema')
                    module_temp['compilation'] = mod['compilation-status']
                    module_temp['semver'] = mod.get('derived-semantic-version')
                    if module_temp['semver'] is None:
                        semver_exist = False
                    modules.append(module_temp)
                data['{}@{}'.format(module['name'], module['revision'])] = module
                if len(modules) == 1:
                    module['derived-semantic-version'] = '1.0.0'
                    self.__new_modules.append(module)
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
                        self.__new_modules.append(module)
                    else:
                        if modules[-2]['compilation'] != 'passed':
                            versions = modules[-2]['semver'].split('.')
                            ver = int(versions[0])
                            ver += 1
                            upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                            module['derived-semantic-version'] = upgraded_version
                            self.__new_modules.append(module)
                            continue
                        else:
                            schema2 = '{}/{}@{}.yang'.format(self.__save_file_dir,
                                                            modules[-2]['name'],
                                                            modules[-2]['revision'])
                            schema1 = '{}/{}@{}.yang'.format(self.__save_file_dir,
                                                            modules[-1]['name'],
                                                            modules[-1]['revision'])
                            ctx = create_context('{}:{}'.format(os.path.abspath(self.__yang_models), self.__save_file_dir))
                            with open(schema1, 'r') as f:
                                a1 = ctx.add_module(schema1, f.read())
                            ctx.opts.check_update_from = schema2
                            ctx.opts.old_path = [os.path.abspath(self.__yang_models)]
                            ctx.opts.verbose = False
                            check_update(ctx, schema2, a1)
                            if len(ctx.errors) == 0:
                                with open(schema2, 'r') as f:
                                    a2 = ctx.add_module(schema2, f.read())
                                if ctx.opts.tree_path is not None:
                                    path = ctx.opts.tree_path.split('/')
                                    if path[0] == '':
                                        path = path[1:]
                                else:
                                    path = None
                                with open('{}/pyang_temp.txt'.format(self.temp_dir), 'w')as f:
                                    emit_tree(ctx, [a1], f, ctx.opts.tree_depth,
                                              ctx.opts.tree_line_length, path)
                                with open('{}/pyang_temp.txt'.format(self.temp_dir), 'r')as f:
                                    stdout = f.read()
                                with open('{}/pyang_temp.txt'.format(self.temp_dir), 'w')as f:
                                    emit_tree(ctx, [a2], f, ctx.opts.tree_depth,
                                              ctx.opts.tree_line_length, path)
                                with open('{}/pyang_temp.txt'.format(self.temp_dir), 'r')as f:
                                    stdout2 = f.read()
                                os.unlink('{}/pyang_temp.txt'.format(self.temp_dir))

                                if stdout == stdout2:
                                    versions = modules[-2]['semver'].split('.')
                                    ver = int(versions[2])
                                    ver += 1
                                    upgraded_version = '{}.{}.{}'.format(versions[0],
                                                                         versions[1],
                                                                         ver)
                                    module[
                                        'derived-semantic-version'] = upgraded_version
                                    self.__new_modules.append(module)
                                    continue
                                else:
                                    versions = modules[-2]['semver'].split('.')
                                    ver = int(versions[1])
                                    ver += 1
                                    upgraded_version = '{}.{}.{}'.format(versions[0],
                                                                         ver, 0)
                                    module[
                                        'derived-semantic-version'] = upgraded_version
                                    self.__new_modules.append(module)
                                    continue
                            else:
                                versions = modules[-2]['semver'].split('.')
                                ver = int(versions[0])
                                ver += 1
                                upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                                module[
                                    'derived-semantic-version'] = upgraded_version
                                self.__new_modules.append(module)
                                continue
                else:
                    mod = {}
                    mod['name'] = modules[0]['name']
                    mod['revision'] = modules[0]['revision']
                    mod['organization'] = modules[0]['organization']
                    modules[0]['semver'] = '1.0.0'
                    response = data['{}@{}'.format(mod['name'], mod['revision'])]
                    response['derived-semantic-version'] = '1.0.0'
                    self.__new_modules.append(response)

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
                            self.__new_modules.append(response)
                        else:
                            if modules[x - 1]['compilation'] != 'passed':
                                versions = modules[x - 1]['semver'].split('.')
                                ver = int(versions[0])
                                ver += 1
                                upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                                modules[x]['semver'] = upgraded_version
                                response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                response['derived-semantic-version'] = upgraded_version
                                self.__new_modules.append(response)
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
                                ctx = create_context('{}:{}'.format(os.path.abspath(self.__yang_models), self.__save_file_dir))
                                with open(schema1, 'r') as f:
                                    a1 = ctx.add_module(schema1, f.read())
                                ctx.opts.check_update_from = schema2
                                ctx.opts.old_path = [os.path.abspath(self.__yang_models)]
                                ctx.opts.verbose = False

                                check_update(ctx, schema2, a1)
                                if len(ctx.errors) == 0:
                                    with open(schema2, 'r') as f:
                                        a2 = ctx.add_module(schema2, f.read())
                                    if ctx.opts.tree_path is not None:
                                        path = ctx.opts.tree_path.split('/')
                                        if path[0] == '':
                                            path = path[1:]
                                    else:
                                        path = None
                                    with open('{}/pyang_temp.txt'.format(self.temp_dir), 'w')as f:
                                        emit_tree(ctx, [a1], f, ctx.opts.tree_depth,
                                                  ctx.opts.tree_line_length, path)
                                    with open('{}/pyang_temp.txt'.format(self.temp_dir), 'r')as f:
                                        stdout = f.read()
                                    with open('{}/pyang_temp.txt'.format(self.temp_dir), 'w')as f:
                                        emit_tree(ctx, [a2], f, ctx.opts.tree_depth,
                                                  ctx.opts.tree_line_length, path)
                                    with open('{}/pyang_temp.txt'.format(self.temp_dir), 'r')as f:
                                        stdout2 = f.read()
                                    os.unlink('{}/pyang_temp.txt'.format(self.temp_dir))
                                    if stdout == stdout2:
                                        versions = modules[x - 1]['semver'].split('.')
                                        ver = int(versions[2])
                                        ver += 1
                                        upgraded_version = '{}.{}.{}'.format(versions[0], versions[1], ver)
                                        modules[x]['semver'] = upgraded_version
                                        response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                        response['derived-semantic-version'] = upgraded_version
                                        self.__new_modules.append(response)
                                    else:
                                        versions = modules[x - 1]['semver'].split('.')
                                        ver = int(versions[1])
                                        ver += 1
                                        upgraded_version = '{}.{}.{}'.format(versions[0], ver, 0)
                                        modules[x]['semver'] = upgraded_version
                                        response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                        response['derived-semantic-version'] = upgraded_version
                                        self.__new_modules.append(response)
                                else:
                                    versions = modules[x - 1]['semver'].split('.')
                                    ver = int(versions[0])
                                    ver += 1
                                    upgraded_version = '{}.{}.{}'.format(ver, 0, 0)
                                    modules[x]['semver'] = upgraded_version
                                    response = data['{}@{}'.format(mod['name'], mod['revision'])]
                                    response['derived-semantic-version'] = upgraded_version
                                    self.__new_modules.append(response)

    def __parse_dependents(self, modules):
        x = 0
        if modules is not None:
            for mod in self.__all_modules['module']:
                x += 1
                LOGGER.info('Searching dependents for {}. {} out of {}'.format(mod['name'], x,
                                                                               len(self.__all_modules['module'])))
                name = mod['name']
                revision = mod['revision']
                new_dependencies = mod['dependencies']
                if mod.get('dependents')is None:
                    mod['dependents'] = []
                for new_dep in new_dependencies:
                    if new_dep.get('revision'):
                        search = {'name': new_dep['name'], 'revision': new_dep['revision']}
                    else:
                        search = {'name': new_dep['name']}
                    for module in modules:
                        if module['name'] == search['name']:
                            rev = search.get('revision')
                            if rev is not None and rev == module['revision']:
                                new = {'name': name,
                                       'revision': revision,
                                       'schema': mod['schema']}
                                if module.get('dependents') is None:
                                    module['dependents'] = []
                                if new not in module['dependents']:
                                    module['dependents'].append(new)
                                    self.__new_modules.append(module)
                        if module.get('dependencies') is not None:
                            for dep in module['dependencies']:
                                n = dep.get('name')
                                r = dep.get('revision')
                                if n is not None and r is not None:
                                    if n == name and r == revision:
                                        new = {'name': module['name'],
                                               'revision': module['revision'],
                                               'schema': module['schema']}
                                        if module.get('dependents') is None:
                                            module['dependents'] = []
                                        if new not in mod['dependents']:
                                            mod['dependents'].append(new)
                                else:
                                    if n == name:
                                        new = {'name': module['name'],
                                               'revision': module['revision'],
                                               'schema': module['schema']}
                                        if module.get('dependents') is None:
                                            module['dependents'] = []
                                        if new not in mod['dependents']:
                                            mod['dependents'].append(new)
                if len(mod['dependents']) > 0:
                    self.__new_modules.append(mod)

    def __find_file(self, name, revision='*'):
        yang_file = find_first_file('/'.join(self.__path.split('/')[0:-1]),
                                    name + '.yang'
                                    , name + '@' + revision + '.yang')
        if yang_file is None:
            yang_file = find_first_file(self.__yang_models, name + '.yang',
                                        name + '@' + revision + '.yang')
        return yang_file
