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

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'


import json
import os

import redis
import utility.log as log
from redis import Redis
from utility.create_config import create_config


class RedisConnection:

    def __init__(self, modules_db: int = 1, vendors_db: int = 4):
        config = create_config()
        self.log_directory = config.get('Directory-Section', 'logs')
        self.__redis_host = config.get('DB-Section', 'redis-host')
        self.__redis_port = config.get('DB-Section', 'redis-port')
        self.modulesDB = Redis(host=self.__redis_host, port=self.__redis_port, db=modules_db)
        self.vendorsDB = Redis(host=self.__redis_host, port=self.__redis_port, db=vendors_db)

        self.LOGGER = log.get_logger('redisModules', os.path.join(self.log_directory, 'redisModulesConnection.log'))

    ### MODULES DATABASE COMMUNICATION ###
    def update_module_properties(self, new_module: dict, existing_module: dict):
        keys = {**new_module, **existing_module}.keys()
        for key in keys:
            if key == 'implementations':
                new_impls = new_module.get('implementations', {}).get('implementation', [])
                existing_impls = existing_module.get('implementations', {}).get('implementation', [])
                existing_impls_names = [self.create_implementation_key(impl) for impl in existing_impls]
                for new_impl in new_impls:
                    new_impl_name = self.create_implementation_key(new_impl)
                    if new_impl_name not in existing_impls_names:
                        existing_impls.append(new_impl)
                        existing_impls_names.append(new_impl_name)
            elif key in ['dependents', 'dependencies']:
                new_prop_list = new_module.get(key, [])
                existing_prop_list = existing_module.get(key, [])
                existing_prop_names = [existing_prop.get('name') for existing_prop in existing_prop_list]
                for new_prop in new_prop_list:
                    new_prop_name = new_prop.get('name')
                    if new_prop_name not in existing_prop_names:
                        existing_prop_list.append(new_prop)
                        existing_prop_names.append(new_prop_name)
                    else:
                        index = existing_prop_names.index(new_prop_name)
                        existing_prop_list[index] = new_prop
            else:
                new_value = new_module.get(key)
                existing_value = existing_module.get(key)
                if existing_value != new_value and new_value is not None:
                    existing_module[key] = new_value

        return existing_module

    def populate_modules(self, new_modules: list):
        """ Merge new data of each module in 'new_modules' list with existing data already stored in Redis.
        Set updated data to Redis under created key in format: <name>@<revision>/<organization>

        Argument:
            :param new_modules  (list) list of modules which need to be stored into Redis cache
        """
        new_merged_modules = {}

        for new_module in new_modules:
            redis_key = self._create_module_key(new_module)
            redis_module = self.get_module(redis_key)
            if redis_module == '{}':
                updated_module = new_module
            else:
                updated_module = self.update_module_properties(new_module, json.loads(redis_module))

            self.set_redis_module(updated_module, redis_key)
            new_merged_modules[redis_key] = updated_module

    def get_all_modules(self):
        data = self.modulesDB.get('modules-data')
        return (data or b'{}').decode('utf-8')

    def get_module(self, key: str):
        data = self.modulesDB.get(key)
        return (data or b'{}').decode('utf-8')

    def set_redis_module(self, module: dict, redis_key: str):
        result = self.modulesDB.set(redis_key, json.dumps(module))
        if result:
            self.LOGGER.info('{} key updated'.format(redis_key))
        else:
            self.LOGGER.exception('Problem while setting {}'.format(redis_key))

        return result

    def reload_modules_cache(self):
        modules_data = {}
        for key in self.modulesDB.scan_iter():
            redis_key = key.decode('utf-8')
            if redis_key != 'modules-data' and ':' not in redis_key:
                modules_data[redis_key] = json.loads(self.get_module(redis_key))
        result = self.set_redis_module(modules_data, 'modules-data')

        return result

    def delete_modules(self, modules_keys: list):
        result = self.modulesDB.delete(*modules_keys)
        return result

    def delete_dependent(self, redis_key: str, dependent_name: str):
        result = False
        redis_module_raw = self.get_module(redis_key)
        redis_module = json.loads(redis_module_raw)
        dependents_list = redis_module.get('dependents', [])
        dependent_to_remove = None
        for dependent in dependents_list:
            if dependent.get('name') == dependent_name:
                dependent_to_remove = dependent
                break

        if dependent_to_remove is not None:
            dependents_list.remove(dependent_to_remove)
            result = self.set_redis_module(redis_module, redis_key)
        return result

    def delete_implementation(self, redis_key: str, implemntation_key: str):
        impl_param_names = ['vendor', 'platform', 'software-version', 'software-flavor']
        result = False
        redis_module_raw = self.get_module(redis_key)
        redis_module = json.loads(redis_module_raw)
        implementations = redis_module.get('implementations', {}).get('implementation', [])
        for impl in implementations:
            imp_data = [impl[prop] for prop in impl_param_names]
            impl_key = ','.join(imp_data)
            if impl_key == implemntation_key:
                implementations.remove(impl)
                result = self.set_redis_module(redis_module, redis_key)
                break

        return result

    def delete_expires(self, module: dict):
        result = False
        redis_key = self._create_module_key(module)
        redis_module_raw = self.get_module(redis_key)
        redis_module = json.loads(redis_module_raw)
        redis_module.pop('expires', None)
        result = self.set_redis_module(redis_module, redis_key)

        return result

    def _create_module_key(self, module: dict):
        return '{}@{}/{}'.format(module.get('name'), module.get('revision'), module.get('organization'))

    def create_implementation_key(self, impl: dict):
        return '{}/{}/{}/{}'.format(impl['vendor'].replace(' ', '#'), impl['platform'].replace(' ', '#'),
                                    impl['software-version'].replace(' ', '#'), impl['software-flavor'].replace(' ', '#'))

    # VENDORS DATABASE COMMUNICATION ###
    def get_all_vendors(self):
        data = self.vendorsDB.get('vendors-data')
        return (data or b'{}').decode('utf-8')

    def get_implementation(self, key: str):
        data = self.vendorsDB.get(key)
        return (data or b'{}').decode('utf-8')

    def populate_implementation(self, new_implemenetation: list):
        """ Merge new data of each implementaion in 'new_implementaions' list with existing data already stored in Redis.
        Set updated data to Redis under created key in format:
        <vendors>/<platform>/<software-version>/<software-flavor>

        Argument:
            :param new_implemenetation  (list) list of modules which need to be stored into Redis cache
        """
        data = {}
        for implementation in new_implemenetation:
            vendor_name = implementation.get('name').replace(' ', '#')
            for platform in implementation.get('platforms').get('platform'):
                platform_name = platform.get('name').replace(' ', '#')
                for software_version in platform.get('software-versions').get('software-version'):
                    software_version_name = software_version.get('name').replace(' ', '#')
                    for software_flavor in software_version.get('software-flavors').get('software-flavor'):
                        software_flavor_name = software_flavor.get('name').replace(' ', '#')
                        key = '{}/{}/{}/{}'.format(vendor_name, platform_name, software_version_name, software_flavor_name)
                        if not data.get(key):
                            data[key] = {'protocols': software_flavor.get('protocols', {})}
                        if not data.get(key).get('modules'):
                            data[key]['modules'] = {'module': []}
                        for module in software_flavor.get('modules', {}).get('module', []):
                            data[key]['modules']['module'].append(module)

        for key, value in data.items():
            existing_data = self.get_implementation(key)
            if existing_data == '{}':
                new_data = value
            else:
                existing_implementation = json.loads(existing_data)
                existing_modules = existing_implementation.get('modules').get('module')
                existing_modules_keys = [self._create_module_key(module) for module in existing_modules]
                new_modules_list = value.get('modules', {}).get('module', [])
                for module in new_modules_list:
                    mod_key = self._create_module_key(module)
                    if mod_key not in existing_modules_keys:
                        existing_modules.append(module)
                        existing_modules_keys.append(mod_key)
                    else:
                        index = existing_modules_keys.index(mod_key)
                        existing_modules[index] = module
                new_data = {
                    'protocols': value.get('protocols'),
                    'modules': {
                        'module': existing_modules
                    }
                }

            self.vendorsDB.set(key, json.dumps(new_data))

    def reload_vendors_cache(self):
        vendors_data = self.create_vendors_data_dict()

        vendors_list = []
        for val in vendors_data.values():
            vendors_list.append(val)
        self.vendorsDB.set('vendors-data', json.dumps({'vendor': vendors_list}))

    def create_vendors_data_dict(self):
        vendors_data = {}
        for vendor_key in self.vendorsDB.scan_iter():
            key = vendor_key.decode('utf-8')
            if key != 'vendors-data':
                data = self.vendorsDB.get(key)
                redis_vendors_raw = (data or b'{}').decode('utf-8')
                redis_vendor_data = json.loads(redis_vendors_raw)
                vendor_name, platform_name, software_version_name, software_flavor_name = key.replace('#', ' ').split('/')
                # Build up an object from bottom
                software_flavor = {'name': software_flavor_name, **redis_vendor_data}
                software_version = {'name': software_version_name, 'software-flavors': {'software-flavor': [software_flavor]}}
                platform = {'name': platform_name, 'software-versions': {'software-version': [software_version]}}
                vendor = {'name': vendor_name, 'platforms': {'platform': [platform]}}

                if vendors_data.get(vendor_name):
                    existing_vendor = vendors_data.get(vendor_name)
                    existing_platforms = existing_vendor.get('platforms').get('platform')

                    for existing_platform in existing_platforms:
                        if existing_platform.get('name') == platform_name:
                            existing_versions = existing_platform.get('software-versions').get('software-version')

                            for existing_version in existing_versions:
                                if existing_version.get('name') == software_version_name:
                                    existing_flavors = existing_platform.get('software-flavors').get('software-flavor')

                                    for existing_flavor in existing_flavors:
                                        if existing_flavor.get('name') == software_flavor_name:
                                            pass
                                    else:
                                        existing_flavors.append(software_flavor)
                                        break
                            else:
                                existing_versions.append(software_version)
                                break
                    else:
                        existing_platforms.append(platform)
                else:
                    vendors_data[vendor_name] = vendor

        return vendors_data

    def delete_vendor(self, vendor_key: str):
        result = 0
        keys_to_delete = []
        for key in self.vendorsDB.scan_iter():
            redis_key = key.decode('utf-8')
            if vendor_key in redis_key:
                keys_to_delete.append(redis_key)

        if keys_to_delete:
            result = self.vendorsDB.delete(*keys_to_delete)
        return result
