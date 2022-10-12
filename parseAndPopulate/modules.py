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
import glob
import json
import os
import shutil
import subprocess
import typing as t
from configparser import ConfigParser

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
from redisConnections.redisConnection import RedisConnection
from utility import log, yangParser
from utility.create_config import create_config
from utility.staticVariables import ORGANIZATIONS, NAMESPACE_MAP
from utility.util import get_yang, resolve_revision
from utility.yangParser import ParseException


class Module:
    """This is a class of a single module to parse all the basic metadata we can get out of it."""

    # NOTE: Maybe we should consider passing all or some of the arguments togather in some sort of structure,
    #      as passing this many arguments is ugly and error-prone.
    def __init__(
            self,
            name: str,
            path: str,
            schemas: dict,
            dir_paths: DirPaths,
            yang_modules: dict,
            additional_info: t.Optional[dict[str, str]],
            config: ConfigParser = create_config(),
    ):
        """
        Initialize and parse everything out of a module.

        Arguments:
            :param name:            (str) name of the module (not parsed out of the module)
            :param path:            (str) path to yang file being parsed
            :param dir_paths:       (dict) paths to various needed directories according to configuration
            :param yang_modules:    (dict) yang modules we've already parsed
            :param additional_info:  (dict) some additional information about module given from client
        """
        self.logger = log.get_logger('modules', os.path.join(dir_paths['log'], 'parseAndPopulate.log'))
        self._domain_prefix = config.get('Web-Section', 'domain-prefix', fallback='https://yangcatalog.org')
        self._nonietf_dir = config.get('Directory-Section', 'non-ietf-directory')
        self.html_result_dir = dir_paths['result']
        self._schemas = schemas
        self._path = path
        self.yang_models_path = dir_paths['yang_models']

        self._parse_yang()
        self.implementations: list[Implementation] = []
        self._parse_all(name, yang_modules, additional_info)

    def _parse_yang(self):
        try:
            self._parsed_yang = yangParser.parse(self._path)
        except yangParser.ParseException:
            self.logger.exception(f'Missing yang file {self._path}')
            raise

    def _parse_all(self, name: str, yang_modules: dict, additional_info: t.Optional[dict[str, str]]):
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
        revision_resolver = RevisionResolver(self._parsed_yang, self.logger)
        self.revision = revision_resolver.resolve()
        name_revision = f'{self.name}@{self.revision}'

        belongs_to_resolver = BasicResolver(self._parsed_yang, 'belongs_to')
        self.belongs_to = belongs_to_resolver.resolve()

        namespace_resolver = NamespaceResolver(self._parsed_yang, self.logger, name_revision, self.belongs_to)
        self.namespace = namespace_resolver.resolve()

        organization_resolver = OrganizationResolver(self._parsed_yang, self.logger, self.namespace)
        self.organization = organization or organization_resolver.resolve()

        module_type_resolver = ModuleTypeResolver(self._parsed_yang, self.logger)
        self.module_type = module_type_resolver.resolve()

        key = f'{self.name}@{self.revision}/{self.organization}'
        if key in yang_modules:
            return

        self.schema = self._resolve_schema(name_revision)

        self.dependencies: list[Dependency] = []
        self.submodule: list[Submodule] = []
        submodule_resolver = SubmoduleResolver(self._parsed_yang, self.logger, self._path, self.schema, self._schemas)
        self.dependencies, self.submodule = submodule_resolver.resolve()

        imports_resolver = ImportsResolver(
            self._parsed_yang, self.logger, self._path, self.schema, self._schemas, self.yang_models_path,
            self._nonietf_dir,
        )
        self.imports = imports_resolver.resolve()
        self.dependencies.extend(self.imports)

        semantic_version_resolver = SemanticVersionResolver(self._parsed_yang, self.logger)
        self.semantic_version = semantic_version_resolver.resolve()

        yang_version_resolver = YangVersionResolver(self._parsed_yang, self.logger)
        self.yang_version = yang_version_resolver.resolve()

        self.contact = BasicResolver(self._parsed_yang, 'contact').resolve()
        self.description = BasicResolver(self._parsed_yang, 'description').resolve()

        generated_from_resolver = GeneratedFromResolver(self.logger, self.name, self.namespace)
        self.generated_from = generated_from or generated_from_resolver.resolve()

        prefix_resolver = PrefixResolver(self._parsed_yang, self.logger, name_revision, self.belongs_to)
        self.prefix = prefix_resolver.resolve()

        self.tree = self._resolve_tree(self.module_type)

    def _resolve_tree(self, module_type: t.Optional[str]):
        if module_type == 'module':
            return f'{self._domain_prefix}/api/services/tree/{self.name}@{self.revision}.yang'
        return None

    def _save_file(self, save_file_dir: str):
        file_with_path = f'{save_file_dir}/{self.name}@{self.revision}.yang'
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
            self.logger.warning(f'Schema URL for {self.name}@{self.revision} has not been resolved')


