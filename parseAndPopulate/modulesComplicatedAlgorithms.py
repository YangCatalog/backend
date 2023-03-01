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

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import io
import json
import os
import typing as t
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import date

import requests
from pyang import plugin
from pyang.plugins.tree import emit_tree

from elasticsearchIndexing.pyang_plugin.json_tree import emit_tree as emit_json_tree
from redisConnections.redisConnection import RedisConnection
from utility import log, message_factory
from utility.confdService import ConfdService
from utility.fetch_modules import fetch_modules
from utility.util import context_check_update_from, get_yang, revision_to_date
from utility.yangParser import create_context

MAJOR = 0
MINOR = 1
PATCH = 2


class ModuleMetadata(dict):
    """Module metadata as it can be found in the models subtree of yangcatalog."""

    pass


@dataclass
class ModuleSemverMetadata:
    """A reduced set of module metadata relevant to deriving the semantic version of modules."""

    name: str
    revision: str
    organization: str
    compilation: str
    schema: t.Optional[str]
    semver: str
    date: date


@dataclass
class DependentMetadata(t.TypedDict):
    """Metadata stored for dependent modules."""

    name: str
    revision: t.Optional[str]
    schema: t.Optional[str]


@dataclass
class DependencyMetadata(t.TypedDict):
    """Metadata stored for dependent modules."""

    name: str
    revision: t.Optional[str]
    schema: t.Optional[str]


NameRevisionModuleTable = dict[str, dict[str, ModuleMetadata]]


