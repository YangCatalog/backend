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
import typing as t
from configparser import ConfigParser
from urllib.parse import quote, unquote

from redis import Redis

import utility.log as log
from utility.create_config import create_config

DEFAULT_VALUES = {'compilation-status': 'unknown', 'compilation-result': ''}


class RedisConnection:
    def __init__(
        self,
        modules_db: t.Optional[t.Union[int, str]] = None,
        vendors_db: t.Optional[t.Union[int, str]] = None,
        config: ConfigParser = create_config(),
    ):
        self.log_directory = config.get('Directory-Section', 'logs')
        self._redis_host = config.get('DB-Section', 'redis-host')
        self._redis_port = int(config.get('DB-Section', 'redis-port'))
        if modules_db is None:
            modules_db = config.get('DB-Section', 'redis-modules-db', fallback=1)
        if vendors_db is None:
            vendors_db = config.get('DB-Section', 'redis-vendors-db', fallback=4)
        self.modulesDB = Redis(host=self._redis_host, port=self._redis_port, db=modules_db)  # pyright: ignore
        self.vendorsDB = Redis(host=self._redis_host, port=self._redis_port, db=vendors_db)  # pyright: ignore
        self.temp_modulesDB = Redis(host=self._redis_host, port=self._redis_port, db=5)

        self.LOGGER = log.get_logger('redisModules', os.path.join(self.log_directory, 'redisModulesConnection.log'))

    def update_module_properties(self, new_module: dict, existing_module: dict):
        keys = {**new_module, **existing_module}.keys()
        dependencies_keys = ('dependents', 'dependencies')
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
            elif key in dependencies_keys:
                new_prop_list = new_module.get(key, [])
                existing_prop_list = existing_module.get(key)
                if not existing_prop_list:
                    existing_module[key] = new_prop_list
                    continue
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
                if not existing_value or (existing_value != new_value and new_value is not DEFAULT_VALUES.get(key)):
                    existing_module[key] = new_value

        return existing_module

    def populate_modules(self, new_modules: list[dict]):
        """Merge new data of each module in 'new_modules' list with existing data already stored in Redis.
        Set updated data to Redis under created key in format: <name>@<revision>/<organization>

        Argument:
            :param new_modules  (list) list of modules which need to be stored into Redis cache
        """
        for new_module in new_modules:
            redis_key = self._create_module_key(new_module)
            redis_module = self.get_module(redis_key)
            temp_module_data = self.get_temp_module(redis_key)
            if redis_module == '{}':
                updated_module = new_module
            else:
                updated_module = self.update_module_properties(new_module, json.loads(redis_module))

            if temp_module_data != '{}':
                updated_module = self.update_module_properties(json.loads(temp_module_data), updated_module)
                self.delete_temporary([redis_key])

            self.set_redis_module(updated_module, redis_key)

    def get_all_modules(self) -> str:
        data = self.modulesDB.get('modules-data')
        return (data or b'{}').decode('utf-8')

    def get_module(self, key: str) -> str:
        data = self.modulesDB.get(key)
        return (data or b'{}').decode('utf-8')

    def get_temp_module(self, key: str) -> str:
        data = self.temp_modulesDB.get(key)
        return (data or b'{}').decode('utf-8')

    def set_redis_module(self, module: dict, redis_key: str):
        result = self.modulesDB.set(redis_key, json.dumps(module))
        if result:
            self.LOGGER.info(f'{redis_key} key updated')
        else:
            self.LOGGER.exception(f'Problem while setting {redis_key}')

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
        redis_key = self._create_module_key(module)
        redis_module_raw = self.get_module(redis_key)
        redis_module = json.loads(redis_module_raw)
        redis_module.pop('expires', None)
        result = self.set_redis_module(redis_module, redis_key)

        return result

    def delete_temporary(self, modules_keys: list):
        self.temp_modulesDB.delete(*modules_keys)

    def _create_module_key(self, module: dict):
        return f'{module.get("name")}@{module.get("revision")}/{module.get("organization")}'

    def create_implementation_key(self, impl: dict):
        quoted = [
            key_quote(i) for i in [impl['vendor'], impl['platform'], impl['software-version'], impl['software-flavor']]
        ]
        return '/'.join(quoted)

    # VENDORS DATABASE COMMUNICATION ###
    def get_all_vendors(self):
        data = self.vendorsDB.get('vendors-data')
        return (data or b'{}').decode('utf-8')

    def get_implementation(self, key: str):
        data = self.vendorsDB.get(key)
        return (data or b'{}').decode('utf-8')

    def populate_implementation(self, new_implementation: list):
        """
        Merge new data of each implementation in 'new_implementations' list with existing data already stored in Redis.
        Set updated data to Redis under created key in format:
        <vendors>/<platform>/<software-version>/<software-flavor>

        Argument:
            :param new_implementation  (list) list of modules which need to be stored into Redis cache
        """
        data = {}
        for implementation in new_implementation:
            vendor_name = implementation['name']
            for platform in implementation['platforms']['platform']:
                platform_name = platform['name']
                for software_version in platform['software-versions']['software-version']:
                    software_version_name = software_version['name']
                    for software_flavor in software_version['software-flavors']['software-flavor']:
                        software_flavor_name = software_flavor['name']
                        quoted = [
                            key_quote(i)
                            for i in [vendor_name, platform_name, software_version_name, software_flavor_name]
                        ]
                        key = '/'.join(quoted)
                        if not data.get(key):
                            data[key] = {'protocols': software_flavor.get('protocols', {})}
                        if 'modules' not in data[key]:
                            data[key]['modules'] = {'module': []}
                        data[key]['modules']['module'] += software_flavor.get('modules', {}).get('module', [])

        for key, new_data in data.items():
            existing_json = self.get_implementation(key)
            if existing_json == '{}':
                merged_data = new_data
            else:
                existing_data = json.loads(existing_json)
                self.merge_data(existing_data.get('modules'), new_data.get('modules'))
                merged_data = existing_data
            self.vendorsDB.set(key, json.dumps(merged_data))

    def reload_vendors_cache(self):
        vendors_data = self.create_vendors_data_dict()

        self.vendorsDB.set('vendors-data', json.dumps({'vendor': vendors_data}))

    def create_vendors_data_dict(self, searched_key: str = '') -> list:
        vendors_data = {'yang-catalog:vendor': []}
        for vendor_key in self.vendorsDB.scan_iter():
            key = vendor_key.decode('utf-8')
            if key != 'vendors-data' and searched_key in key:
                try:
                    data = self.vendorsDB.get(key)
                    redis_vendors_raw = (data or b'{}').decode('utf-8')
                    redis_vendor_data = json.loads(redis_vendors_raw)
                    vendor_name, platform_name, software_version_name, software_flavor_name = (
                        unquote(part) for part in key.split('/')
                    )
                    # Build up an object from bottom
                    software_flavor = {'name': software_flavor_name, **redis_vendor_data}
                    software_version = {
                        'name': software_version_name,
                        'software-flavors': {'software-flavor': [software_flavor]},
                    }
                    platform = {'name': platform_name, 'software-versions': {'software-version': [software_version]}}
                    vendor = {'name': vendor_name, 'platforms': {'platform': [platform]}}
                    new_data = {'yang-catalog:vendor': [vendor]}
                    self.merge_data(vendors_data, new_data)
                except Exception:
                    self.LOGGER.exception('Problem while creating vendor dict')
                    continue
        return vendors_data['yang-catalog:vendor']

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

    def merge_data(self, old: dict, new: dict):
        # we're expecting a dict in this shape: {<some string>: [...]}
        data_type, old_data_list = next(iter(old.items()))
        data_type, new_data_list = next(iter(new.items()))
        if data_type == 'module':
            old_modules = {self._create_module_key(module): module for module in old_data_list}
            new_modules = {self._create_module_key(module): module for module in new_data_list}
            old_modules.update(new_modules)
            old['module'] = list(old_modules.values())
        else:
            old_data = {value['name']: value for value in old_data_list}
            new_data = {value['name']: value for value in new_data_list}
            for name in new_data.keys():
                if name in old_data:
                    # We already have object on the same level -> we need to go one level deeper
                    for key, value in old_data[name].items():
                        if key in new_data[name]:
                            if isinstance(value, dict):
                                self.merge_data(old_data[name][key], new_data[name][key])
                            else:
                                old_data[name][key] = new_data[name][key]
                else:
                    old_data[name] = new_data[name]
            old[data_type] = list(old_data.values())


def key_quote(key: str) -> str:
    return quote(key, safe='')
