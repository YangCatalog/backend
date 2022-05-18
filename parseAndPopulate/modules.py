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


__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import errno
import filecmp
import json
import os
import re
import shutil
import sys
import time
import typing as t
from datetime import datetime

import statistic.statistics as stats
from git import InvalidGitRepositoryError
from utility import log, repoutil, yangParser
from utility.create_config import create_config
from utility.staticVariables import (IETF_RFC_MAP, MISSING_ELEMENT, NS_MAP,
                                     github_raw, github_url)
from utility.util import find_first_file

from parseAndPopulate.dir_paths import DirPaths
from parseAndPopulate.loadJsonFiles import LoadFiles


class Submodules:
    def __init__(self):
        self.name: t.Optional[str] = None
        self.revision: t.Optional[str] = None
        self.schema: t.Optional[str] = None


class Dependency:
    def __init__(self):
        self.name: t.Optional[str] = None
        self.revision: t.Optional[str] = None
        self.schema: t.Optional[str] = None


class Implementation:
    def __init__(self):
        self.vendor: t.Optional[str] = None
        self.platform: t.Optional[str] = None
        self.software_version: t.Optional[str] = None
        self.software_flavor: t.Optional[str] = None
        self.os_version: t.Optional[str] = None
        self.feature_set: t.Optional[str] = None
        self.os_type: t.Optional[str] = None
        self.feature = []
        self.deviations = []
        self.conformance_type: t.Optional[str] = None
        self.capabilities = []
        self.netconf_versions = []

    class Deviation:
        def __init__(self):
            self.name: t.Optional[str] = None
            self.revision: t.Optional[str] = None
            self.schema: t.Optional[str] = None


