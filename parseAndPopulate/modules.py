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
import time
import typing as t

import statistic.statistics as stats
from utility import log, yangParser
from utility.create_config import create_config
from utility.staticVariables import IETF_RFC_MAP, MISSING_ELEMENT
from utility.util import get_yang, resolve_revision

from parseAndPopulate.dir_paths import DirPaths
from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.models.implementation import Implementation
from parseAndPopulate.models.submodule import Submodule
from parseAndPopulate.resolvers.basic import BasicResolver
from parseAndPopulate.resolvers.imports import ImportsResolver
from parseAndPopulate.resolvers.module_type import ModuleTypeResolver
from parseAndPopulate.resolvers.namespace import NamespaceResolver
from parseAndPopulate.resolvers.organization import OrganizationResolver
from parseAndPopulate.resolvers.revision import RevisionResolver
from parseAndPopulate.resolvers.semantic_version import SemanticVersionResolver
from parseAndPopulate.resolvers.submodule import SubmoduleResolver
from parseAndPopulate.resolvers.yang_version import YangVersionResolver


class Module:
    """This is a class of a single module to parse all the basic metadata we can get out of it."""

    # NOTE: Maybe we should consider passing all or some of the arguments togeather in some sort of structure,
    #      as passing this many arguments is ugly and error prone.
    def __init__(self, name: str, path: str, jsons: LoadFiles, schemas: dict, dir_paths: DirPaths,
                 yang_modules: dict, additional_info: t.Optional[t.Dict[str, str]]):
        """
        Initialize and parse everything out of a module.

        Arguments:
            :param name:            (str) name of the module (not parsed out of the module)
            :param path:            (str) path to yang file being parsed
            :param jsons:           (obj) LoadFiles class containing all the json
                                    and html files with parsed results
            :param dir_paths:       (dict) paths to various needed directories according to configuration
            :param yang_modules:    (dict) yang modules we've already parsed
            :param schema_parts:    (SchemaParts) Parts of the URL that links to the module in Github
            :param aditional_info:  (dict) some aditional information about module given from client
        """
        global LOGGER
        LOGGER = log.get_logger('modules', '{}/parseAndPopulate.log'.format(dir_paths['log']))
        config = create_config()
        self._domain_prefix = config.get('Web-Section', 'domain-prefix', fallback='https://yangcatalog.org')
        self._nonietf_dir = config.get('Directory-Section', 'non-ietf-directory')
        self.html_result_dir = dir_paths['result']
        self._jsons = jsons
        self._schemas = schemas
        self._path = path
        self.yang_models_path = dir_paths['yang_models']

        self._parsed_yang = yangParser.parse(self._path)
        self.implementations: t.List[Implementation] = []
        self._parse_all(name, yang_modules, additional_info)
        del self._jsons

    def _parse_all(self, name: str, yang_modules: dict, additional_info: t.Optional[t.Dict[str, str]] = None):
        if additional_info:
            author_email = additional_info.get('author-email')
            maturity_level = additional_info.get('maturity-level')
            reference = additional_info.get('reference')
            document_name = additional_info.get('document-name')
            generated_from = additional_info.get('generated-from')
            organization = (additional_info.get('organization') or MISSING_ELEMENT).lower()
            module_classification = additional_info.get('module-classification')
        else:
            author_email = None
            reference = None
            maturity_level = None
            generated_from = None
            organization = None
            module_classification = None
            document_name = None

        self.name: str = self._parsed_yang.arg or name
        revision_resolver = RevisionResolver(self._parsed_yang, LOGGER)
        self.revision = revision_resolver.resolve()
        name_revision = '{}@{}'.format(self.name, self.revision)

        belongs_to_resolver = BasicResolver(self._parsed_yang, 'belongs_to')
        self.belongs_to = belongs_to_resolver.resolve()

        namespace_resolver = NamespaceResolver(self._parsed_yang, LOGGER, name_revision, self._path, self.belongs_to)
        self.namespace = namespace_resolver.resolve()

        organization_resolver = OrganizationResolver(self._parsed_yang, LOGGER, self.namespace)
        self.organization = organization or organization_resolver.resolve()

        module_type_resolver = ModuleTypeResolver(self._parsed_yang, LOGGER)
        self.module_type = module_type_resolver.resolve()

        key = '{}@{}/{}'.format(self.name, self.revision, self.organization)
        if key in yang_modules:
            return

        self.schema = self._resolve_schema(name_revision)
        self.dependencies: t.List[Dependency] = []
        self.submodule: t.List[Submodule] = []
        submodule_resolver = SubmoduleResolver(self._parsed_yang, LOGGER, self._path, self.schema, self._schemas)
        self.dependencies, self.submodule = submodule_resolver.resolve()
        self.json_submodules = json.dumps([{
            'name': self.submodule[x].name,
            'schema': self.submodule[x].schema,
            'revision': self.submodule[x].revision
        } for x in range(0, len(self.submodule))])
        imports_resolver = ImportsResolver(self._parsed_yang, LOGGER, self._path,
                                           self.schema, self._schemas, self.yang_models_path, self._nonietf_dir)
        self.imports = imports_resolver.resolve()
        self.dependencies.extend(self.imports)

        semantic_version_resolver = SemanticVersionResolver(self._parsed_yang)
        self.semantic_version = semantic_version_resolver.resolve()

        yang_version_resolver = YangVersionResolver(self._parsed_yang)
        self.yang_version = yang_version_resolver.resolve()

        self.contact = BasicResolver(self._parsed_yang, 'contact').resolve()
        self.description = BasicResolver(self._parsed_yang, 'description').resolve()

        self.generated_from = generated_from or self._resolve_generated_from()
        self.compilation_status, self.compilation_result = \
            self._resolve_compilation_status_and_result(self.generated_from)

        self.prefix = self._resolve_prefix()
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

    def _resolve_tree(self, module_type: t.Optional[str]):
        if module_type == 'module':
            return '{}/api/services/tree/{}@{}.yang'.format(self._domain_prefix, self.name, self.revision)
        return None

    def _save_file(self, save_file_dir: str):
        file_with_path = '{}/{}@{}.yang'.format(save_file_dir, self.name, self.revision)
        try:
            same = filecmp.cmp(self._path, file_with_path)
            if not same:
                shutil.copy(self._path, file_with_path)
        except FileNotFoundError:
            shutil.copy(self._path, file_with_path)

    def _resolve_semver(self):
        # cisco specific modules - semver defined is inside revision
        try:
            parsed_semver = self._parsed_yang.search('revision')[0].search(('cisco-semver', 'module-version'))[0].arg
            return re.findall('[0-9]+.[0-9]+.[0-9]+', parsed_semver).pop()
        except IndexError:
            pass

        # openconfig specific modules
        try:
            parsed_semver = self._parsed_yang.search(('oc-ext', 'openconfig-version'))[0].arg
            return re.findall('[0-9]+.[0-9]+.[0-9]+', parsed_semver).pop()
        except IndexError:
            pass

        return None

    def _resolve_schema(self, name_revision: str) -> t.Optional[str]:
        try:
            return self._schemas[name_revision]
        except KeyError:
            LOGGER.warning('Schema URL for {}@{} has not been resolved'.format(self.name, self.revision))


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

        return '{}/results/{}'.format(self._domain_prefix, file_url)

    def _resolve_prefix(self) -> t.Optional[str]:
        LOGGER.debug('Resolving prefix')
        return self._resolve_submodule_case('prefix')

    def _resolve_submodule_case(self, field: str) -> t.Optional[str]:
        if self.module_type == 'submodule':
            LOGGER.debug('Getting parent information because file {} is a submodule'.format(self._path))
            if self.belongs_to:
                yang_file = get_yang(self.belongs_to)
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


