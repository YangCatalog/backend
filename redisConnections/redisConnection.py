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


import json
import os

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
        updated_module = {**existing_module, **new_module}
        for prop in ['submodule', 'dependents', 'dependencies', 'implementations']:
            new_prop_list = new_module.get(prop, [])
            if new_prop_list:
                if prop == 'implementations':
                    existing_prop_list = existing_module.get('implementations', {}).get('implementation', [])
                    existing_impl_names = [self.create_implementation_key(impl) for impl in existing_prop_list]
                    for new_implementation in new_prop_list.get('implementation', []):
                        if self.create_implementation_key(new_implementation) not in existing_impl_names:
                            existing_prop_list.append(new_implementation)
                    updated_module['implementations']['implementation'] = existing_prop_list
                else:
                    existing_prop_list = existing_module.get(prop, [])
                    existing_prop_names = [existing_prop.get('name') for existing_prop in existing_prop_list]
                    for new_prop_value in new_prop_list:
                        if new_prop_value.get('name') not in existing_prop_names:
                            existing_prop_list.append(new_prop_value)
                            existing_prop_names.append(new_prop_value.get('name'))
                        else:
                            index = existing_prop_names.index(new_prop_value.get('name'))
                            existing_prop_list[index] = new_prop_value
                    updated_module[prop] = existing_prop_list

        return updated_module

    def populate_modules(self, new_modules: list):
        """ Merge new data of each module in "new_modules" list with existing data already stored in Redis.
        Set updated data to Redis under created key in format: <name>@<revision>/<organization>

        Argument:
            :param new_modules  (list) list of modules which need to be stored into Redis cache
        """
        new_merged_modules = {}

        for new_module in new_modules:
            redis_key = self.__create_module_key(new_module)
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

    def delete_expires(self, module: dict):
        result = False
        redis_key = self.__create_module_key(module)
        redis_module_raw = self.get_module(redis_key)
        redis_module = json.loads(redis_module_raw)
        redis_module.pop('expires', None)
        result = self.set_redis_module(redis_module, redis_key)

        return result

    def __create_module_key(self, module: dict):
        return '{}@{}/{}'.format(module.get('name'), module.get('revision'), module.get('organization'))

    def create_implementation_key(self, impl: dict):
        return '{}/{}/{}/{}'.format(impl['vendor'].replace(' ', '#'), impl['platform'].replace(' ', '#'),
                                    impl['software-version'].replace(' ', '#'), impl['software-flavor'].replace(' ', '#'))
