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
Backup or restore all yangcatalog data.
Redis .rdb files are prioritized. JSON dumps are used if .rdb files aren't present.
Load adittionally makes a PATCH request to write the yang-catalog@2018-04-03 module to ConfD.
This script runs as a daily cronjob.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'


import datetime
import gzip
import json
import os
import time
import typing as t
from time import sleep

import utility.log as log
from redisConnections.redisConnection import RedisConnection
from requests import ConnectionError
from utility.confdService import ConfdService
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.staticVariables import backup_date_format
from utility.util import get_list_of_backups, job_log

current_file_basename = os.path.basename(__file__)


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = __doc__
        config = create_config()
        args: t.List[Arg] = [
            {
                'flag': '--name_save',
                'help': 'Set name of the file to save. Default name is date and time in UTC',
                'type': str,
                'default': datetime.datetime.utcnow().strftime(backup_date_format)
            },
            {
                'flag': '--name_load',
                'help': 'Set name of the file to load. Default will take a last saved file',
                'type': str,
                'default': ''
            },
            {
                'flag': '--type',
                'help': 'Set whether you want to save a file or load a file. Default is save',
                'type': str,
                'choices': ['save', 'load'],
                'default': 'save'
            }
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])

        self.log_directory = config.get('Directory-Section', 'logs')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.cache_directory = config.get('Directory-Section', 'cache')
        self.redis_host = config.get('DB-Section', 'redis-host')
        self.redis_port = config.get('DB-Section', 'redis-port')
        self.var_yang = config.get('Directory-Section', 'var')


def feed_confd_modules(modules: list, confdService: ConfdService):
    return confdService.patch_modules(modules)


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    cache_directory = scriptConf.cache_directory
    log_directory = scriptConf.log_directory
    temp_dir = scriptConf.temp_dir
    var_yang = scriptConf.var_yang
    confdService = ConfdService()

    confd_backups = os.path.join(cache_directory, 'confd')
    redis_backups = os.path.join(cache_directory, 'redis')
    redis_json_backup = os.path.join(cache_directory, 'redis-json')

    LOGGER = log.get_logger('recovery', os.path.join(log_directory, 'yang.log'))
    LOGGER.info(f'Starting {args.type} process of Redis database')
    job_log(start_time, temp_dir, status='In Progress', filename=current_file_basename)

    if 'save' == args.type:
        # Redis dump.rdb file backup
        redis_backup_file = f'{var_yang}/redis/dump.rdb'
        if not os.path.exists(redis_backups):
            os.mkdir(redis_backups)
        if os.path.exists(redis_backup_file):
            redis_copy_file = os.path.join(redis_backups, f'{args.name_save}.rdb.gz')
            with gzip.open(redis_copy_file, 'w') as save_file:
                with open(redis_backup_file, 'rb') as original:
                    save_file.write(original.read())
            LOGGER.info('Backup of Redis dump.rdb file created')
        else:
            LOGGER.warning('Redis dump.rdb file does not exists')

        # Backup content of Redis into JSON file
        redisConnection = RedisConnection()
        redis_modules_raw = redisConnection.get_all_modules()
        redis_vendors_raw = redisConnection.get_all_vendors()
        redis_modules_dict = json.loads(redis_modules_raw)
        redis_modules = [i for i in redis_modules_dict.values()]
        redis_vendors = json.loads(redis_vendors_raw)

        if not os.path.exists(redis_json_backup):
            os.mkdir(redis_json_backup)
        with open(os.path.join(redis_json_backup, 'backup.json'), 'w') as f:
            data = {
                'yang-catalog:catalog': {
                    'modules': redis_modules,
                    'vendors': redis_vendors
                }
            }
            json.dump(data, f)

        num_of_modules = len(redis_modules)
        num_of_vendors = len(redis_vendors.get('vendor', []))
        messages = [
            {'label': 'Saved modules', 'message': num_of_modules},
            {'label': 'Saved vendors', 'message': num_of_vendors}
        ]
        LOGGER.info('Save completed successfully')
        job_log(start_time, temp_dir, messages=messages, status='Success', filename=current_file_basename)
    else:
        file_name = ''
        if args.name_load:
            file_name = os.path.join(confd_backups, args.name_load)
        else:
            list_of_backups = get_list_of_backups(confd_backups)
            file_name = os.path.join(confd_backups, list_of_backups[-1])

        redisConnection = RedisConnection()
        redis_modules = redisConnection.get_all_modules()
        yang_catalog_module = redisConnection.get_module('yang-catalog@2018-04-03/ietf')

        if '{}' in (redis_modules, yang_catalog_module):
            # RDB not exists - load from JSON
            backup_path = os.path.join(redis_json_backup, 'backup.json')
            modules = []
            vendors = []
            if os.path.exists(backup_path):
                with open(backup_path, 'r') as file_load:
                    catalog_data = json.load(file_load)
                    modules = catalog_data.get('yang-catalog:catalog', {}).get('modules', [])
                    vendors = catalog_data.get('yang-catalog:catalog', {}).get('vendors', {}).get('vendor', [])
            else:
                if file_name.endswith('.gz'):
                    with gzip.open(file_name, 'r') as file_load:
                        LOGGER.info(f'Loading file {file_load.name}')
                        catalog_data = json.loads(file_load.read().decode())
                        modules = catalog_data.get('yang-catalog:catalog', {}).get('modules', {}).get('module', [])
                        vendors = catalog_data.get('yang-catalog:catalog', {}).get('vendors', {}).get('vendor', [])
                elif file_name.endswith('.json'):
                    with open(file_name, 'r') as file_load:
                        LOGGER.info(f'Loading file {file_load.name}')
                        catalog_data = json.load(file_load)
                        modules = catalog_data.get('yang-catalog:catalog', {}).get('modules', {}).get('module', [])
                        vendors = catalog_data.get('yang-catalog:catalog', {}).get('vendors', {}).get('vendor', [])
                else:
                    print('unable to load modules - ending')

            redisConnection.populate_modules(modules)
            redisConnection.populate_implementation(vendors)
            redisConnection.reload_modules_cache()
            redisConnection.reload_vendors_cache()
            LOGGER.info('All the modules data set to Redis successfully')

        tries = 4
        try:
            response = confdService.head_confd()
            LOGGER.info(f'Status code for HEAD request {response.status_code} ')
            if response.status_code == 200:
                yang_catalog_module = redisConnection.get_module('yang-catalog@2018-04-03/ietf')
                error = feed_confd_modules([json.loads(yang_catalog_module)], confdService)
                if error:
                    LOGGER.error('Error occurred while patching yang-catalog@2018-04-03/ietf module')
                else:
                    LOGGER.info('yang-catalog@2018-04-03/ietf patched successfully')
        except ConnectionError:
            if tries == 0:
                LOGGER.exception('Unable to connect to ConfD for over 5 minutes')
            tries -= 1
            sleep(60)

    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