class SdoModule(Module):

    def __init__(self, name: str, path: str, jsons: LoadFiles, schemas: dict, dir_paths: DirPaths,
                 yang_modules: dict, aditional_info: t.Optional[t.Dict[str, str]] = None):
        super().__init__(name, os.path.abspath(path), jsons, schemas, dir_paths, yang_modules, aditional_info)


class VendorModule(Module):
    """A module with additional vendor information."""

    def __init__(self, name: str, path: str, jsons: LoadFiles, schemas: dict, dir_paths: DirPaths,
                 yang_modules: dict, aditional_info: t.Optional[t.Dict[str, str]] = None,
                 data: t.Optional[t.Union[str, dict]] = None):
        # these are required for self._find_file() to work
        self.yang_models = dir_paths['yang_models']
        self.features = []
        self.deviations = []
        if isinstance(data, str):  # string from a capabilities file
            self.features = self._resolve_deviations_and_features('features=', data)
            deviation_names = self._resolve_deviations_and_features('deviations=', data)
            for deviation_name in deviation_names:
                deviation = {'name': deviation_name}
                yang_file = get_yang(deviation_name)
                if yang_file is None:
                    deviation['revision'] = '1970-01-01'
                else:
                    try:
                        deviation['revision'] = resolve_revision(os.path.abspath(yang_file))
                    except:
                        deviation['revision'] = '1970-01-01'
                self.deviations.append(deviation)

        elif isinstance(data, dict):  # dict parsed out from a ietf-yang-library file
            self.deviations = data['deviations']
            self.features = data['features']
        super().__init__(name, path, jsons, schemas, dir_paths, yang_modules, aditional_info)

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
