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
import json
import os
import shutil
import typing as t
from configparser import ConfigParser

from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.models.directory_paths import DirPaths
from parseAndPopulate.models.implementation import Implementation
from parseAndPopulate.models.submodule import Submodule
from parseAndPopulate.models.vendor_modules import VendorInfo
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
from utility.util import get_yang, resolve_revision, yang_url


class Module:
    """This is a class of a single module to parse all the basic metadata we can get out of it."""

    # NOTE: Maybe we should consider passing all or some of the arguments togather in some sort of structure,
    #      as passing this many arguments is ugly and error-prone.

    AdditionalModuleInfo = t.TypedDict(
        'AdditionalModuleInfo',
        {
            'author-email': str,
            'maturity-level': str,
            'reference': str,
            'document-name': str,
            'module-classification': str,
            'generated-from': str,
            'organization': str,
        },
        total=False,
    )

    def __init__(
        self,
        path: str,
        dir_paths: DirPaths,
        yang_modules: t.Iterable[str],
        additional_info: t.Optional[AdditionalModuleInfo],
        config: ConfigParser = create_config(),
        redis_connection: t.Optional[RedisConnection] = None,
        can_be_already_stored_in_db: bool = False,
    ):
        """
        Initialize and parse everything out of a module.

        Arguments:
            :param path:            (str) path to yang file being parsed
            :param dir_paths:       (dict) paths to various needed directories according to configuration
            :param yang_modules:    (dict) yang modules we've already parsed
            :param additional_info:  (dict) some additional information about module given from client
            :param can_be_already_stored_in_db:  (bool) True if there's a chance that this module is already
                stored in the DB (for example, we already have a stored cache of this module),
                so we can try to avoid using resolvers and load information from the DB instead
        """
        self.logger = log.get_logger('modules', os.path.join(dir_paths['log'], 'parseAndPopulate.log'))
        self._domain_prefix = config.get('Web-Section', 'domain-prefix', fallback='https://yangcatalog.org')
        self._nonietf_dir = config.get('Directory-Section', 'non-ietf-directory')
        self.html_result_dir = dir_paths['result']
        self._path = path
        self.yang_models_path = dir_paths['yang_models']
        self.dependencies: list[Dependency] = []
        self.submodule: list[Submodule] = []
        self.imports: list[Dependency] = []
        self.semantic_version: t.Optional[str] = None
        self.schema: t.Optional[str] = None
        self.contact: t.Optional[str] = None
        self.description: t.Optional[str] = None
        self.prefix: t.Optional[str] = None
        self.tree: t.Optional[str] = None
        self.can_be_already_stored_in_db = can_be_already_stored_in_db
        self._redis_connection = (
            redis_connection if redis_connection or not can_be_already_stored_in_db else RedisConnection(config=config)
        )

        self._parsed_yang = yangParser.parse(self._path)
        self.implementations: list[Implementation] = []
        self._parse_all(yang_modules, additional_info)

    def _parse_all(self, yang_modules: t.Iterable[str], additional_info: t.Optional[AdditionalModuleInfo]):
        additional_info = additional_info or self.AdditionalModuleInfo()
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

        if self._parsed_yang.arg is None:
            raise ValueError(f'{self._path} did not contain a module statement')
        self.name: str = self._parsed_yang.arg
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
        if (
            self.can_be_already_stored_in_db
            and self._redis_connection
            and (module_data := self._redis_connection.get_module(key)) != '{}'
        ):
            self._populate_information_from_db(json.loads(module_data))
            return

        self.schema = yang_url(self.name, self.revision)

        submodule_resolver = SubmoduleResolver(self._parsed_yang, self.logger, self._domain_prefix)
        self.dependencies, self.submodule = submodule_resolver.resolve()

        imports_resolver = ImportsResolver(
            self._parsed_yang,
            self.logger,
            self._domain_prefix,
        )
        self.imports = imports_resolver.resolve()
        self.dependencies.extend(self.imports)

        semantic_version_resolver = SemanticVersionResolver(self._parsed_yang, self.logger)
        self.semantic_version = semantic_version_resolver.resolve()

        yang_version_resolver = YangVersionResolver(self._parsed_yang, self.logger)
        self.yang_version = yang_version_resolver.resolve()

        self.contact = BasicResolver(self._parsed_yang, 'contact').resolve()
        self.description = BasicResolver(self._parsed_yang, 'description').resolve()

        self.generated_from = generated_from or GeneratedFromResolver(self.logger, self.name, self.namespace).resolve()

        prefix_resolver = PrefixResolver(self._parsed_yang, self.logger, name_revision, self.belongs_to)
        self.prefix = prefix_resolver.resolve()

        self.tree = self._resolve_tree(self.module_type)

    def _populate_information_from_db(self, module_data_from_db: dict):
        dependencies_keys = ('submodule', 'dependencies')
        for key, value in module_data_from_db.items():
            if key == 'implementations':
                continue
            elif key == 'ietf':
                self.ietf_wg = value['ietf-wg']
            elif key == 'yang-tree':
                self.tree = value
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
                    dependency_instance.name = dependency.get('name')
                    dependency_instance.revision = dependency.get('revision')
                    dependency_instance.schema = dependency.get('schema')
                    dependencies.append(dependency_instance)
                attribute += dependencies
            else:
                setattr(self, key.replace('-', '_'), value)

    def _resolve_tree(self, module_type: t.Optional[str]) -> t.Optional[str]:
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


class SdoModule(Module):
    def __init__(
        self,
        path: str,
        dir_paths: DirPaths,
        yang_modules: t.Iterable[str],
        additional_info: t.Optional[Module.AdditionalModuleInfo] = None,
        config: ConfigParser = create_config(),
        redis_connection: t.Optional[RedisConnection] = None,
        can_be_already_stored_in_db: bool = False,
    ):
        super().__init__(
            os.path.abspath(path),
            dir_paths,
            yang_modules,
            additional_info,
            config=config,
            redis_connection=redis_connection,
            can_be_already_stored_in_db=can_be_already_stored_in_db,
        )


class VendorModule(Module):
    """A module with additional vendor information."""

    def __init__(
        self,
        path: str,
        dir_paths: DirPaths,
        yang_modules: t.Iterable[str],
        vendor_info: t.Optional[VendorInfo] = None,
        additional_info: t.Optional[Module.AdditionalModuleInfo] = None,
        data: t.Optional[t.Union[str, dict]] = None,
        config: ConfigParser = create_config(),
        redis_connection: t.Optional[RedisConnection] = None,
        can_be_already_stored_in_db: bool = False,
    ):
        """
        Initialize and parse everything out of a vendor module and
        add information from platform-metadata json files provided with Cisco modules.

        Arguments:
            :param path:                (str) path to yang file being parsed
            :param dir_paths:           (dict) paths to various needed directories according to configuration
            :param yang_modules:        (dict) yang modules we've already parsed
            :param additional_info:      (dict) some additional information about module given from client
            :param vendor_info:         (Optional[VendorInfo]) dict with additional vendor information
        """

        # these are required for self._find_file() to work
        self.yang_models = dir_paths['yang_models']
        self.deviations = []
        self.features = []
        if data:
            self._resolve_deviations_and_features(data)
        super().__init__(
            path,
            dir_paths,
            yang_modules,
            additional_info,
            config=config,
            redis_connection=redis_connection,
            can_be_already_stored_in_db=can_be_already_stored_in_db,
        )
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
