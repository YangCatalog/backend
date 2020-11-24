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
This class will create temporary json file
with all the metadata that were parsed from
yang files on provided directory to runCapabilities.py
script. The json file is formatted to be compliant with
yangcatalog.yang file
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import json

import requests
import utility.log as log

from parseAndPopulate.modules import Modules
from parseAndPopulate.nullJsonEncoder import NullJsonEncoder


class Prepare:
    def __init__(self, log_directory: str, file_name: str, yangcatalog_api_prefix: str):
        global LOGGER
        LOGGER = log.get_logger(__name__, log_directory + '/parseAndPopulate.log')
        if len(LOGGER.handlers) > 1:
            LOGGER.handlers[1].close()
            LOGGER.removeHandler(LOGGER.handlers[1])
        self.file_name = file_name
        self.name_revision_organization = set()
        self.yang_modules = {}
        self.yangcatalog_api_prefix = yangcatalog_api_prefix

    def add_key_sdo_module(self, yang: Modules):
        """
        Create key in format <module_name>@<revision>/<organization> from yang Modules object passed as argument.
        Dictionary of yang_modules is updated using created key and Modules object as a value.

        :param yang     (obj) Modules object of yang module.
        """
        key = '{}@{}/{}'.format(yang.name, yang.revision, yang.organization)
        LOGGER.debug('Module {} parsed'.format(key))
        if key in self.name_revision_organization:
            self.yang_modules[key].implementation.extend(yang.implementation)
        else:
            if yang.tree is not None:
                yang.tree = '{}{}'.format(self.yangcatalog_api_prefix,
                                          yang.tree)

            self.name_revision_organization.add(key)
            self.yang_modules[key] = yang
            if self.yang_modules[key].compilation_status is None:
                try:
                    self.yang_modules[key].compilation_status = requests.get('{}search/modules/{},{},{}'.format(
                                                                             self.yangcatalog_api_prefix,
                                                                             yang.name, yang.revision,
                                                                             yang.organization)).json()['module'][0].get('compilation-status')
                except:
                    self.yang_modules[key].compilation_status = 'unknown'

    def dump_modules(self, directory: str):
        """
        All the data about modules from yang_modules variable are dumped into json file.
        This file is stored in directory pased as an argument and is used by runCapabilities.py script

        :param directory    (str) Absolute path to the directory where .json file will be saved.
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
                'module-classification': self.yang_modules[
                    key].module_classification,
                'compilation-status': self.yang_modules[key].compilation_status,
                'compilation-result': self.yang_modules[key].compilation_result,
                'expires': self.yang_modules[key].expiration_date,
                'expired': self.yang_modules[key].expired,
                'prefix': self.yang_modules[key].prefix,
                'yang-version': self.yang_modules[key].yang_version,
                'description': self.yang_modules[key].description,
                'contact': self.yang_modules[key].contact,
                'module-type': self.yang_modules[key].module_type,
                'belongs-to': self.yang_modules[key].belongs_to,
                'tree-type': self.yang_modules[key].tree_type,
                'yang-tree': self.yang_modules[key].tree,
                'ietf': {
                    'ietf-wg': self.yang_modules[key].ietf_wg
                },
                'namespace': self.yang_modules[key].namespace,
                'submodule': json.loads(self.yang_modules[key].json_submodules),
                'dependencies': self.__get_dependencies(self.yang_modules[key]
                                                        .dependencies),
                'semantic-version': self.yang_modules[key].semver,
                'derived-semantic-version': self.yang_modules[key].derived_semver,
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
                        'deviation': self.__get_deviations(
                            implementation.deviations),
                        'conformance-type': implementation.conformance_type
                    } for implementation in
                        self.yang_modules[key].implementation],
                }
            } for key in self.name_revision_organization]}, prepare_model, cls=NullJsonEncoder)

    def dump_vendors(self, directory: str):
        """
        All the data about vendor and implementation are dumped into json file.
        This file is stored in directory pased as an argument and is used by populate.py script

        :param directory    (str) Absolute path to the directory where .json file will be saved.
        """
        LOGGER.debug('Creating normal.json file from vendor implementation information')

        with open('{}/normal.json'.format(directory), 'w') as ietf_model:
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
                                                        'capabilities': impl.capability,
                                                        'protocol-version': impl.netconf_version,
                                                    }]
                                                },
                                                'modules': {
                                                    'module': [{
                                                        'name':
                                                            self.yang_modules[
                                                                key].name,
                                                        'revision':
                                                            self.yang_modules[
                                                                key].revision,
                                                        'organization':
                                                            self.yang_modules[
                                                                key].organization,
                                                        'os-version': impl.os_version,
                                                        'feature-set': impl.feature_set,
                                                        'os-type': impl.os_type,
                                                        'feature': impl.feature,
                                                        'deviation': self.__get_deviations(
                                                            impl.deviations),
                                                        'conformance-type': impl.conformance_type
                                                    }],
                                                }
                                            }]
                                        }
                                    }]
                                }
                            }]
                        }
                    } for key in self.name_revision_organization for impl in
                        self.yang_modules[key].implementation]
                }
            }, ietf_model, cls=NullJsonEncoder)

    @staticmethod
    def __get_deviations(deviations):
        if deviations is None:
            return None
        else:
            return [
                {'name': dev.name,
                 'revision': dev.revision
                 } for dev in deviations]

    @staticmethod
    def __get_dependencies(dependencies):
        if dependencies is None:
            return None
        else:
            return [
                {'name': dep.name,
                 'revision': dep.revision,
                 'schema': dep.schema
                 } for dep in dependencies]
