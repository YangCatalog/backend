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
import typing as t

import utility.log as log

from parseAndPopulate.modules import Module
from parseAndPopulate.nullJsonEncoder import NullJsonEncoder


def get_deviations(deviations):
    if deviations is None:
        return None
    else:
        return [{
            'name': dev.name,
            'revision': dev.revision
        } for dev in deviations]


def get_dependencies(dependencies):
    if dependencies is None:
        return None
    else:
        return [{
            'name': dep.name,
            'revision': dep.revision,
            'schema': dep.schema
        } for dep in dependencies]


class Dumper:
    """A dumper for yang module metadata."""

    def __init__(self, log_directory: str, file_name: str):
        """
        Arguments:
            :param log_directory:           (str) directory where the log file is saved
            :param file_name:               (str) name of the file to which the modules are dumped
        """
        global LOGGER
        LOGGER = log.get_logger(__name__, '{}/parseAndPopulate.log'.format(log_directory))
        self.file_name = file_name
        self.yang_modules: t.Dict[str, Module] = {}

    def add_module(self, yang: Module):
        """
        Add a module's data to be dumped.

        Argument:
            :param yang     (Modules) Modules object
        """
        key = '{}@{}/{}'.format(yang.name, yang.revision, yang.organization)
        LOGGER.debug('Module {} parsed'.format(key))
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
        LOGGER.debug('Creating {}.json file from sdo information'.format(self.file_name))

        with open('{}/{}.json'.format(directory, self.file_name), 'w') as prepare_model:
            json.dump({'module': [{
                'name': self.yang_modules[key].name,
                'revision': self.yang_modules[key].revision,
                'organization': self.yang_modules[key].organization,
                'schema': self.yang_modules[key].schema,
                'generated-from': self.yang_modules[key].generated_from,
                'maturity-level': self.yang_modules[key].maturity_level,
                'document-name': self.yang_modules[key].document_name,
                'author-email': self.yang_modules[key].author_email,
                'reference': self.yang_modules[key].reference,
                'module-classification': self.yang_modules[key].module_classification,
                'compilation-status': self.yang_modules[key].compilation_status,
                'compilation-result': self.yang_modules[key].compilation_result,
                'expires': None,
                'expired': None,
                'prefix': self.yang_modules[key].prefix,
                'yang-version': self.yang_modules[key].yang_version,
                'description': self.yang_modules[key].description,
                'contact': self.yang_modules[key].contact,
                'module-type': self.yang_modules[key].module_type,
                'belongs-to': self.yang_modules[key].belongs_to,
                'tree-type': None,
                'yang-tree': self.yang_modules[key].tree,
                'ietf': {
                    'ietf-wg': self.yang_modules[key].ietf_wg
                },
                'namespace': self.yang_modules[key].namespace,
                'submodule': json.loads(self.yang_modules[key].json_submodules),
                'dependencies': get_dependencies(self.yang_modules[key].dependencies),
                'semantic-version': self.yang_modules[key].semver,
                'derived-semantic-version': None,
                'implementations': {
                    'implementation': [{
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
                    } for implementation in
                        self.yang_modules[key].implementations],
                }
            } for key in sorted(self.yang_modules.keys())]}, prepare_model, cls=NullJsonEncoder)

    def dump_vendors(self, directory: str):
        """
        Dump vendor and implementation metadata into a normal.json file.

        Argument:
            :param directory    (str) Absolute path to the directory where .json file will be saved.
        """
        LOGGER.debug('Creating normal.json file from vendor implementation information')

        with open('{}/normal.json'.format(directory), 'w') as f:
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
                                                        'name':
                                                            self.yang_modules[key].name,
                                                        'revision':
                                                            self.yang_modules[key].revision,
                                                        'organization':
                                                            self.yang_modules[key].organization,
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
                    } for key in sorted(self.yang_modules.keys())
                        for impl in self.yang_modules[key].implementations]
                }
            }, f, cls=NullJsonEncoder)
