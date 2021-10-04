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

        self.LOGGER = log.get_logger('confdService', '{}/confd.log'.format(self.log_directory))
        self.confd_prefix = '{}://{}:{}'.format(self.__confd_protocol, self.__confd_ip, self.__confd_port)

    def get_module(self, module_key: str):
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(self.confd_prefix, module_key)
        modules_data = requests.get(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return modules_data

    def get_catalog_data(self):
        path = '{}/restconf/data/yang-catalog:catalog'.format(self.confd_prefix)
        catalog_data = requests.get(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return catalog_data

    def patch_module(self, module_key: str, new_data):
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(self.confd_prefix, module_key)
        response = requests.patch(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def patch_modules(self, new_data):
        path = '{}/restconf/data/yang-catalog:catalog/modules/'.format(self.confd_prefix)
        response = requests.patch(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def patch_vendors(self, new_data):
        path = '{}/restconf/data/yang-catalog:catalog/vendors/'.format(self.confd_prefix)
        response = requests.patch(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_module(self, module_key: str):
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(self.confd_prefix, module_key)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_dependent(self, module_key: str, dependent: str):
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}/dependents={}'.format(self.confd_prefix, module_key, dependent)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_expires(self, module_key: str):
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}/expires'.format(self.confd_prefix, module_key)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def head_catalog(self):
        path = '{}/restconf/data'.format(self.confd_prefix)
        response = requests.head(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response