class SdoModule(Module):

    def __init__(
            self,
            name: str,
            path: str,
            schemas: dict,
            dir_paths: DirPaths,
            yang_modules: dict,
            additional_info: t.Optional[dict[str, str]] = None,
            config: ConfigParser = create_config(),
    ):
        super().__init__(name, os.path.abspath(path), schemas, dir_paths, yang_modules, additional_info, config=config)


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
            additional_info: t.Optional[dict[str, str]] = None,
            data: t.Optional[t.Union[str, dict]] = None,
            config: ConfigParser = create_config(),
            redis_connection: t.Optional[RedisConnection] = None
    ):
        """
        Initialize and parse everything out of a vendor module and 
        add information from platform-metadata json files provided with Cisco modules.

        Arguments:
            :param name:                (str) name of the module (not parsed out of the module)
            :param path:                (str) path to yang file being parsed
            :param dir_paths:           (dict) paths to various needed directories according to configuration
            :param yang_modules:        (dict) yang modules we've already parsed
            :param additional_info:      (dict) some additional information about module given from client
            :param vendor_info:         (dict) dict with additional vendor information
        """

        # these are required for self._find_file() to work
        self.yang_models = dir_paths['yang_models']
        self.deviations = []
        self.features = []
        if isinstance(data, (str, dict)):
            self._resolve_deviations_and_features(data)
        super().__init__(name, path, schemas, dir_paths, yang_modules, additional_info, config=config)
        if vendor_info is not None:
            self.implementations += ImplementationResolver(vendor_info, self.features, self.deviations).resolve()

    def _resolve_deviations_and_features(self, data: t.Union[str, dict]):
        if isinstance(data, str):  # string from a capabilities file
            self.features = self._resolve_deviations_or_features('features=', data)
            deviation_names = self._resolve_deviations_or_features('deviations=', data)
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
        elif isinstance(data, dict):  # dict parsed out from an ietf-yang-library file
            self.deviations, self.features = data['deviations'], data['features']

    def _resolve_deviations_or_features(self, search_for: str, data: str) -> list[str]:
        ret = []
        if search_for in data:
            devs_or_features = data.split(search_for)[1]
            devs_or_features = devs_or_features.split('&')[0]
            ret = devs_or_features.split(',')
        return ret