class Module:
    """This is a class of a single module to parse all the basic metadata we can get out of it."""

    # NOTE: Maybe we should consider passing all or some of the arguments togeather in some sort of structure,
    #      as passing this many arguments is ugly and error prone.
    def __init__(self, name: str, path: str, jsons: LoadFiles, dir_paths: DirPaths, git_commit_hash: str,
                 yang_modules: dict, schema_base: str, aditional_info: t.Optional[t.Dict[str, str]],
                 submodule_name: t.Optional[str]):
        """
        Initialize and parse everything out of a module.
        Arguments:
            :param name:            (str) name of the module (not parsed out of the module)
            :param path:            (str) path to yang file being parsed
            :param jsons:           (obj) LoadFiles class containing all the json
                                    and html files with parsed results
            :param dir_paths:       (dict) paths to various needed directories according to configuration
            :param git_commit_hash: (str) name of the git commit hash where we can find the module
            :param yang_modules:    (dict) yang modules we've already parsed
            :param schema_base:     (str) url to a raw module on github up to and not including the
                                    path of the file in the repo
            :param aditional_info:  (dict) some aditional information about module given from client
            :param submodule_name:  (str) name of the git submodule the yang module belongs to
        """
        global LOGGER
        LOGGER = log.get_logger('modules', '{}/parseAndPopulate.log'.format(dir_paths['log']))
        config = create_config()
        self._web_uri = config.get('Web-Section', 'my-uri', fallback='https://yangcatalog.org')
        self.html_result_dir = dir_paths['result']
        self._jsons = jsons
        self._path = path
        self.yang_models = dir_paths['yang_models']

        self._parsed_yang = yangParser.parse(self._path)
        self.implementations: t.List[Implementation] = []
        self._parse_all(name, git_commit_hash, yang_modules, schema_base, dir_paths['save'], aditional_info, submodule_name)
        del self._jsons

    def _parse_all(self, name: str, git_commit_hash: str, yang_modules: dict, schema_base: str,
                   save_file_dir: str, aditional_info: t.Optional[t.Dict[str, str]] = None, submodule_name: t.Optional[str] = None):
        if aditional_info:
            author_email = aditional_info.get('author-email')
            maturity_level = aditional_info.get('maturity-level')
            reference = aditional_info.get('reference')
            document_name = aditional_info.get('document-name')
            generated_from = aditional_info.get('generated-from')
            organization = (aditional_info.get('organization') or MISSING_ELEMENT).lower()
            module_classification = aditional_info.get('module-classification')
        else:
            author_email = None
            reference = None
            maturity_level = None
            generated_from = None
            organization = None
            module_classification = None
            document_name = None
        self.name: str = self._parsed_yang.arg or name
        self.revision = self._resolve_revision()
        self.module_type = self._resolve_module_type()
        self.belongs_to = self._resolve_belongs_to(self.module_type)
        self.namespace = self._resolve_namespace()
        self.organization = organization or self._resolve_organization(self.namespace)
        key = '{}@{}/{}'.format(self.name, self.revision, self.organization)
        if key in yang_modules:
            return
        self.schema = self._resolve_schema(schema_base, git_commit_hash, submodule_name)
        self.dependencies: t.List[Dependency] = []
        self.submodule: t.List[Submodules] = []
        self._resolve_submodule(self.dependencies, self.submodule)
        self.json_submodules = json.dumps([{'name': self.submodule[x].name,
                                            'schema': self.submodule[x].schema,
                                            'revision': self.submodule[x].revision
                                            } for x in range(0, len(self.submodule))])
        self.imports = self._resolve_imports(self.dependencies, git_commit_hash)
        self._save_file(save_file_dir)
        self.generated_from = generated_from or self._resolve_generated_from()
        self.compilation_status, self.compilation_result = \
            self._resolve_compilation_status_and_result(self.generated_from)
        self.yang_version = self._resolve_yang_version()
        self.prefix = self._resolve_prefix()
        self.contact = self._resolve_contact()
        self.description = self._resolve_description()
        if document_name is None and reference is None:
            self.document_name, self.reference = self._parse_document_reference()
        else:
            self.document_name = document_name
            self.reference = reference
        self.tree = self._resolve_tree(self.module_type)
        self.module_classification = module_classification or 'unknown'
        self.ietf_wg = self._resolve_working_group()
        self.author_email = author_email or self._resolve_author_email()
        self.maturity_level = maturity_level or self._resolve_maturity_level()
        self.semver = self._resolve_semver()

    def _resolve_tree(self, module_type: t.Optional[str]):
        if module_type == 'module':
            return 'services/tree/{}@{}.yang'.format(self.name, self.revision)
        else:
            return None

    def _save_file(self, save_file_dir):
        file_with_path = '{}/{}@{}.yang'.format(save_file_dir, self.name, self.revision)
        try:
            same = filecmp.cmp(self._path, file_with_path)
            if not same:
                shutil.copy(self._path, file_with_path)
        except FileNotFoundError:
            shutil.copy(self._path, file_with_path)

    def _resolve_semver(self):
        semver = None
        yang_file = open(self._path, encoding='utf-8')
        for line in yang_file:
            if re.search('oc-ext:openconfig-version .*;', line):
                semver = re.findall('[0-9]+.[0-9]+.[0-9]+', line).pop()
        yang_file.close()
        return semver

    def _resolve_imports(self, dependencies: t.List[Dependency], git_commit_hash: str) -> list:
        LOGGER.debug('Resolving imports')
        imports = []
        try:
            imports = self._parsed_yang.search('import')

            for chunk in imports:
                dependency = Dependency()
                dependency.name = chunk.arg
                revisions = chunk.search('revision-date')
                if revisions:
                    dependency.revision = revisions[0].arg
                if dependency.revision:
                    yang_file = self._find_file(dependency.name, dependency.revision)
                else:
                    yang_file = self._find_file(dependency.name)
                if yang_file is None:
                    dependency.schema = None
                else:
                    try:
                        if os.path.dirname(yang_file) == os.path.dirname(self._path):
                            if self.schema:
                                dependency.schema = '/'.join((*self.schema.split('/')[0:-1], yang_file.split('/')[-1]))
                            else:
                                dependency.schema = None
                        else:
                            if '/yangmodels/yang/' in yang_file:
                                suffix = os.path.abspath(yang_file).split('/yangmodels/yang/')[1]
                                # First load/clone YangModels/yang repo
                                owner_name = 'YangModels'
                                repo_name = 'yang'
                                repo_url = os.path.join(github_url, owner_name, repo_name)
                                try:
                                    repo = repoutil.load(self.yang_models, repo_url)
                                except InvalidGitRepositoryError:
                                    repo = repoutil.RepoUtil(repo_url, clone_options={'local_dir': self.yang_models})
                                # Check if repository submodule
                                for submodule in repo.repo.submodules:
                                    if submodule.name in suffix:
                                        repo_url = submodule.url.lower()
                                        repo_dir = os.path.join(self.yang_models, submodule.name)
                                        repo = repoutil.load(repo_dir, repo_url)
                                        owner_name = repo.get_repo_owner()
                                        repo_name = repo.get_repo_dir().split('.git')[0]
                                        suffix = suffix.replace('{}/'.format(submodule.name), '')

                                branch = repo.get_commit_hash(suffix, 'main')

                                dependency.schema = os.path.join(github_raw, owner_name, repo_name, branch, suffix)
                            elif git_commit_hash in yang_file:
                                if self.schema:
                                    prefix = self.schema.split('/{}/'.format(git_commit_hash))[0]
                                    suffix = os.path.abspath(yang_file).split('/{}/'.format(git_commit_hash))[1]
                                    dependency.schema = '{}/master/{}'.format(prefix, suffix)
                                else:
                                    dependency.schema = None
                    except:
                        LOGGER.exception('Unable to resolve schema for {}@{}.yang'
                                         .format(dependency.name, dependency.revision))
                        dependency.schema = None
                        dependencies.append(dependency)
                dependencies.append(dependency)
        finally:
            return imports

    def _resolve_revision(self) -> str:
        LOGGER.debug('Resolving revision')
        try:
            revision = self._parsed_yang.search('revision')[0].arg
        except:
            revision = '1970-01-01'
        rev_parts = revision.split('-')
        try:
            revision = datetime(int(rev_parts[0]), int(rev_parts[1]), int(rev_parts[2])).date().isoformat()
        except ValueError:
            try:
                if int(rev_parts[2]) == 29 and int(rev_parts[1]) == 2:
                    revision = datetime(int(rev_parts[0]), int(rev_parts[1]), 28).date().isoformat()
            except ValueError:
                revision = '1970-01-01'
        return revision

    def _resolve_schema(self, schema_base: str, git_commit_hash: str, submodule_name: t.Optional[str]) -> t.Optional[str]:
        LOGGER.debug('Resolving schema')
        if self.organization == 'etsi':
            suffix = self._path.split('SOL006')[-1]
            return 'https://forge.etsi.org/rep/nfv/SOL006/raw/master/{}'.format(suffix)
        if not schema_base:
            return None

        schema_base = os.path.join(schema_base, git_commit_hash)
        if 'openconfig/public' in self._path:
            suffix = os.path.abspath(self._path).split('/openconfig/public/')[-1]
            return os.path.join(schema_base, suffix)
        if 'draftpulllocal' in self._path:
            suffix = os.path.abspath(self._path).split('draftpulllocal/')[-1]
            return os.path.join(schema_base, suffix)
        if 'yangmodels/yang' in self._path:
            suffix = os.path.abspath(self._path).split('/yangmodels/yang/')[-1]
        elif '/tmp/' in self._path:
            suffix = os.path.abspath(self._path).split('/tmp/')[1]
            suffix = '/'.join(suffix.split('/')[3:])  # remove directory_number/owner/repo prefix
        else:
            LOGGER.warning('Called by api, files should be copied in a subdirectory of tmp')
            return
        if submodule_name:
            suffix = suffix.replace('{}/'.format(submodule_name), '')
        return os.path.join(schema_base, suffix)

    def _resolve_maturity_level(self) -> t.Optional[str]:
        LOGGER.debug('Resolving maturity level')
        yang_name = '{}.yang'.format(self.name)
        yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
        try:
            maturity_level = self._jsons.status['IETFDraft'][yang_name][0].split(
                '</a>')[0].split('\">')[1].split('-')[1]
            if 'ietf' in maturity_level:
                return 'adopted'
            else:
                return 'initial'
        except KeyError:
            pass
        # try to find in draft with revision
        try:
            maturity_level = self._jsons.status['IETFDraft'][yang_name_rev][0].split(
                '</a>')[0].split('\">')[1].split('-')[1]
            if 'ietf' in maturity_level:
                return 'adopted'
            else:
                return 'initial'
        except KeyError:
            pass
        # try to find in rfc with revision
        if self._jsons.status['IETFYANGRFC'].get(yang_name_rev) is not None:
            return 'ratified'
        # try to find in rfc without revision
        if self._jsons.status['IETFYANGRFC'].get(yang_name) is not None:
            return 'ratified'
        return None

    def _resolve_author_email(self) -> t.Optional[str]:
        LOGGER.debug('Resolving author email')
        yang_name = '{}.yang'.format(self.name)
        yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
        try:
            return self._jsons.status['IETFDraft'][yang_name][1].split('\">Email')[0].split('mailto:')[1]
        except KeyError:
            pass
        # try to find in draft with revision
        try:
            return self._jsons.status['IETFDraft'][yang_name_rev][1].split('\">Email')[0].split('mailto:')[1]
        except KeyError:
            pass
        # try to find in draft examples without revision
        try:
            return self._jsons.status['IETFDraftExample'][yang_name][1].split('\">Email')[0].split('mailto:')[1]
        except KeyError:
            pass
        # try to find in draft examples with revision
        try:
            return self._jsons.status['IETFDraftExample'][yang_name_rev][1].split(
                '\">Email')[0].split('mailto:')[1]
        except KeyError:
            pass
        return None

    def _resolve_working_group(self) -> t.Optional[str]:
        LOGGER.debug('Resolving working group')
        if self.organization == 'ietf':
            yang_name = '{}.yang'.format(self.name)
            yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
            try:
                return self._jsons.status['IETFDraft'][yang_name][0].split('</a>')[0].split('\">')[1].split('-')[2]
            except KeyError:
                pass
            # try to find in draft with revision
            try:
                return self._jsons.status['IETFDraft'][yang_name_rev][0].split('</a>')[0].split('\">')[1].split('-')[2]
            except KeyError:
                pass
            # try to find in ietf RFC map without revision
            try:
                return IETF_RFC_MAP[yang_name]
            except KeyError:
                pass
            # try to find in ietf RFC map with revision
            try:
                return IETF_RFC_MAP[yang_name_rev]
            except KeyError:
                pass
        return None

    def _resolve_submodule(self, dependencies: t.List[Dependency], submodule: t.List[Submodules]):
        LOGGER.debug('Resolving submodules')
        try:
            submodules = self._parsed_yang.search('include')
        except:
            return

        if len(submodules) == 0:
            return

        for chunk in submodules:
            dep = Dependency()
            sub = Submodules()
            sub.name = chunk.arg

            if len(chunk.search('revision-date')) > 0:
                sub.revision = chunk.search('revision-date')[0].arg

            if sub.revision:
                yang_file = self._find_file(sub.name, sub.revision)
                dep.revision = sub.revision
            else:
                yang_file = self._find_file(sub.name)
                if yang_file:
                    try:
                        sub.revision = \
                            yangParser.parse(os.path.abspath(yang_file)).search('revision')[0].arg
                    except:
                        sub.revision = '1970-01-01'
                else:
                    sub.revision = '1970-01-01'
            if yang_file is None:
                LOGGER.error('Module can not be found')
                continue
            if self.schema:
                sub_schema = '/'.join((*self.schema.split('/')[0:-1], yang_file.split('/')[-1]))
            else:
                sub_schema = None
            if yang_file:
                sub.schema = sub_schema
            dep.name = sub.name
            dep.schema = sub.schema
            dependencies.append(dep)
            submodule.append(sub)

    def _resolve_yang_version(self) -> str:
        LOGGER.debug('Resolving yang version')
        try:
            yang_version = self._parsed_yang.search('yang-version')[0].arg
        except:
            yang_version = '1.0'
        if yang_version == '1':
            yang_version = '1.0'
        return yang_version

    def _resolve_generated_from(self) -> str:
        LOGGER.debug('Resolving generated from')
        if self.namespace and ':smi' in self.namespace:
            return 'mib'
        elif 'cisco' in self.name.lower():
            return 'native'
        else:
            return 'not-applicable'

    def _resolve_compilation_status_and_result(self, generated_from: str) -> t.Tuple[str, str]:
        LOGGER.debug('Resolving compiation status and result')
        if self._jsons.mangled_name is None:
            return 'unknown', ''
        status, ths = self._parse_status()
        if status not in ['passed', 'passed-with-warnings', 'failed', 'pending', 'unknown']:
            status = 'unknown'
        if status != 'passed':
            compilation_result = self._parse_result()
            if (self.organization == 'cisco'
                and compilation_result
                and compilation_result['pyang'] == ''
                and compilation_result['yanglint'] == ''
                and compilation_result['confdrc'] == ''
                and compilation_result['yumadump'] == ''
                and (generated_from == 'native'
                     or generated_from == 'mib')):
                status = 'passed'
        else:
            compilation_result = {'pyang': '', 'pyang_lint': '',
                                  'confdrc': '', 'yumadump': '',
                                  'yanglint': ''}
        result_url = self._create_compilation_result_file(compilation_result, status, ths)
        if status == 'unknown':
            result_url = ''
        return status, result_url

    def _create_compilation_result_file(self, compilation_result: t.Dict[str, str], status, ths):
        LOGGER.debug('Resolving compilation status')
        if status in ['unknown', 'pending']:
            return ''
        compilation_result['name'] = self.name
        compilation_result['revision'] = self.revision
        compilation_result['generated'] = time.strftime('%d/%m/%Y')
        context = {'result': compilation_result,
                   'ths': ths}
        template = os.path.join(os.environ['BACKEND'], 'parseAndPopulate/template/compilationStatusTemplate.html')
        rendered_html = stats.render(template, context)
        file_url = '{}@{}_{}.html'.format(self.name, self.revision, self.organization)

        # Don t override status if it was already written once
        file_path = '{}/{}'.format(self.html_result_dir, file_url)
        if os.path.exists(file_path):
            if status not in ['unknown', 'pending']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_output = f.read()
                if existing_output != rendered_html:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(rendered_html)
                    os.chmod(file_path, 0o664)
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(rendered_html)
            os.chmod(file_path, 0o664)

        return '{}/results/{}'.format(self._web_uri, file_url)

    def _resolve_contact(self) -> t.Optional[str]:
        LOGGER.debug('Resolving contact')
        try:
            return self._parsed_yang.search('contact')[0].arg
        except:
            return None

    def _resolve_description(self):
        LOGGER.debug('Resolving description')
        try:
            return self._parsed_yang.search('description')[0].arg
        except:
            return None

    def _resolve_namespace(self) -> t.Optional[str]:
        LOGGER.debug('Resolving namespace')
        return self._resolve_submodule_case('namespace')

    def _resolve_belongs_to(self, module_type: t.Optional[str]) -> t.Optional[str]:
        LOGGER.debug('Resolving belongs to')
        if module_type == 'submodule':
            try:
                return self._parsed_yang.search('belongs-to')[0].arg
            except:
                return None
        return None

    def _resolve_module_type(self) -> t.Optional[str]:
        LOGGER.debug('Resolving module type')
        try:
            with open(self._path, 'r', encoding='utf-8') as file_input:
                all_lines = file_input.readlines()
        except:
            LOGGER.critical(
                'Could not open a file {}. Maybe a path is set incorrectly'.format(self._path))
            sys.exit(10)
        commented_out = False
        for each_line in all_lines:
            module_position = each_line.find('module')
            submodule_position = each_line.find('submodule')
            cpos = each_line.find('//')
            if commented_out:
                mcpos = each_line.find('*/')
            else:
                mcpos = each_line.find('/*')
            if mcpos != -1 and cpos > mcpos:
                if commented_out:
                    commented_out = False
                else:
                    commented_out = True
            if submodule_position >= 0 and (
                    submodule_position < cpos or cpos == -1) and not commented_out:
                LOGGER.debug(
                    'Module {} is of type submodule'.format(self._path))
                return 'submodule'
            if module_position >= 0 and (
                    module_position < cpos or cpos == -1) and not commented_out:
                LOGGER.debug('Module {} is of type module'.format(self._path))
                return 'module'
        LOGGER.error('Module {} has wrong format'.format(self._path))
        return None

    def _resolve_organization(self, namespace: t.Optional[str]) -> str:
        LOGGER.debug('Resolving organization')
        try:
            temp_organization = self._parsed_yang.search('organization')[0].arg.lower()
            if 'cisco' in temp_organization or 'CISCO' in temp_organization:
                return 'cisco'
            elif 'ietf' in temp_organization or 'IETF' in temp_organization:
                return 'ietf'
        except:
            pass
        if namespace:
            for ns, org in NS_MAP:
                if ns in namespace:
                    return org
            if 'cisco' in namespace or 'CISCO' in namespace:
                return 'cisco'
            elif 'ietf' in namespace or 'IETF' in namespace:
                return 'ietf'
            elif 'urn:' in namespace:
                return namespace.split('urn:')[1].split(':')[0]
        return 'independent'

    def _resolve_prefix(self) -> t.Optional[str]:
        LOGGER.debug('Resolving prefix')
        return self._resolve_submodule_case('prefix')

    def _resolve_submodule_case(self, field: str) -> t.Optional[str]:
        if self.module_type == 'submodule':
            LOGGER.debug('Getting parent information because file {} is a submodule'.format(self._path))
            if self.belongs_to:
                yang_file = self._find_file(self.belongs_to)
            else:
                return None
            if yang_file is None:
                return None
            try:
                parsed_parent_yang = yangParser.parse(os.path.abspath(yang_file))
                return parsed_parent_yang.search(field)[0].arg
            except IndexError:
                if field == 'prefix':
                    return None
                return MISSING_ELEMENT
        else:
            try:
                return self._parsed_yang.search(field)[0].arg
            except IndexError:
                if field == 'prefix':
                    return None
                return MISSING_ELEMENT

    def _parse_status(self) -> t.Tuple[str, t.List[str]]:
        LOGGER.debug('Parsing status of module {}'.format(self._path))
        status = 'unknown'
        ths = []
        for w_rev in [True, False]:
            status, ths = self._get_module_status(w_rev)
            if status != 'unknown':
                break
        return status, ths

    def _get_module_status(self, with_revision) -> t.Tuple[str, t.List[str]]:
        index = 0
        if self._jsons.mangled_name == 'IETFYANGRFC':
            return 'unknown', []
        if self._jsons.mangled_name == 'IETFDraft':
            index = 3
        if with_revision:
            yang_file = '{}@{}.yang'.format(self.name, self.revision)
        else:
            yang_file = '{}.yang'.format(self.name)
        try:
            status = self._jsons.status[self._jsons.mangled_name][yang_file][index]
            if status == 'PASSED WITH WARNINGS':
                status = 'passed-with-warnings'
            status = status.lower()
            ths = self._jsons.headers[self._jsons.mangled_name]
            assert status != ''
            return status, ths
        except:
            pass
        ths = self._jsons.headers[self._jsons.mangled_name]
        return 'unknown', ths

    def _parse_result(self) -> t.Dict[str, str]:
        LOGGER.debug('Parsing compilation status of module {}'.format(self._path))
        res = {}
        with_revision = [True, False]
        for w_rev in with_revision:
            res = self._parse_res(w_rev)
            if res:
                break
        return {'pyang': '', 'pyang_lint': '', 'confdrc': '', 'yumadump': '', 'yanglint': ''}

    def _parse_res(self, with_revision: bool) -> t.Dict[str, str]:
        index = 0
        result = {}
        if self._jsons.mangled_name == 'IETFDraft':
            index = 3
        elif self._jsons.mangled_name == 'IETFYANGRFC':
            return {}
        if with_revision:
            # try to find with revision
            yang_file = '{}@{}.yang'.format(self.name, self.revision)
        else:
            # try to find without revision
            yang_file = '{}.yang'.format(self.name)
        try:
            result['pyang_lint'] = self._jsons.status[self._jsons.mangled_name][yang_file][1 + index]
            result['pyang'] = self._jsons.status[self._jsons.mangled_name][yang_file][2 + index]
            result['confdrc'] = self._jsons.status[self._jsons.mangled_name][yang_file][3 + index]
            result['yumadump'] = self._jsons.status[self._jsons.mangled_name][yang_file][4 + index]
            result['yanglint'] = self._jsons.status[self._jsons.mangled_name][yang_file][5 + index]
            return result
        except:
            pass
        return {}

    def _parse_document_reference(self):
        LOGGER.debug('Parsing document reference of module {}'.format(self._path))
        # try to find in draft without revision
        yang_name = '{}.yang'.format(self.name)
        yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
        try:
            doc_name = self._jsons.status['IETFDraft'][yang_name][0].split(
                '</a>')[0].split('\">')[1]
            doc_source = self._jsons.status['IETFDraft'][yang_name][0].split(
                'a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
        # try to find in draft with revision
        try:
            doc_name = self._jsons.status['IETFDraft'][yang_name_rev][
                0].split('</a>')[0].split('\">')[1]
            doc_source = self._jsons.status['IETFDraft'][yang_name_rev][
                0].split('a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
        # try to find in rfc with revision
        try:
            doc_name = self._jsons.status['IETFYANGRFC'][
                yang_name_rev].split('</a>')[0].split('\">')[1]
            doc_source = self._jsons.status['IETFYANGRFC'][
                yang_name_rev].split('a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
        # try to find in rfc without revision
        try:
            doc_name = self._jsons.status['IETFYANGRFC'][yang_name].split('</a>')[
                0].split('\">')[1]
            doc_source = self._jsons.status['IETFYANGRFC'][yang_name].split(
                'a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
        return [None, None]

    def _find_file(self, name: str, revision: str = '*') -> t.Optional[str]:
        pattern = '{}.yang'.format(name)
        pattern_with_revision = '{}@{}.yang'.format(name, revision)
        yang_file = find_first_file(os.path.dirname(self._path), pattern, pattern_with_revision, self.yang_models)
        return yang_file


class SdoModule(Module):

    def __init__(self, name: str, path: str, jsons: LoadFiles, dir_paths: DirPaths, git_commit_hash: str,
                 yang_modules: dict, schema_base: str, aditional_info: t.Optional[t.Dict[str, str]] = None,
                 submodule_name: t.Optional[str] = None):
        super().__init__(name, os.path.abspath(path), jsons, dir_paths, git_commit_hash, yang_modules, schema_base,
                         aditional_info, submodule_name)


class VendorModule(Module):
    """A module with additional vendor information."""

    def __init__(self, name: str, path: str, jsons: LoadFiles, dir_paths: DirPaths, git_commit_hash: str,
                 yang_modules: dict, schema_base: str, aditional_info: t.Optional[t.Dict[str, str]] = None,
                 submodule_name: t.Optional[str] = None, data: t.Optional[t.Union[str, dict]] = None):
        real_path = path
        # these are required for self._find_file() to work
        self.yang_models = dir_paths['yang_models']
        self._path = path
        self.features = []
        self.deviations = []
        if isinstance(data, str):  # string from a capabilities file
            self.features = self._resolve_deviations_and_features('features=', data)
            deviation_names = self._resolve_deviations_and_features('deviations=', data)
            for name in deviation_names:
                deviation = {'name': name}
                yang_file = self._find_file(name)
                if yang_file is None:
                    deviation['revision'] = '1970-01-01'
                else:
                    try:
                        deviation['revision'] = yangParser.parse(os.path.abspath(yang_file)) \
                            .search('revision')[0].arg
                    except:
                        deviation['revision'] = '1970-01-01'
                self.deviations.append(deviation)

            self.revision = '*'
            if 'revision' in data:
                revision_and_more = data.split('revision=')[1]
                revision = revision_and_more.split('&')[0]
                self.revision = revision

            real_path = self._find_file(data.split('&')[0], self.revision)
        elif isinstance(data, dict):  # dict parsed out from a ietf-yang-library file
            self.deviations = data['deviations']
            self.features = data['features']
            self.revision = data['revision']
            real_path = self._find_file(data['name'], self.revision)
        if not real_path:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)
        super().__init__(name, os.path.abspath(real_path), jsons, dir_paths, git_commit_hash, yang_modules, schema_base,
                         aditional_info, submodule_name)

    def _resolve_deviations_and_features(self, search_for: str, data: str) -> t.List[str]:
        ret = []
        if search_for in data:
            devs_or_features = data.split(search_for)[1]
            devs_or_features = devs_or_features.split('&')[0]
            ret = devs_or_features.split(',')
        return ret

    def add_vendor_information(self, platform_data: list, conformance_type: t.Optional[str],
                               capabilities: list, netconf_versions: list):
        """
        Add information from platform-metadata json files provided with Cisco modules.

        Arguments:
            :param platform_data:       (list) list of platform_data loaded from platform_metadata.json
            :param conformance_type:    (str) string representing conformance type of module
            :param capabilities:        (list) list of netconf capabilities loaded from platform_metadata.json
            :param netconf_versions:    (list) list of netconf versions loaded from platform-metadata.json
        """
        for data in platform_data:
            implementation = Implementation()
            implementation.vendor = data['vendor']
            implementation.platform = data['platform']
            implementation.software_version = data['software-version']
            implementation.software_flavor = data['software-flavor']
            implementation.os_version = data['os-version']
            implementation.feature_set = data['feature-set']
            implementation.os_type = data['os']
            implementation.feature = self.features
            implementation.capabilities = capabilities
            implementation.netconf_versions = netconf_versions

            for deviation in self.deviations:
                dev = implementation.Deviation()
                dev.name = deviation['name']
                dev.revision = deviation['revision']
                implementation.deviations.append(dev)

            implementation.conformance_type = conformance_type
            self.implementations.append(implementation)
