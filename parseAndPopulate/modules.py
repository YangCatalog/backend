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

import filecmp
import os
import shutil
import typing as t

from parseAndPopulate.dir_paths import DirPaths
from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.models.implementation import Implementation
from parseAndPopulate.models.submodule import Submodule
from parseAndPopulate.resolvers.basic import BasicResolver
from parseAndPopulate.resolvers.generated_from import GeneratedFromResolver
from parseAndPopulate.resolvers.implementations import ImplementationResolver
from parseAndPopulate.resolvers.imports import ImportsResolver
from parseAndPopulate.resolvers.module_type import ModuleTypeResolver
from parseAndPopulate.resolvers.namespace import NamespaceResolver
from parseAndPopulate.resolvers.organization import OrganizationResolver
from parseAndPopulate.resolvers.prefix import PrefixResolver
from parseAndPopulate.resolvers.revision import RevisionResolver
from parseAndPopulate.resolvers.semantic_version import SemanticVersionResolver
from parseAndPopulate.resolvers.submodule import SubmoduleResolver
from parseAndPopulate.resolvers.yang_version import YangVersionResolver
from utility import log, yangParser
from utility.create_config import create_config
from utility.util import get_yang, resolve_revision


class Module:
    """This is a class of a single module to parse all the basic metadata we can get out of it."""

    # NOTE: Maybe we should consider passing all or some of the arguments togeather in some sort of structure,
    #      as passing this many arguments is ugly and error prone.
    def __init__(
        self,
        name: str,
        path: str,
        schemas: dict,
        dir_paths: DirPaths,
        yang_modules: dict,
        additional_info: t.Optional[t.Dict[str, str]],
    ):
        """
        Initialize and parse everything out of a module.

        Arguments:
            :param name:            (str) name of the module (not parsed out of the module)
            :param path:            (str) path to yang file being parsed
            :param dir_paths:       (dict) paths to various needed directories according to configuration
            :param yang_modules:    (dict) yang modules we've already parsed
            :param schema_parts:    (SchemaParts) Parts of the URL that links to the module in Github
            :param aditional_info:  (dict) some aditional information about module given from client
            :param vendor_info:     (dict) optional dict with additional vendor information
        """
        global LOGGER
        LOGGER = log.get_logger('modules', '{}/parseAndPopulate.log'.format(dir_paths['log']))
        config = create_config()
        self._domain_prefix = config.get('Web-Section', 'domain-prefix', fallback='https://yangcatalog.org')
        self._nonietf_dir = config.get('Directory-Section', 'non-ietf-directory')
        self.html_result_dir = dir_paths['result']
        self._schemas = schemas
        self._path = path
        self.yang_models_path = dir_paths['yang_models']

        try:
            self._parsed_yang = yangParser.parse(self._path)
        except yangParser.ParseException:
            LOGGER.exception('Missing yang file {}'.format(self._path))
            raise
        self.implementations: t.List[Implementation] = []
        self._parse_all(name, yang_modules, additional_info)

    def _parse_all(self, name: str, yang_modules: dict, additional_info: t.Optional[t.Dict[str, str]] = None):
        if not additional_info:
            additional_info = {}
        self.author_email = additional_info.get('author-email')
        self.maturity_level = additional_info.get('maturity-level')
        self.reference = additional_info.get('reference')
        self.document_name = additional_info.get('document-name')
        self.module_classification = additional_info.get('module-classification', 'unknown')
        generated_from = additional_info.get('generated-from')
        organization = additional_info.get('organization')
        self.compilation_status = 'unknown'
        self.compilation_result = None
        self.ietf_wg = None

        self.name: str = self._parsed_yang.arg or name
        revision_resolver = RevisionResolver(self._parsed_yang, LOGGER)
        self.revision = revision_resolver.resolve()
        name_revision = '{}@{}'.format(self.name, self.revision)

        belongs_to_resolver = BasicResolver(self._parsed_yang, 'belongs_to')
        self.belongs_to = belongs_to_resolver.resolve()

        namespace_resolver = NamespaceResolver(self._parsed_yang, LOGGER, name_revision, self.belongs_to)
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

        imports_resolver = ImportsResolver(
            self._parsed_yang,
            LOGGER,
            self._path,
            self.schema,
            self._schemas,
            self.yang_models_path,
            self._nonietf_dir,
        )
        self.imports = imports_resolver.resolve()
        self.dependencies.extend(self.imports)

        semantic_version_resolver = SemanticVersionResolver(self._parsed_yang, LOGGER)
        self.semantic_version = semantic_version_resolver.resolve()

        yang_version_resolver = YangVersionResolver(self._parsed_yang, LOGGER)
        self.yang_version = yang_version_resolver.resolve()

        self.contact = BasicResolver(self._parsed_yang, 'contact').resolve()
        self.description = BasicResolver(self._parsed_yang, 'description').resolve()

        generated_from_resolver = GeneratedFromResolver(LOGGER, self.name, self.namespace)
        self.generated_from = generated_from or generated_from_resolver.resolve()

        prefix_resolver = PrefixResolver(self._parsed_yang, LOGGER, name_revision, self.belongs_to)
        self.prefix = prefix_resolver.resolve()

        self.tree = self._resolve_tree(self.module_type)

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

    def _resolve_schema(self, name_revision: str) -> t.Optional[str]:
        try:
            return self._schemas[name_revision]
        except KeyError:
            LOGGER.warning('Schema URL for {}@{} has not been resolved'.format(self.name, self.revision))


class SdoModule(Module):
    def __init__(
        self,
        name: str,
        path: str,
        schemas: dict,
        dir_paths: DirPaths,
        yang_modules: dict,
        aditional_info: t.Optional[t.Dict[str, str]] = None,
    ):
        super().__init__(name, os.path.abspath(path), schemas, dir_paths, yang_modules, aditional_info)


class VendorModule(Module):
    """A module with additional vendor information."""

    def __init__(
        self,
        name: str,
        path: str,
        schemas: dict,
        dir_paths: DirPaths,
        yang_modules: dict,
        vendor_info: t.Optional[dict] = None,
        aditional_info: t.Optional[t.Dict[str, str]] = None,
        data: t.Optional[t.Union[str, dict]] = None,
    ):
        """
        Initialize and parse everything out of a vendor module and
        add information from platform-metadata json files provided with Cisco modules.

        Arguments:
            :param name:                (str) name of the module (not parsed out of the module)
            :param path:                (str) path to yang file being parsed
            :param dir_paths:           (dict) paths to various needed directories according to configuration
            :param yang_modules:        (dict) yang modules we've already parsed
            :param schema_parts:        (SchemaParts) Parts of the URL that links to the module in Github
            :param aditional_info:      (dict) some aditional information about module given from client
            :param vendor_info:         (dict) dict with additional vendor information
        """

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
                    except FileNotFoundError:
                        deviation['revision'] = '1970-01-01'
                self.deviations.append(deviation)

        elif isinstance(data, dict):  # dict parsed out from a ietf-yang-library file
            self.deviations = data['deviations']
            self.features = data['features']
        super().__init__(name, path, schemas, dir_paths, yang_modules, aditional_info)

        if vendor_info is not None:
            implementation_resolver = ImplementationResolver(vendor_info, self.features, self.deviations)
            self.implementations += implementation_resolver.resolve()

    def _resolve_deviations_and_features(self, search_for: str, data: str) -> t.List[str]:
        ret = []
        if search_for in data:
            devs_or_features = data.split(search_for)[1]
            devs_or_features = devs_or_features.split('&')[0]
            ret = devs_or_features.split(',')
        return ret