class VendorModuleFromDB(VendorModule):
    def __init__(
            self,
            name: str,
            path: str,
            schemas: dict,
            dir_paths: DirPaths,
            yang_modules: dict,
            vendor_info: t.Optional[dict] = None,
            additional_info: t.Optional[dict[str, str]] = None,
            data: t.Optional[t.Union[str, dict]] = None,
            config: ConfigParser = create_config(),
            redis_connection: t.Optional[RedisConnection] = None
    ):
        self.pyang_exec = config.get('Tool-Section', 'pyang-exec')
        self.modules_dir = config.get('Directory-Section', 'save-file-dir')
        self.redis_connection = redis_connection or RedisConnection(config=config)

        self.dependencies: list[Dependency] = []
        self.submodule: list[Submodule] = []
        self.imports: list[Dependency] = []
        super().__init__(
            name, path, schemas, dir_paths, yang_modules, vendor_info=vendor_info, additional_info=additional_info,
            data=data, config=config,
        )

    def _parse_yang(self):
        self.module_basic_info = self._parse_module_basic_info(self._path)
        if not self.module_basic_info:
            raise ParseException(f'Problem occurred while parsing basic info of: "{self._path}"')

    def _parse_all(self, name: str, yang_modules: dict, additional_info: t.Optional[dict[str, str]]):
        self.name = self.module_basic_info.get('name', name)
        self.revision = self.module_basic_info.get('revision', '1970-01-01')
        self._parse_organization()
        key = f'{self.name}@{self.revision}/{self.organization}'
        if key in yang_modules:
            return
        module_data = self.redis_connection.get_module(key)
        if module_data == '{}':
            return
        module_data = json.loads(module_data)
        dependencies_keys = ('submodule', 'dependencies')
        for key, value in module_data.items():
            if key == 'implementations':
                continue
            elif key == 'ietf':
                self.ietf_wg = value['ietf-wg']
            elif key in dependencies_keys:
                if key == 'dependencies':
                    attribute = self.dependencies
                    dependency_class = Dependency
                else:
                    attribute = self.submodule
                    dependency_class = Submodule
                dependencies = []
                for dependency in value:
                    dependency_instance = dependency_class()
                    dependency_instance.name = dependency['name']
                    dependency_instance.revision = dependency['revision']
                    dependency_instance.schema = dependency['schema']
                    dependencies.append(dependency_instance)
                attribute += dependencies
            else:
                setattr(self, key.replace('-', '_'), value)

    def _parse_organization(self):
        parsed_organization = self.module_basic_info.get('organization', '').lower()
        if parsed_organization in ORGANIZATIONS:
            self.organization = parsed_organization
            return
        namespace = self.json_parse_namespace(self.module_basic_info)
        self.organization = self._namespace_to_organization(namespace)

    def _namespace_to_organization(self, namespace: t.Optional[str]) -> str:
        if not namespace:
            return 'independent'
        for ns, org in NAMESPACE_MAP:
            if ns in namespace:
                return org
        if 'cisco' in namespace:
            return 'cisco'
        elif 'ietf' in namespace:
            return 'ietf'
        elif 'urn:' in namespace:
            return namespace.split('urn:')[1].split(':')[0]
        return 'independent'

    def json_parse_namespace(self, module_basic_info: dict) -> t.Optional[str]:
        if 'belongs-to' in module_basic_info:
            belongs_to = module_basic_info['belongs-to']
            try:
                path = max(glob.glob(os.path.join(self.modules_dir, f'{belongs_to}@*.yang')))
                parent_module = self._parse_module_basic_info(path)
                if not parent_module:
                    return
                return self.json_parse_namespace(parent_module)
            except ValueError:
                return
        return module_basic_info.get('namespace')

    def _parse_module_basic_info(self, path: str) -> t.Optional[dict]:
        json_module_command = f'pypy3 {self.pyang_exec} -fbasic-info --path="{self.modules_dir}" {path}'
        working_directory = os.getcwd()
        try:
            os.chdir(os.environ['BACKEND'])
            self.logger.info(f'BACKEND DIR: {os.environ["BACKEND"]}')
            with os.popen(json_module_command) as pipe:
                os.chdir(working_directory)
                return json.load(pipe)
        except json.decoder.JSONDecodeError:
            os.chdir(working_directory)
            self.logger.exception(
                f'Problem with parsing basic info of a file: "{self._path}", command: {json_module_command}'
            )
            return None