class ModulesComplicatedAlgorithms:
    def __init__(
        self,
        log_directory: str,
        yangcatalog_api_prefix: str,
        credentials: list[str],
        save_file_dir: str,
        direc: str,
        all_modules: t.Optional[dict],
        yang_models_dir: str,
        temp_dir: str,
        json_ytree: str,
    ):
        """
        Arguments:
            :param log_directory            (str) Directory where logs will be stored.
            :param yangcatalog_api_prefix   (str) URL of yangcatalog's api.
            :param credentials              (list[str]) Credentials of a registered yangcatalog user.
            :param save_file_dir            (str) Directory where all yang models are collected.
            :param direc                    (str) Directory where to loook for a prepare.json file.
            :param all_modules              (Optional[dict]) The module subtree of yangcatalog.
            :param yang_models_dir          (str) Directory to be added to pyangs parsing context.
            :param temp_dir                 (str) Yangcatalog's temp directory.
            :param json_ytree               (str) Directory where json ytrees are stored.
        """
        global LOGGER
        LOGGER = log.get_logger('modulesComplicatedAlgorithms', f'{log_directory}/parseAndPopulate.log')
        if all_modules is None:
            with open(f'{direc}/prepare.json', 'r') as f:
                all_modules = json.load(f)
        self._yangcatalog_api_prefix = yangcatalog_api_prefix
        self._all_modules: list[ModuleMetadata] = all_modules.get('module', [])  # pyright: ignore
        self.new_modules: NameRevisionModuleTable = defaultdict(dict)
        self._credentials = credentials
        self._save_file_dir = save_file_dir
        self._yang_models = yang_models_dir
        self.temp_dir = temp_dir
        self.json_ytree = json_ytree
        self._trees: dict[str, dict[str, str]] = defaultdict(dict)
        self._unavailable_modules = []

        LOGGER.info('Fetching all existing modules.')
        existing_modules = fetch_modules(LOGGER)

        self._existing_modules: NameRevisionModuleTable = defaultdict(dict)
        self._latest_revisions = {}
        for module in existing_modules:
            # Store latest revision of each module - used in resolving tree-type
            latest_revision = self._latest_revisions.get(module['name'])
            if latest_revision is None:
                self._latest_revisions[module['name']] = module['revision']
            else:
                self._latest_revisions[module['name']] = max(module['revision'], latest_revision)

            self._existing_modules[module['name']][module['revision']] = module

    def parse_non_requests(self):
        LOGGER.info('parsing tree types')
        self.resolve_tree_type(self._all_modules)

    def parse_requests(self):
        LOGGER.info('parsing semantic version')
        self.parse_semver()
        LOGGER.info('parsing dependents')
        self.parse_dependents()

    def populate(self):
        new_modules = [revision for name in self.new_modules.values() for revision in name.values()]
        LOGGER.info(f'populate with module complicated data. amount of new data is {len(new_modules)}')
        confd_service = ConfdService()
        confd_service.patch_modules(new_modules)

        redis_connection = RedisConnection()
        redis_connection.populate_modules(new_modules)

        if len(new_modules) > 0:
            url = f'{self._yangcatalog_api_prefix}/load-cache'
            response = requests.post(url, None, auth=(self._credentials[0], self._credentials[1]))
            if response.status_code != 201:
                LOGGER.warning(
                    f'Could not send a load-cache request. Status code: '
                    f'{response.status_code} Message: {response.text}',
                )
            else:
                LOGGER.info(f'load-cache responded with status code {response.status_code}')

    def resolve_tree_type(self, all_modules: list[ModuleMetadata]):
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
                if (
                    '+--rw' in row
                    and row_number != 0
                    and row_number not in skip
                    and '[' not in row
                    and (len(row.replace('|', '').strip(' ').split(' ')) != 2 or '(' in row)
                ):
                    if '->' in row and 'config' in row.split('->')[1] and '+--rw config' not in rows[row_number - 1]:
                        row_number += 1
                        continue
                    if '+--rw config' not in rows[row_number - 1]:
                        if 'augment' in rows[row_number - 1]:
                            if not rows[row_number - 1].endswith(':config:'):
                                return False
                        else:
                            return False
                    length_before = {len(row.split('+--')[0])}
                    skip = []
                    for x in range(row_number, len(rows)):
                        if 'x--' in rows[x] or 'o--' in rows[x]:
                            continue
                        if len(rows[x].split('+--')[0]) not in length_before:
                            if (
                                (len(rows[x].replace('|', '').strip(' ').split(' ')) != 2 and '[' not in rows[x])
                                or '+--:' in rows[x]
                                or '(' in rows[x]
                            ):
                                length_before.add(len(rows[x].split('+--')[0]))
                            else:
                                break
                        if '+--ro' in rows[x]:
                            return False
                        duplicate = rows[x].replace('+--rw', '+--ro').split('+--')[1]
                        if duplicate.replace(' ', '') not in output.replace(' ', ''):
                            return False
                        skip.append(x)
                if (
                    '+--ro' in row
                    and row_number != 0
                    and row_number not in skip
                    and '[' not in row
                    and (len(row.replace('|', '').strip(' ').split(' ')) != 2 or '(' in row)
                ):
                    if '->' in row and 'state' in row.split('->')[1] and '+--ro state' not in rows[row_number - 1]:
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
                if '+--rw config' == row.replace('|', '').strip(' ') or '+--ro state' == row.replace('|', '').strip(
                    ' ',
                ):
                    return False
                if len(row.split('+--')[0]) == 4:
                    if '-state' in row and '+--ro' in row:
                        return False
                if 'augment' in row and len(row.split('augment')[0]) == 2:
                    part = row.strip(' ').split('/')[1]
                    if '-state' in part:
                        next_obsolete_or_deprecated = True
                    part = row.strip(' ').split('/')[-1]
                    if ':state:' in part or '/state:' in part or ':config:' in part or '/config:' in part:
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
                coresponding_nmda_file = get_yang(name_of_module)
                if coresponding_nmda_file:
                    name = coresponding_nmda_file.split('/')[-1].split('.')[0]
                    revision = name.split('@')[-1]
                    name = name.split('@')[0]
                    if f'{name}@{revision}' in self._trees:
                        stdout = self._trees[name][revision]
                        pyang_list_of_rows = stdout.split('\n')[2:]
                    else:
                        plugin.plugins = []
                        plugin.init([])

                        ctx = create_context(f'{os.path.abspath(self._yang_models)}:{self._save_file_dir}')

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
                            emit_tree(ctx, [a], f, ctx.opts.tree_depth, ctx.opts.tree_line_length, path)
                            stdout = f.getvalue()
                        except Exception:
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
                            leaf = rows[x].split('+--ro ')[1].split(' ')[0].split('?')[0]

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
                if '+--rw config' == row.replace('|', '').strip(' ') or '+--ro state' == row.replace('|', '').strip(
                    ' ',
                ):
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
                if (len(row.split('+--')[0]) == 4 and 'augment' not in rows[row_num - 1]) or len(
                    row.split('augment')[0],
                ) == 2:
                    if '-state' in row:
                        if 'augment' in row:
                            part = row.strip(' ').split('/')[1]
                            if '-state' not in part:
                                row_num += 1
                                continue
                        for x in range(row_num + 1, len(rows)):
                            if 'x--' in rows[x] or 'o--' in rows[x]:
                                continue
                            if (
                                rows[x].strip(' ') == ''
                                or (len(rows[x].split('+--')[0]) == 4 and 'augment' not in rows[row_num - 1])
                                or len(row.split('augment')[0]) == 2
                            ):
                                break
                            if '+--rw' in rows[x]:
                                failed = True
                                break
                row_num += 1
            if failed:
                return False
            else:
                return True

        for x, module in enumerate(all_modules, start=1):
            name = module['name']
            revision = module['revision']
            name_revision = f'{name}@{revision}'
            self._path = f'{self._save_file_dir}/{name_revision}.yang'
            is_latest_revision = self.check_if_latest_revision(module)
            LOGGER.info(f'Searching tree-type for {name_revision}. {x} out of {len(all_modules)}')
            if revision in self._trees[name]:
                stdout = self._trees[name][revision]
            else:
                plugin.plugins = []
                plugin.init([])
                ctx = create_context(f'{os.path.abspath(self._yang_models)}:{self._save_file_dir}')
                ctx.opts.lint_namespace_prefixes = []
                ctx.opts.lint_modulename_prefixes = []
                for p in plugin.plugins:
                    p.setup_ctx(ctx)
                with open(self._path, 'r', errors='ignore') as f:
                    a = ctx.add_module(self._path, f.read())
                if a is None:
                    LOGGER.debug(
                        f'Could not use pyang to generate tree because of errors on module {self._path}',
                    )
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
                    emit_tree(ctx, [a], f, ctx.opts.tree_depth, ctx.opts.tree_line_length, path)
                    stdout = f.getvalue()
                    self._trees[name][revision] = stdout
                except Exception:
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
                    LOGGER.debug(f'Module {self._path} is a submodule')
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
            LOGGER.debug(f'tree type for module {module["name"]} is {module["tree-type"]}')
            if (
                revision not in self._existing_modules[name]
                or self._existing_modules[name][revision].get('tree-type') != module['tree-type']
            ):
                LOGGER.info(
                    f'tree-type {self._existing_modules[name].get(revision, {}).get("tree-type")} vs '
                    f'{module["tree-type"]} for module {module["name"]}@{module["revision"]}',
                )
                if revision not in self.new_modules[name]:
                    self.new_modules[name][revision] = module
                else:
                    self.new_modules[name][revision]['tree-type'] = module['tree-type']

    def parse_semver(self):
        def increment_semver(old: str, significance: int) -> str:
            """Increment a semver string at the specified position."""
            versions = old.split('.')
            versions = list(map(int, versions))
            versions[significance] += 1
            versions[significance + 1 :] = [0] * len(versions[significance + 1 :])
            return '{}.{}.{}'.format(*versions)

        def update_semver(old_semver_data: ModuleSemverMetadata, new_module: ModuleMetadata, significance: int):
            """Increment a module's semver at the specified position."""
            upgraded_version = increment_semver(old_semver_data.semver, significance)
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
            else:
                assert False

        def get_trees(new: ModuleSemverMetadata, old: ModuleSemverMetadata) -> t.Optional[t.Tuple[str, str]]:
            new_name_revision = f'{new.name}@{new.revision}'
            old_name_revision = f'{old.name}@{old.revision}'
            new_schema = f'{self._save_file_dir}/{new_name_revision}.yang'
            old_schema = f'{self._save_file_dir}/{old_name_revision}.yang'
            new_tree_path = f'{self.json_ytree}/{new_name_revision}.json'
            old_tree_path = f'{self.json_ytree}/{old_name_revision}.json'

            ctx, new_schema_ctx = context_check_update_from(
                old_schema,
                new_schema,
                self._yang_models,
                self._save_file_dir,
            )
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
                    except Exception:
                        new_yang_tree = ''
                    try:
                        f = io.StringIO()
                        emit_json_tree([old_schema_ctx], f, ctx)
                        old_yang_tree = f.getvalue()
                        with open(old_tree_path, 'w') as f:
                            f.write(old_yang_tree)
                    except Exception:
                        old_yang_tree = '2'
                return (new_yang_tree, old_yang_tree)
            else:
                raise Exception

        def add_to_new_modules(new_module: ModuleMetadata):
            name = new_module['name']
            revision = new_module['revision']
            if (
                revision not in self._existing_modules[name]
                or self._existing_modules[name][revision].get('derived-semantic-version')
                != new_module['derived-semantic-version']
            ):
                LOGGER.info(
                    f'semver {self._existing_modules[name].get(revision, {}).get("derived-semantic-version")} vs '
                    f'{new_module["derived-semantic-version"]} for module {name}@{revision}',
                )
                if revision not in self.new_modules[name]:
                    self.new_modules[name][revision] = new_module
                else:
                    self.new_modules[name][revision]['derived-semantic-version'] = new_module[
                        'derived-semantic-version'
                    ]

        for z, new_module in enumerate(self._all_modules, start=1):
            name = new_module['name']
            new_revision = new_module['revision']
            name_revision = f'{name}@{new_revision}'
            all_module_revisions = {}
            # Get all other available revisions of the module
            for m in self._existing_modules[new_module['name']].values():
                if m['revision'] != new_module['revision']:
                    all_module_revisions[m['revision']] = deepcopy(m)

            LOGGER.info(f'Searching semver for {name_revision}. {z} out of {len(self._all_modules)}')
            if len(all_module_revisions) == 0:
                # If there is no other revision for this module
                new_module['derived-semantic-version'] = '1.0.0'
                add_to_new_modules(new_module)
            else:
                # If there is at least one revision for this module
                new_date = revision_to_date(new_module['revision'])
                semver_data = [
                    ModuleSemverMetadata(
                        name=name,
                        revision=new_revision,
                        organization=new_module['organization'],
                        compilation=new_module.get('compilation-status', 'PENDING'),
                        schema=new_module.get('schema'),
                        semver='',
                        date=new_date,
                    ),
                ]

                # Loop through all other available revisions of the module
                try:
                    for module in all_module_revisions.values():
                        try:
                            semver_data.append(
                                ModuleSemverMetadata(
                                    name=name,
                                    revision=module['revision'],
                                    organization=module['organization'],
                                    compilation=module.get('compilation-status', 'PENDING'),
                                    schema=module.get('schema'),
                                    semver=module.get('derived-semantic-version', ''),
                                    date=revision_to_date(module['revision']),
                                ),
                            )
                        except KeyError:
                            LOGGER.exception(
                                f'Existing module {name}@{module["revision"]} is missing a field',
                            )
                            raise
                except KeyError:
                    continue
                missing_semver = not all(revision.semver for revision in semver_data)

                all_module_revisions[new_revision] = new_module
                semver_data = sorted(semver_data, key=lambda x: x.date)
                # if the revision we are adding is the latest one yet
                if not missing_semver and semver_data[-1].date == new_date:
                    new_module_semver_data = semver_data[-1]
                    newest_existing_module_semver_data = semver_data[-2]
                    if new_module_semver_data.compilation != 'passed':
                        versions = newest_existing_module_semver_data.semver.split('.')
                        major_ver = int(versions[0])
                        major_ver += 1
                        upgraded_version = f'{major_ver}.0.0'
                        new_module['derived-semantic-version'] = upgraded_version
                        add_to_new_modules(new_module)
                    else:
                        if newest_existing_module_semver_data.compilation != 'passed':
                            update_semver(newest_existing_module_semver_data, new_module, MAJOR)
                        else:
                            try:
                                trees = get_trees(new_module_semver_data, newest_existing_module_semver_data)
                                # if schemas do not exist, trees will be None
                                if not trees:
                                    continue
                                new_yang_tree, old_yang_tree = trees
                                if trees_match(new_yang_tree, old_yang_tree):
                                    # yang trees are the same - update only the patch version
                                    update_semver(newest_existing_module_semver_data, new_module, PATCH)
                                else:
                                    # yang trees have changed - update minor version
                                    update_semver(newest_existing_module_semver_data, new_module, MINOR)
                            except Exception:
                                # pyang found an error - update major version
                                update_semver(newest_existing_module_semver_data, new_module, MAJOR)
                # semvers for all revisions need to be recalculated
                else:
                    oldest_module_semver_data = semver_data[0]
                    name = oldest_module_semver_data.name
                    revision = oldest_module_semver_data.revision
                    oldest_module_semver_data.semver = '1.0.0'
                    response = all_module_revisions[revision]
                    response['derived-semantic-version'] = '1.0.0'
                    add_to_new_modules(response)

                    for prev_module_semver_data, curr_module_semver_data in zip(semver_data, semver_data[1:]):
                        revision = curr_module_semver_data.revision
                        module = all_module_revisions[revision]
                        if curr_module_semver_data.compilation != 'passed':
                            update_semver(prev_module_semver_data, module, 0)
                            curr_module_semver_data.semver = increment_semver(prev_module_semver_data.semver, 0)
                        else:
                            # If the previous revision has the compilation status 'passed'
                            if prev_module_semver_data.compilation != 'passed':
                                update_semver(prev_module_semver_data, module, 0)
                                curr_module_semver_data.semver = increment_semver(prev_module_semver_data.semver, 0)
                            else:
                                # Both actual and previous revisions have the compilation status 'passed'
                                try:
                                    trees = get_trees(curr_module_semver_data, prev_module_semver_data)
                                    # if schemas do not exist, trees will be None
                                    if not trees:
                                        continue
                                    new_yang_tree, old_yang_tree = trees
                                    if trees_match(new_yang_tree, old_yang_tree):
                                        # yang trees are the same - update only the patch version
                                        update_semver(prev_module_semver_data, module, 2)
                                        curr_module_semver_data.semver = increment_semver(
                                            prev_module_semver_data.semver,
                                            2,
                                        )
                                    else:
                                        # yang trees have changed - update minor version
                                        update_semver(prev_module_semver_data, module, 1)
                                        curr_module_semver_data.semver = increment_semver(
                                            prev_module_semver_data.semver,
                                            1,
                                        )
                                except Exception:
                                    # pyang found an error - update major version
                                    update_semver(prev_module_semver_data, module, 0)
                                    curr_module_semver_data.semver = increment_semver(prev_module_semver_data.semver, 0)

        if len(self._unavailable_modules) != 0:
            mf = message_factory.MessageFactory()
            mf.send_github_unavailable_schemas(self._unavailable_modules)

    def parse_dependents(self):
        """
        Add new modules as dependents to existing modules that depend on them.
        Add existing modules as dependants to new modules that depend on them.
        """

        def dependent_index(name: str, dependents: list) -> t.Optional[int]:
            for i, dependent in enumerate(dependents):
                if dependent['name'] == name:
                    return i
            return None

        def update_dependent(dependent: DependentMetadata, dependency: ModuleMetadata):
            """
            Check is the correct name and revision are already listed as a dependent to the dependency.
            If already present, return True. If a dependency with the same name, but different revision
            is listed, it is removed from the list of dependents.
            """
            existing_dependent_list: list[DependentMetadata] = dependency.get('dependents', [])
            index = dependent_index(dependent['name'], existing_dependent_list)
            if index is not None:
                if existing_revision := existing_dependent_list[index].get('revision'):
                    new_revision = dependent['revision']
                    assert new_revision, 'We created this and took the revision from the full ModuleMetadata.'
                    if revision_to_date(existing_revision) >= revision_to_date(new_revision):
                        return
                LOGGER.info(
                    f'Adding {dependent["name"]}@{dependent["revision"]} as dependent of '
                    f'{dependency["name"]}@{dependency["revision"]}',
                )
                existing_dependent_list.pop(index)
            dependency.setdefault('dependents', []).append(dependent)
            self.new_modules[dependency['name']][dependency['revision']] = dependency

        def add_dependents(dependents: list[ModuleMetadata], possible_dependencies: NameRevisionModuleTable):
            """
            Adds and updates modules in the dependents list as dependents to modules in the dependencies list.
            """
            for dependent_full in dependents:
                dependent_partial: DependentMetadata = {
                    'name': dependent_full['name'],
                    'revision': dependent_full['revision'],
                    'schema': dependent_full.get('schema'),
                }
                for dependency_partial in dependent_full.get('dependencies', []):
                    dependency_partial: DependencyMetadata
                    dependency_name = dependency_partial['name']
                    dependency_specified_revision = dependency_partial.get('revision')
                    if dependency_name not in possible_dependencies:
                        continue
                    dependencies_to_check = []
                    if dependency_specified_revision:
                        if dependency_specified_revision in possible_dependencies[dependency_name]:
                            dependencies_to_check = [
                                possible_dependencies[dependency_name][dependency_specified_revision],
                            ]
                    else:
                        # if no revision was specified for a dependency, the module should accept every revision
                        # therefore it should be listed as a dependent for every revision
                        dependencies_to_check = possible_dependencies[dependency_name].values()

                    for dependency_full in dependencies_to_check:
                        dependency_found_revision = dependency_full['revision']
                        # if this module has already been processed, the metadata could have been modified
                        # use up to date metadata if available
                        if dependency_found_revision in self.new_modules[dependency_name]:
                            dependency_full = self.new_modules[dependency_name][dependency_found_revision]
                        elif dependency_found_revision in self._existing_modules[dependency_name]:
                            dependency_full = deepcopy(
                                self._existing_modules[dependency_name][dependency_found_revision],
                            )

                        update_dependent(dependent_partial, dependency_full)

        new_modules = self._all_modules
        new_modules_dict: NameRevisionModuleTable = defaultdict(dict)
        for i in new_modules:
            new_modules_dict[i['name']][i['revision']] = deepcopy(i)
        both_dict = deepcopy(self._existing_modules)
        for name, revisions in new_modules_dict.items():
            both_dict[name].update(deepcopy(revisions))
        existing_modules = [revision for name in self._existing_modules.values() for revision in name.values()]
        LOGGER.info('Adding new modules as dependents')
        add_dependents(
            new_modules,
            both_dict,
        )  # New modules can be dependents both to existing modules, and other new modules
        LOGGER.info('Adding existing modules as dependents')
        add_dependents(
            existing_modules,
            new_modules_dict,
        )  # Existing modules have already been added as dependents to other existing modules

    def check_if_latest_revision(self, module: ModuleMetadata):
        """Check if the parsed module is the latest revision.

        Arguments:
            :param module   (ModuleMetadata) Metadata of the currently parsed module
        """
        return module.get('revision', '') >= self._latest_revisions.get(module['name'], '')
