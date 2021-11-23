# Copyright The IETF Trust 2021, All Rights Reserved
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
This script contains methods which are used across the application to communicate with ConfD database.
In each script where GET, PATCH, DELETE or HEAD request to the ConfD need to be done, confdService is initialized.
This eliminates need for setting URL, auth and headers each time.
"""

__author__ = "Slavomir Mazur"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "slavomir.mazur@pantheon.tech"


import requests

import utility.log as log
from utility.create_config import create_config
from utility.staticVariables import confd_headers


class ConfdService:
    def __init__(self):
        config = create_config()
        self.__confd_ip = config.get('Web-Section', 'confd-ip')
        self.__confd_port = config.get('Web-Section', 'confd-port')
        self.__confd_protocol = config.get('General-Section', 'protocol-confd')
        self.credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
        self.log_directory = config.get('Directory-Section', 'logs')

        self.LOGGER = log.get_logger('confdService', '{}/confdService.log'.format(self.log_directory))
        self.confd_prefix = '{}://{}:{}'.format(self.__confd_protocol, self.__confd_ip, self.__confd_port)

    def get_restconf(self):
        path = '{}/restconf'.format(self.confd_prefix)
        response = requests.get(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def get_module(self, module_key: str):
        self.LOGGER.debug('Sending GET request to the module {}'.format(module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(self.confd_prefix, module_key)
        modules_data = requests.get(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return modules_data

    def get_catalog_data(self):
        self.LOGGER.debug('Sending GET request to get all the catalog data')
        path = '{}/restconf/data/yang-catalog:catalog'.format(self.confd_prefix)
        catalog_data = requests.get(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return catalog_data

    def patch_module(self, module_key: str, new_data: str):
        self.LOGGER.debug('Sending PATCH request to the module {}'.format(module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(self.confd_prefix, module_key)
        response = requests.patch(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def patch_modules(self, new_data: str):
        self.LOGGER.debug('Sending PATCH request to patch multiple modules')
        path = '{}/restconf/data/yang-catalog:catalog/modules/'.format(self.confd_prefix)
        response = requests.patch(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def patch_vendors(self, new_data: str):
        self.LOGGER.debug('Sending PATCH request to patch multiple vendors')
        path = '{}/restconf/data/yang-catalog:catalog/vendors/'.format(self.confd_prefix)
        response = requests.patch(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_module(self, module_key: str):
        self.LOGGER.debug('Sending DELETE request to the module {}'.format(module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(self.confd_prefix, module_key)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_dependent(self, module_key: str, dependent: str):
        self.LOGGER.debug('Sending DELETE request to dependent {} of the module {}'.format(dependent, module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}/dependents={}'.format(
            self.confd_prefix, module_key, dependent)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_expires(self, module_key: str):
        self.LOGGER.debug('Sending DELETE request to expire property of the module {}'.format(module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}/expires'.format(self.confd_prefix, module_key)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_implementation(self, module_key: str, implementation_key: str):
        self.LOGGER.debug('Sending DELETE request to implementation {} of the module {}'.format(
            implementation_key, module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}/implementations/implementation={}'.format(
            self.confd_prefix, module_key, implementation_key)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_vendor_data(self, confd_suffix: str):
        path = '{}{}'.format(self.confd_prefix, confd_suffix)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def head_catalog(self):
        path = '{}/restconf/data/yang-catalog:catalog'.format(self.confd_prefix)
        response = requests.head(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def head_confd(self):
        path = '{}/restconf/data/'.format(self.confd_prefix)
        response = requests.head(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def put_module_metadata(self, new_data: str):
        path = '{}/restconf/data/module-metadata:modules'.format(self.confd_prefix)
        response = requests.put(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def put_platform_metadata(self, new_data: str):
        path = '{}/restconf/data/platform-implementation-metadata:platforms'.format(self.confd_prefix)
        response = requests.put(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response
