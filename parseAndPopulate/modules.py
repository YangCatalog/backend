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
import json
import os
import re
import sys
import time
import typing as t
from datetime import datetime

from pyang.statements import Statement

import statistic.statistics as stats
from utility import log, repoutil, yangParser
from utility.create_config import create_config
from utility.staticVariables import (IETF_RFC_MAP, MISSING_ELEMENT, NS_MAP,
                                     github_raw, github_url)
from utility.util import find_first_file
from parseAndPopulate.loadJsonFiles import LoadFiles


class Module:
    """This is a class of a single module to parse all the basic metadata we can get out of it."""

    def __init__(self, path: str, jsons: LoadFiles, dir_paths: t.Dict[str, str]):
        """
        Preset Modules class to parse yang module and save data to it.
        :param path:            (str) path to yang file being parsed
        :param jsons:           (obj) LoadFiles class containing all the json
                                and html files with parsed results
        :param dir_paths        (dict) paths to various needed directories according to configuration
        """
        global LOGGER
        LOGGER = log.get_logger('modules', '{}/parseAndPopulate.log'.format(dir_paths['log']))
        config = create_config()
        self._web_uri = config.get('Web-Section', 'my-uri', fallback='https://yangcatalog.org')
        self.html_result_dir = dir_paths['result']
        self.jsons = jsons
        self.revision = '*'
        self._path = path
        self.features = []
        self.deviations = []
        self.yang_models = dir_paths['yang_models']

        self.name = None
        self.organization = None
        self.ietf_wg = None
        self.namespace = None
        self.schema = None
        self.generated_from = None
        self.maturity_level = None
        self.document_name = None
        self.author_email = None
        self.reference = None
        self.tree = None
        self.expired = None
        self.expiration_date = None
        self.module_classification = None
        self.compilation_status = None
        self.compilation_result = {}
        self.prefix = None
        self.yang_version = None
        self.description = None
        self.contact = None
        self.belongs_to = None
        self.submodule = []
        self.dependencies = []
        self.module_type = None
        self.tree_type = None
        self.semver = None
        self.derived_semver = None
        self.implementations: t.List[Module.Implementation] = []
        self.imports = []
        self.json_submodules = json.dumps([])
        self._parsed_yang: Statement

    def _resolve_deviations_and_features(self, search_for: str, data: str) -> t.List[str]:
        ret = []
        if search_for in data:
            devs_or_features = data.split(search_for)[1]
            devs_or_features = devs_or_features.split('&')[0]
            ret = devs_or_features.split(',')
        return ret

    def parse_all(self, name: str, git_commit_hash: str, yang_modules: dict, schema_base: str,
                  path_in_repo: str, save_file_dir: str, aditional_info: t.Optional[dict] = None):
        """
        Parse all data that we can from the module. Must only be called once.

        Arguments:
            :param name:            (str) name of the module (not parsed out of the module)
            :param git_commit_hash: (str) name of the git commit hash where we can find the module
            :param yang_modules:    (dict) yang modules we've already parsed
            :param schema_base:     (str) url to a raw module on github up to and not including the
                                    path of the file in the repo
            :param path_in_repo     (str) the rest of the url
            :param save_file_dir:   (str) directory, where all the modules are saved at
            :param aditional_info   (dict) some aditional information about module given from client
        """
        def get_json(js):
            if js:
                return js
            else:
                return 'missing element'

        if aditional_info:
            author_email = aditional_info.get('author-email')
            maturity_level = aditional_info.get('maturity-level')
            reference = aditional_info.get('reference')
            document_name = aditional_info.get('document-name')
            generated_from = aditional_info.get('generated-from')
            organization = get_json(aditional_info.get('organization'))
            module_classification = aditional_info.get('module-classification')
        else:
            author_email = None
            reference = None
            maturity_level = None
            generated_from = None
            organization = None
            module_classification = None
            document_name = None
        self._resolve_name(name)
        self._resolve_revision()
        self._resolve_module_type()
        self._resolve_belongs_to()
        self._resolve_namespace()
        self._resolve_organization(organization)
        self._resolve_schema(schema_base, git_commit_hash, path_in_repo)
        self._resolve_submodule()
        self._resolve_imports(git_commit_hash)
        key = '{}@{}/{}'.format(self.name, self.revision, self.organization)
        if key in yang_modules:
            return
        self._save_file(save_file_dir)
        self._resolve_generated_from(generated_from)
        self._resolve_compilation_status_and_result()
        self._resolve_yang_version()
        self._resolve_prefix()
        self._resolve_contact()
        self._resolve_description()
        self._resolve_document_name_and_reference(document_name, reference)
        self._resolve_tree()
        self._resolve_module_classification(module_classification)
        self._resolve_working_group()
        self._resolve_author_email(author_email)
        self._resolve_maturity_level(maturity_level)
        self._resolve_semver()
        del self.jsons

    def _resolve_tree(self):
        if self.module_type == 'module':
            self.tree = 'services/tree/{}@{}.yang'.format(self.name, self.revision)

    def _save_file(self, save_file_dir):
        file_with_path = '{}/{}@{}.yang'.format(save_file_dir, self.name, self.revision)
        if not os.path.exists(file_with_path):
            with open(self._path, 'r', encoding='utf-8') as f:
                with open(file_with_path, 'w', encoding='utf-8') as f2:
                    f2.write(f.read())

    def _resolve_semver(self):
        yang_file = open(self._path, encoding='utf-8')
        for line in yang_file:
            if re.search('oc-ext:openconfig-version .*;', line):
                self.semver = re.findall('[0-9]+.[0-9]+.[0-9]+', line).pop()
        yang_file.close()

    def _resolve_imports(self, git_commit_hash):
        LOGGER.debug('Resolving imports')
        try:
            self.imports = self._parsed_yang.search('import')
            if len(self.imports) == 0:
                return

            for chunk in self.imports:
                dependency = self.Dependency()
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
                            schema = '/'.join(self.schema.split('/')[0:-1])
                            schema += '/{}'.format(yang_file.split('/')[-1])

                            dependency.schema = schema
                        else:
                            if '/yangmodels/yang/' in yang_file:
                                suffix = os.path.abspath(yang_file).split('/yangmodels/yang/')[1]
                                # First load/clone YangModels/yang repo
                                owner_name = 'YangModels'
                                repo_name = 'yang'
                                repo_url = os.path.join(github_url, owner_name, repo_name)
                                repo = repoutil.load(self.yang_models, repo_url)
                                if repo is None:
                                    repo = repoutil.RepoUtil(repo_url)
                                    repo.clone()
                                # Check if repository submodule
                                assert repo.repo, 'Is loaded either from the yang_models dir or freshly cloned'
                                for submodule in repo.repo.submodules:
                                    if submodule.name in suffix:
                                        repo_url = submodule.url
                                        repo_dir = os.path.join(self.yang_models, submodule.name)
                                        repo = repoutil.load(repo_dir, repo_url)
                                        assert repo, 'Loaded from a known submodule'
                                        owner_name = repo.get_repo_owner()
                                        repo_name = repo.get_repo_dir().split('.git')[0]
                                        suffix = suffix.replace('{}/'.format(submodule.name), '')

                                branch = repo.get_commit_hash(suffix)
                                schema = os.path.join(github_raw, owner_name, repo_name, branch, suffix)

                                dependency.schema = schema
                            elif git_commit_hash in yang_file:
                                prefix = self.schema.split('/{}/'.format(git_commit_hash))[0]
                                suffix = os.path.abspath(yang_file).split('/{}/'.format(git_commit_hash))[1]
                                dependency.schema = '{}/master/{}'.format(prefix, suffix)
                    except:
                        LOGGER.exception('Unable to resolve schema for {}@{}.yang'
                            .format(dependency.name, dependency.revision))
                        dependency.schema = None
                        self.dependencies.append(dependency)
                self.dependencies.append(dependency)
        except:
            return

    def _resolve_name(self, name):
        LOGGER.debug('Resolving name')
        if self._parsed_yang.arg:
            self.name = self._parsed_yang.arg
        else:
            self.name = name

    def _resolve_revision(self):
        LOGGER.debug('Resolving revision')
        if self.revision == '*':
            try:
                self.revision = self._parsed_yang.search('revision')[0].arg
            except:
                self.revision = '1970-01-01'
            rev_parts = self.revision.split('-')
            try:
                self.revision = datetime(int(rev_parts[0]), int(rev_parts[1]), int(rev_parts[2])).date().isoformat()
            except ValueError:
                try:
                    if int(rev_parts[2]) == 29 and int(rev_parts[1]) == 2:
                        self.revision = datetime(int(rev_parts[0]), int(rev_parts[1]), 28).date().isoformat()
                except ValueError:
                    self.revision = '1970-01-01'

    def _resolve_schema(self, schema_base, git_commit_hash, path_in_repo):
        LOGGER.debug('Resolving schema')
        schema = os.path.join(schema_base, path_in_repo)
        if self.organization == 'etsi':
            suffix = self._path.split('SOL006')[-1]
            self.schema = 'https://forge.etsi.org/rep/nfv/SOL006/raw//master/{}'.format(suffix)
        elif schema:
            self.schema = schema
        else:
            self.schema = None

    def _resolve_module_classification(self, module_classification=None):
        LOGGER.debug('Resolving module classification')
        if module_classification:
            self.module_classification = module_classification
        else:
            self.module_classification = 'unknown'

    def _resolve_maturity_level(self, maturity_level=None):
        LOGGER.debug('Resolving maturity level')
        if maturity_level:
            self.maturity_level = maturity_level
        else:
            yang_name = '{}.yang'.format(self.name)
            yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
            try:
                maturity_level = self.jsons.status['IETFDraft'][yang_name][0].split(
                    '</a>')[0].split('\">')[1].split('-')[1]
                if 'ietf' in maturity_level:
                    self.maturity_level = 'adopted'
                    return
                else:
                    self.maturity_level = 'initial'
                    return
            except KeyError:
                pass
            # try to find in draft with revision
            try:
                maturity_level = self.jsons.status['IETFDraft'][yang_name_rev][0].split(
                    '</a>')[0].split('\">')[1].split('-')[1]
                if 'ietf' in maturity_level:
                    self.maturity_level = 'adopted'
                    return
                else:
                    self.maturity_level = 'initial'
                    return
            except KeyError:
                pass
            # try to find in rfc with revision
            if self.jsons.status['IETFYANGRFC'].get(yang_name_rev) is not None:
                self.maturity_level = 'ratified'
                return
            # try to find in rfc without revision
            if self.jsons.status['IETFYANGRFC'].get(yang_name) is not None:
                self.maturity_level = 'ratified'
                return
            self.maturity_level = None

    def _resolve_author_email(self, author_email=None):
        LOGGER.debug('Resolving author email')
        if author_email:
            self.author_email = author_email
        else:
            yang_name = '{}.yang'.format(self.name)
            yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
            try:
                self.author_email = self.jsons.status['IETFDraft'][yang_name][1].split(
                    '\">Email')[0].split('mailto:')[1]
                return
            except KeyError:
                pass
            # try to find in draft with revision
            try:
                self.author_email = self.jsons.status['IETFDraft'][yang_name_rev][1].split(
                    '\">Email')[0].split('mailto:')[1]
                return
            except KeyError:
                pass
            # try to find in draft examples without revision
            try:
                self.author_email = self.jsons.status['IETFDraftExample'][yang_name][
                    1].split('\">Email')[0].split('mailto:')[1]
                return
            except KeyError:
                pass
            # try to find in draft examples with revision
            try:
                self.author_email = self.jsons.status['IETFDraftExample'][yang_name_rev][1].split(
                    '\">Email')[0].split('mailto:')[1]
                return
            except KeyError:
                pass
            self.author_email = None

    def _resolve_working_group(self):
        LOGGER.debug('Resolving working group')
        if self.organization == 'ietf':
            yang_name = '{}.yang'.format(self.name)
            yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
            try:
                self.ietf_wg = self.jsons.status['IETFDraft'][yang_name][0].split(
                    '</a>')[0].split('\">')[1].split('-')[2]
                return
            except KeyError:
                pass
            # try to find in draft with revision
            try:
                self.ietf_wg = self.jsons.status['IETFDraft'][yang_name_rev][0] \
                    .split('</a>')[0].split('\">')[1].split('-')[2]
                return
            except KeyError:
                pass
            # try to find in ietf RFC map without revision
            try:
                self.ietf_wg = IETF_RFC_MAP[yang_name]
                return
            except KeyError:
                pass
            # try to find in ietf RFC map with revision
            try:
                self.ietf_wg = IETF_RFC_MAP[yang_name_rev]
                return
            except KeyError:
                pass
            self.ietf_wg = None

    def _resolve_document_name_and_reference(self, document_name=None, reference=None):
        LOGGER.debug('Resolving document name and reference')
        if document_name:
            self.document_name = document_name
        if reference:
            self.reference = reference

        if document_name is None and reference is None:
            self.document_name, self.reference = \
                self._parse_document_reference()

    def _resolve_submodule(self):
        LOGGER.debug('Resolving submodule')
        try:
            submodules = self._parsed_yang.search('include')
        except:
            return

        if len(submodules) == 0:
            return

        for chunk in submodules:
            dep = self.Dependency()
            sub = self.Submodules()
            sub.name = chunk.arg

            if len(chunk.search('revision-date')) > 0:
                sub.revision = chunk.search('revision-date')[0].arg

            if sub.revision:
                yang_file = self._find_file(sub.name, sub.revision)
                dep.revision = sub.revision
            else:
                yang_file = self._find_file(sub.name)
                try:
                    sub.revision = \
                        yangParser.parse(os.path.abspath(yang_file)).search('revision')[0].arg
                except:
                    sub.revision = '1970-01-01'
            if yang_file is None:
                LOGGER.error('Module can not be found')
                continue
            try:
                path = '/'.join(self.schema.split('/')[0:-1])
                path += '/{}'.format(yang_file.split('/')[-1])
            except:
                path = None
            if yang_file:
                sub.schema = path
            dep.name = sub.name
            dep.schema = sub.schema
            self.dependencies.append(dep)
            self.submodule.append(sub)
        self.json_submodules = json.dumps([{'name': self.submodule[x].name,
                                            'schema': self.submodule[x].schema,
                                            'revision': self.submodule[x].revision
                                            } for x in
                                           range(0, len(self.submodule))])

    def _resolve_yang_version(self):
        LOGGER.debug('Resolving yang version')
        try:
            self.yang_version = self._parsed_yang.search('yang-version')[0].arg
        except:
            self.yang_version = '1.0'
        if self.yang_version == '1':
            self.yang_version = '1.0'

    def _resolve_generated_from(self, generated_from: t.Optional[str] = None):
        LOGGER.debug('Resolving generated from')
        if generated_from:
            self.generated_from = generated_from
        else:
            if ':smi' in self.namespace:
                self.generated_from = 'mib'
            elif 'cisco' in self.name.lower():
                self.generated_from = 'native'
            else:
                self.generated_from = 'not-applicable'

    def _resolve_compilation_status_and_result(self):
        LOGGER.debug('Resolving compiation status and result')
        self.compilation_status = self._parse_status()
        if self.compilation_status['status'] not in ['passed', 'passed-with-warnings', 'failed', 'pending', 'unknown']:
            self.compilation_status['status'] = 'unknown'
        if self.compilation_status['status'] != 'passed':
            self.compilation_result = self._parse_result()
            if (self.organization == 'cisco'
                and self.compilation_result['pyang'] == ''
                and self.compilation_result['yanglint'] == ''
                and self.compilation_result['confdrc'] == ''
                and self.compilation_result['yumadump'] == ''
                and (self.generated_from == 'native'
                     or self.generated_from == 'mib')):
                self.compilation_status['status'] = 'passed'
        else:
            self.compilation_result = {'pyang': '', 'pyang_lint': '',
                                       'confdrc': '', 'yumadump': '',
                                       'yanglint': ''}
        self.compilation_result = self._create_compilation_result_file()
        if self.compilation_status['status'] == 'unknown':
            self.compilation_result = ''
        self.compilation_status = self.compilation_status['status']

    def _create_compilation_result_file(self):
        LOGGER.debug('Resolving compilation status')
        if self.compilation_status['status'] in ['unknown', 'pending']:
            return ''
        else:
            result = self.compilation_result
        result['name'] = self.name
        result['revision'] = self.revision
        result['generated'] = time.strftime('%d/%m/%Y')
        context = {'result': result,
                   'ths': self.compilation_status['ths']}
        template = os.path.dirname(os.path.realpath(__file__)) + '/template/compilationStatusTemplate.html'
        rendered_html = stats.render(template, context)
        file_url = '{}@{}_{}.html'.format(self.name, self.revision, self.organization)

        # Don t override status if it was already written once
        file_path = '{}/{}'.format(self.html_result_dir, file_url)
        if os.path.exists(file_path):
            if self.compilation_status['status'] not in ['unknown', 'pending']:
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

    def _resolve_contact(self):
        LOGGER.debug('Resolving contact')
        try:
            self.contact = self._parsed_yang.search('contact')[0].arg
        except:
            self.contact = None

    def _resolve_description(self):
        LOGGER.debug('Resolving description')
        try:
            self.description = self._parsed_yang.search('description')[0].arg
        except:
            self.description = None

    def _resolve_namespace(self):
        LOGGER.debug('Resolving namespace')
        self.namespace = self._resolve_submodule_case('namespace')

    def _resolve_belongs_to(self):
        LOGGER.debug('Resolving belongs to')
        if self.module_type == 'submodule':
            try:
                self.belongs_to = self._parsed_yang.search('belongs-to')[0].arg
            except:
                self.belongs_to = None

    def _resolve_module_type(self):
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
                self.module_type = 'submodule'
                return
            if module_position >= 0 and (
                    module_position < cpos or cpos == -1) and not commented_out:
                LOGGER.debug('Module {} is of type module'.format(self._path))
                self.module_type = 'module'
                return
        LOGGER.error('Module {} has wrong format'.format(self._path))
        self.module_type = None

    def _resolve_organization(self, organization=None):
        LOGGER.debug('Resolving organization')
        if organization:
            self.organization = organization.lower()
        else:
            try:
                temp_organization = self._parsed_yang.search('organization')[0].arg.lower()
                if 'cisco' in temp_organization or 'CISCO' in temp_organization:
                    self.organization = 'cisco'
                    return
                elif 'ietf' in temp_organization or 'IETF' in temp_organization:
                    self.organization = 'ietf'
                    return
            except:
                pass
            for ns, org in NS_MAP:
                if ns in self.namespace:
                    self.organization = org
                    return
            if self.organization is None:
                if 'cisco' in self.namespace or 'CISCO' in self.namespace:
                    self.organization = 'cisco'
                    return
                elif 'ietf' in self.namespace or 'IETF' in self.namespace:
                    self.organization = 'ietf'
                    return
                elif 'urn:' in self.namespace:
                    self.organization = \
                        self.namespace.split('urn:')[1].split(':')[0]
                    return
            if self.organization is None:
                self.organization = 'independent'

    def _resolve_prefix(self):
        LOGGER.debug('Resolving prefix')
        self.prefix = self._resolve_submodule_case('prefix')

    def _resolve_submodule_case(self, field):
        if self.module_type == 'submodule':
            LOGGER.debug(
                'Getting parent information because file {} is a submodule'.format(
                    self._path))
            yang_file = self._find_file(self.belongs_to)
            if yang_file is None:
                return None
            try:
                parsed_parent_yang = yangParser.parse(os.path.abspath(yang_file))
                return parsed_parent_yang.search(field)[0].arg
            except:
                if field == 'prefix':
                    return None
                else:
                    return MISSING_ELEMENT
        else:
            try:
                return self._parsed_yang.search(field)[0].arg
            except:
                if field == 'prefix':
                    return None
                else:
                    return MISSING_ELEMENT

    def _parse_status(self):
        LOGGER.debug('Parsing status of module {}'.format(self._path))
        status = {'status': 'unknown'}
        with_revision = [True, False]
        for w_rev in with_revision:
            if status['status'] == 'unknown':
                for name in self.jsons.names:
                    if status['status'] == 'unknown':
                        if name == 'IETFDraft':
                            status = self._get_module_status(w_rev, name, 3)
                        else:
                            status = self._get_module_status(w_rev, name)
                    else:
                        break
            else:
                break
        return status

    def _get_module_status(self, with_revision, name, index=0):
        if name == 'IETFYANGRFC':
            return {'status': 'unknown'}
        status = {}
        if with_revision:
            # try to find with revision
            try:
                yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
                status['status'] = self.jsons.status[name][yang_name_rev][index]
                if status['status'] == 'PASSED WITH WARNINGS':
                    status['status'] = 'passed-with-warnings'
                status['status'] = status['status'].lower()
                status['ths'] = self.jsons.headers[name]
                return status
            except:
                pass
        else:
            # try to find without revision
            try:
                yang_name = '{}.yang'.format(self.name)
                status['status'] = self.jsons.status[name][yang_name][index]
                if status['status'] == 'PASSED WITH WARNINGS':
                    status['status'] = 'passed-with-warnings'
                status['status'] = status['status'].lower()
                status['ths'] = self.jsons.headers[name]
                return status
            except:
                pass
        return {'status': 'unknown', 'ths': self.jsons.headers[name]}

    def _parse_result(self):
        LOGGER.debug('Parsing compilation status of module {}'.format(self._path))
        res = ''
        with_revision = [True, False]
        for w_rev in with_revision:
            for name in self.jsons.names:
                if name == 'IETFYANGRFC':
                    continue
                if res == '':
                    if name == 'IETFDraft':
                        res = self._parse_res(w_rev, name, 3)
                    else:
                        res = self._parse_res(w_rev, name)
                else:
                    return res
        return {'pyang': '', 'pyang_lint': '', 'confdrc': '', 'yumadump': '',
                'yanglint': ''}

    def _parse_res(self, with_revision, name, index=0):
        result = {}
        if with_revision:
            # try to find with revision
            try:
                yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
                result['pyang_lint'] = self.jsons.status[name][yang_name_rev][1 + index]
                result['pyang'] = self.jsons.status[name][yang_name_rev][2 + index]
                result['confdrc'] = self.jsons.status[name][yang_name_rev][3 + index]
                result['yumadump'] = self.jsons.status[name][yang_name_rev][4 + index]
                result['yanglint'] = self.jsons.status[name][yang_name_rev][5 + index]
                return result
            except:
                pass
        else:
            # try to find without revision
            try:
                yang_name = '{}.yang'.format(self.name)
                result['pyang_lint'] = self.jsons.status[name][yang_name][1 + index]
                result['pyang'] = self.jsons.status[name][yang_name][2 + index]
                result['confdrc'] = self.jsons.status[name][yang_name][3 + index]
                result['yumadump'] = self.jsons.status[name][yang_name][4 + index]
                result['yanglint'] = self.jsons.status[name][yang_name][5 + index]
                return result
            except:
                pass
        return ''

    def _parse_document_reference(self):
        LOGGER.debug(
            'Parsing document reference of module {}'.format(self._path))
        # try to find in draft without revision
        yang_name = '{}.yang'.format(self.name)
        yang_name_rev = '{}@{}.yang'.format(self.name, self.revision)
        try:
            doc_name = self.jsons.status['IETFDraft'][yang_name][0].split(
                '</a>')[0].split('\">')[1]
            doc_source = self.jsons.status['IETFDraft'][yang_name][0].split(
                'a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
        # try to find in draft with revision
        try:
            doc_name = self.jsons.status['IETFDraft'][yang_name_rev][
                0].split('</a>')[0].split('\">')[1]
            doc_source = self.jsons.status['IETFDraft'][yang_name_rev][
                0].split('a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
        # try to find in rfc with revision
        try:
            doc_name = self.jsons.status['IETFYANGRFC'][
                yang_name_rev].split('</a>')[0].split('\">')[1]
            doc_source = self.jsons.status['IETFYANGRFC'][
                yang_name_rev].split('a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
        # try to find in rfc without revision
        try:
            doc_name = self.jsons.status['IETFYANGRFC'][yang_name].split('</a>')[
                0].split('\">')[1]
            doc_source = self.jsons.status['IETFYANGRFC'][yang_name].split(
                'a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
        return [None, None]

    def _find_file(self, name: str, revision: str = '*') -> t.Optional[str]:
        pattern = '{}.yang'.format(name)
        pattern_with_revision = '{}@{}.yang'.format(name, revision)
        yang_file = find_first_file('/'.join(self._path.split('/')[0:-1]), pattern, pattern_with_revision, self.yang_models)
        return yang_file

    # NOTE: Could these just be empty strings instead?
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


class SdoModule(Module):

    def __init__(self, path: str, jsons: LoadFiles, dir_paths: t.Dict[str, str]):
        super().__init__(path, jsons, dir_paths)
        self._parsed_yang = yangParser.parse(os.path.abspath(self._path))



class VendorModule(Module):
    """A module with additional vendor information."""

    def __init__(self, path: str, jsons: LoadFiles, dir_paths: t.Dict[str, str],
                 data: t.Optional[t.Union[str, dict]] = None):
        super().__init__(path, jsons, dir_paths)
        if isinstance(data, str): # string from a capabilities file
            self.features = self._resolve_deviations_and_features('features=', data)
            deviation_names = self._resolve_deviations_and_features('deviations=', data)
            self.deviations  = []
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
            if 'revision' in data:
                revision_and_more = data.split('revision=')[1]
                revision = revision_and_more.split('&')[0]
                self.revision = revision

            self._path = self._find_file(data.split('&')[0], self.revision)
        elif isinstance(data, dict): # dict parsed out from a ietf-yang-library file
            self.deviations = data['deviations']
            self.features = data['features']
            self.revision = data['revision']
            self._path = self._find_file(data['name'], self.revision)
        if self._path:
            self._parsed_yang = yangParser.parse(os.path.abspath(self._path))
        else:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)

    def _resolve_schema(self, schema_base: str, git_commit_hash: str, path_in_repo: str):
        super()._resolve_schema(schema_base, git_commit_hash, path_in_repo)
        if schema_base:
            split_index = git_commit_hash
            if '/yangmodels/yang/' in self._path:
                split_index = '/yangmodels/yang/'
            suffix = os.path.abspath(self._path).split(split_index)[1]
            if path_in_repo:
                git_root_dir = path_in_repo.split('/')[0]
                if git_root_dir in suffix:
                    suffix = os.path.join(git_root_dir, suffix.split(git_root_dir)[1].removeprefix('/'))
            self.schema = os.path.join(schema_base, suffix.removeprefix('/'))


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
            implementation = self.Implementation()
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
