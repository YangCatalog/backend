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

import json
import os.path
import typing as t

import utility.log as log
from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.models.implementation import Implementation
from parseAndPopulate.models.submodule import Submodule

from parseAndPopulate.modules import Module
from parseAndPopulate.nullJsonEncoder import NullJsonEncoder


def get_deviations(deviations: t.Optional[list[Implementation.Deviation]]) -> t.Optional[list[dict]]:
    if deviations is None:
        return None
    return [
        {
            'name': dev.name,
            'revision': dev.revision
        } for dev in deviations
    ]


def get_dependencies(dependencies: t.Union[None, list[Dependency], list[Submodule]]) -> t.Optional[list[dict]]:
    if dependencies is None:
        return None
    return [
        {
            'name': dep.name,
            'revision': dep.revision,
            'schema': dep.schema
        } for dep in dependencies
    ]


class Dumper:
    """A dumper for yang module metadata."""

    def __init__(self, log_directory: str, file_name: str):
        """
        Arguments:
            :param log_directory:           (str) directory where the log file is saved
            :param file_name:               (str) name of the file to which the modules are dumped
        """
        self.logger = log.get_logger(__name__, os.path.join(log_directory, 'parseAndPopulate.log'))
        self.file_name = file_name
        self.yang_modules: dict[str, Module] = {}

    def add_module(self, yang: Module):
        """
        Add a module's data to be dumped.

        Argument:
            :param yang     (Module) Module object to be dumped
        """
        key = f'{yang.name}@{yang.revision}/{yang.organization}'
        self.logger.debug(f'Module {key} parsed')
        if key in self.yang_modules:
            self.yang_modules[key].implementations.extend(yang.implementations)
        else:
            self.yang_modules[key] = yang

    def dump_modules(self, directory: str):
        """
        Dump all module data into a json file.

        Argument:
            :param directory    (str) Absolute path to the directory where the .json file will be saved.
        """
        self.logger.debug(f'Creating {self.file_name}.json file from sdo information')

        with open(os.path.join(directory, f'{self.file_name}.json'), 'w') as prepare_model:
            json.dump(
                {
                    'module': [
                        {
                            'name': (yang_module := self.yang_modules[key]).name,
                            'revision': yang_module.revision,
                            'organization': yang_module.organization,
                            'schema': yang_module.schema,
                            'generated-from': yang_module.generated_from,
                            'maturity-level': yang_module.maturity_level,
                            'document-name': yang_module.document_name,
                            'author-email': yang_module.author_email,
                            'reference': yang_module.reference,
                            'module-classification': yang_module.module_classification,
                            'compilation-status': yang_module.compilation_status,
                            'compilation-result': yang_module.compilation_result,
                            'expires': None,
                            'expired': None,
                            'prefix': yang_module.prefix,
                            'yang-version': yang_module.yang_version,
                            'description': yang_module.description,
                            'contact': yang_module.contact,
                            'module-type': yang_module.module_type,
                            'belongs-to': yang_module.belongs_to,
                            'tree-type': None,
                            'yang-tree': yang_module.tree,
                            'ietf': {
                                'ietf-wg': yang_module.ietf_wg
                            },
                            'namespace': yang_module.namespace,
                            'submodule': get_dependencies(yang_module.submodule),
                            'dependencies': get_dependencies(yang_module.dependencies),
                            'semantic-version': yang_module.semantic_version,
                            'derived-semantic-version': None,
                            'implementations': {
                                'implementation': [
                                    {
                                        'vendor': implementation.vendor,
                                        'platform': implementation.platform,
                                        'software-version': implementation.software_version,
                                        'software-flavor': implementation.software_flavor,
                                        'os-version': implementation.os_version,
                                        'feature-set': implementation.feature_set,
                                        'os-type': implementation.os_type,
                                        'feature': implementation.feature,
                                        'deviation': get_deviations(implementation.deviations),
                                        'conformance-type': implementation.conformance_type
                                    } for implementation in yang_module.implementations
                                ],
                            }
                        } for key in sorted(self.yang_modules.keys())
                    ]
                },
                prepare_model, cls=NullJsonEncoder
            )

    def dump_vendors(self, directory: str):
        """
        Dump vendor and implementation metadata into a normal.json file.

        Argument:
            :param directory    (str) Absolute path to the directory where .json file will be saved.
        """
        self.logger.debug('Creating normal.json file from vendor implementation information')

        with open(os.path.join(directory, 'normal.json'), 'w') as f:
            json.dump({
                'vendors': {
                    'vendor': [{
                        'name': impl.vendor,
                        'platforms': {
                            'platform': [{
                                'name': impl.platform,
                                'software-versions': {
                                    'software-version': [{
                                        'name': impl.software_version,
                                        'software-flavors': {
                                            'software-flavor': [{
                                                'name': impl.software_flavor,
                                                'protocols': {
                                                    'protocol': [{
                                                        'name': 'netconf',
                                                        'capabilities': impl.capabilities,
                                                        'protocol-version': impl.netconf_versions,
                                                    }]
                                                },
                                                'modules': {
                                                    'module': [{
                                                        'name': (yang_module := self.yang_modules[key]).name,
                                                        'revision': yang_module.revision,
                                                        'organization': yang_module.organization,
                                                        'os-version': impl.os_version,
                                                        'feature-set': impl.feature_set,
                                                        'os-type': impl.os_type,
                                                        'feature': impl.feature,
                                                        'deviation': get_deviations(impl.deviations),
                                                        'conformance-type': impl.conformance_type
                                                    }],
                                                }
                                            }]
                                        }
                                    }]
                                }
                            }]
                        }
                    } for key in sorted(self.yang_modules.keys()) for impl in self.yang_modules[key].implementations]
                }
            }, f, cls=NullJsonEncoder)
