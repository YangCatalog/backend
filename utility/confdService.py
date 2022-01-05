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

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'


import json
import os

import requests

import utility.log as log
from utility import messageFactory
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

    def get_restconf(self) -> requests.Response:
        path = '{}/restconf'.format(self.confd_prefix)
        response = requests.get(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def get_module(self, module_key: str) -> requests.Response:
        self.LOGGER.debug('Sending GET request to the module {}'.format(module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(self.confd_prefix, module_key)
        modules_data = requests.get(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return modules_data

    def get_catalog_data(self) -> requests.Response:
        self.LOGGER.debug('Sending GET request to get all the catalog data')
        path = '{}/restconf/data/yang-catalog:catalog'.format(self.confd_prefix)
        catalog_data = requests.get(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return catalog_data

    def patch_module(self, module: dict) -> requests.Response:
        module_key = self.create_module_key(module)
        self.LOGGER.debug('Sending PATCH request to the module {}'.format(module_key))
        patch_data = {'yang-catalog:module': module}
        patch_json = json.dumps(patch_data)
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(self.confd_prefix, module_key)
        response = requests.patch(path, patch_json, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def _patch(self, data: list, type: str, log_file: str) -> bool:
        errors = False
        chunk_size = 500
        failed_data = {}
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        path = '{}/restconf/data/yang-catalog:catalog/{}/'.format(self.confd_prefix, type)
        self.LOGGER.debug('Sending PATCH request to patch multiple {}'.format(type))
        for i, chunk in enumerate(chunks, start=1):
            self.LOGGER.debug('Processing chunk {} out of {}'.format(i, len(chunks)))
            patch_data = {type: {type.rstrip('s'): chunk}}
            patch_json = json.dumps(patch_data)
            response = requests.patch(path, patch_json, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)
            if response.status_code == 400:
                self.LOGGER.warning('Failed to batch patch {}, falling back to patching individually'.format(type))
                for datum in chunk:
                    patch_data = {type: {type.rstrip('s'): [datum]}}
                    patch_json = json.dumps(patch_data)
                    response = requests.patch(path, patch_json, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)
                    if response.status_code == 400:
                        errors = True
                        with open(os.path.join(self.log_directory, log_file), 'a') as f:
                            if type == 'modules':
                                name_revision = '{}@{}'.format(datum['name'], datum['revision'])
                                self.LOGGER.error('Failed to patch {} {}'.format(type.rstrip('s'), name_revision))
                                try:
                                    failed_data[name_revision] = json.loads(response.text)
                                except json.decoder.JSONDecodeError:
                                    self.LOGGER.exception('No test in response')
                                f.write('{}@{} error: {}\n'.format(datum['name'], datum['revision'], response.text))
                            elif type == 'vendors':
                                platform_name = datum['platforms']['platform'][0]['name']
                                vendor_platform = '{} {}'.format(datum['name'], platform_name)
                                self.LOGGER.error('Failed to patch {} {}'.format(type.rstrip('s'), vendor_platform))
                                try:
                                    failed_data[vendor_platform] = json.loads(response.text)
                                except json.decoder.JSONDecodeError:
                                    self.LOGGER.exception('No test in response')
                                f.write('{} {} error: {}\n'.format(datum['name'], platform_name, response.text))
        if failed_data:
            mf = messageFactory.MessageFactory()
            mf.send_confd_writing_failures(type, failed_data)
        return errors

    def patch_modules(self, modules: list) -> bool:
        return self._patch(modules, 'modules', 'confd-failed-patch-modules.log')

    def patch_vendors(self, vendors: list) -> bool:
        return self._patch(vendors, 'vendors', 'confd-failed-patch-vendors.log')

    def delete_module(self, module_key: str) -> requests.Response:
        self.LOGGER.debug('Sending DELETE request to the module {}'.format(module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}'.format(self.confd_prefix, module_key)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_vendor(self, confd_suffix: str) -> requests.Response:
        self.LOGGER.debug('Sending DELETE request to vendors branch {}'.format(confd_suffix))
        path = '{}/restconf/data/yang-catalog:catalog/{}'.format(self.confd_prefix, confd_suffix)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_dependent(self, module_key: str, dependent: str) -> requests.Response:
        self.LOGGER.debug('Sending DELETE request to dependent {} of the module {}'.format(dependent, module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}/dependents={}'.format(
            self.confd_prefix, module_key, dependent)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_submodule(self, module_key: str, submodule: str) -> requests.Response:
        self.LOGGER.debug('Sending DELETE request to submodule {} of the module {}'.format(submodule, module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}/submodule={}'.format(
            self.confd_prefix, module_key, submodule)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_expires(self, module_key: str) -> requests.Response:
        self.LOGGER.debug('Sending DELETE request to expire property of the module {}'.format(module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}/expires'.format(self.confd_prefix, module_key)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def delete_implementation(self, module_key: str, implementation_key: str) -> requests.Response:
        self.LOGGER.debug('Sending DELETE request to implementation {} of the module {}'.format(
            implementation_key, module_key))
        path = '{}/restconf/data/yang-catalog:catalog/modules/module={}/implementations/implementation={}'.format(
            self.confd_prefix, module_key, implementation_key)
        response = requests.delete(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def head_catalog(self) -> requests.Response:
        path = '{}/restconf/data/yang-catalog:catalog'.format(self.confd_prefix)
        response = requests.head(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def head_confd(self) -> requests.Response:
        path = '{}/restconf/data/'.format(self.confd_prefix)
        response = requests.head(path, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def put_module_metadata(self, new_data: str) -> requests.Response:
        path = '{}/restconf/data/module-metadata:modules'.format(self.confd_prefix)
        response = requests.put(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def put_platform_metadata(self, new_data: str) -> requests.Response:
        path = '{}/restconf/data/platform-implementation-metadata:platforms'.format(self.confd_prefix)
        response = requests.put(path, new_data, auth=(self.credentials[0], self.credentials[1]), headers=confd_headers)

        return response

    def create_module_key(self, module: dict) -> str:
        return '{},{},{}'.format(module['name'], module['revision'], module['organization'])
