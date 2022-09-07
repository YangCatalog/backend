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
Load additionally makes a PATCH request to write the yang-catalog@2018-04-03 module to ConfD.
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
from configparser import ConfigParser
from time import sleep

import utility.log as log
from redisConnections.redisConnection import RedisConnection
from requests import ConnectionError
from utility.confdService import ConfdService
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.staticVariables import JobLogStatuses, backup_date_format
from utility.util import get_list_of_backups, job_log

current_file_basename = os.path.basename(__file__)


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = __doc__
        mutually_exclusive_args: list[list[Arg]] = [
            [
                {
                    'flag': '--save',
                    'help': 'Set true if you want to backup data',
                    'action': 'store_true',
                    'default': False,
                },
                {
                    'flag': '--load',
                    'help': 'Set true if you want to load data from backup to the database',
                    'action': 'store_true',
                    'default': False,
                },
            ],
        ]
        args: t.List[Arg] = [
            {
                'flag': '--file',
                'help': (
                    'Set name of the file to save data to/load data from. Default name is empty. '
                    'If name is empty: load operation will use the last backup file, '
                    'save operation will use date and time in UTC.'
                ),
                'type': str,
                'default': ''
            },
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [], mutually_exclusive_args)


class Recovery:
    def __init__(self, script_conf: BaseScriptConfig = ScriptConfig(), config: ConfigParser = create_config()):
        self.start_time = None
        self.job_log_messages = []
        self.yang_catalog_module_name = 'yang-catalog@2018-04-03/ietf'

        self.args = script_conf.args
        self.config = config
        self.log_directory = self.config.get('Directory-Section', 'logs')
        self.temp_dir = self.config.get('Directory-Section', 'temp')
        self.cache_directory = self.config.get('Directory-Section', 'cache')
        self.redis_host = self.config.get('DB-Section', 'redis-host')
        self.redis_port = self.config.get('DB-Section', 'redis-port')
        self.var_yang = self.config.get('Directory-Section', 'var')

        self.redis_connection = RedisConnection()
        self.confd_service = ConfdService()
        self.confd_backups = os.path.join(self.cache_directory, 'confd')
        self.redis_backups = os.path.join(self.cache_directory, 'redis')
        self.redis_json_backup = os.path.join(self.cache_directory, 'redis-json')
        self.logger = log.get_logger('recovery', os.path.join(self.log_directory, 'yang.log'))

    def start_process(self):
        self.start_time = int(time.time())
        process_type = 'save' if self.args.save else 'load'
        self.logger.info(f'Starting {process_type} process of Redis database')
        job_log_filename = 'recovery - save' if self.args.save else current_file_basename
        job_log(self.start_time, self.temp_dir, status=JobLogStatuses.IN_PROGRESS, filename=job_log_filename)
        if self.args.save:
            self.backup_data_from_db()
        elif self.args.load:
            self.load_data_from_backup_to_db()
        self.logger.info(f'{process_type} process of Redis database finished successfully')
        job_log(
            self.start_time, self.temp_dir, messages=self.job_log_messages, status=JobLogStatuses.SUCCESS,
            filename=job_log_filename,
        )

    def backup_data_from_db(self):
        self.args.file = self.args.file or datetime.datetime.utcnow().strftime(backup_date_format)
        os.makedirs(self.redis_backups, exist_ok=True)
        self._backup_redis_rdb_file()
        self._backup_redis_modules()
        self.logger.info('Save completed successfully')

    def _backup_redis_rdb_file(self):
        # Redis dump.rdb file backup
        redis_rdb_file = os.path.join(self.var_yang, 'redis', 'dump.rdb')
        if os.path.exists(redis_rdb_file):
            redis_copy_file = os.path.join(self.redis_backups, f'{self.args.file}.rdb.gz')
            with gzip.open(redis_copy_file, 'w') as save_file:
                with open(redis_rdb_file, 'rb') as original:
                    save_file.write(original.read())
            self.logger.info('Backup of Redis dump.rdb file created')
            return
        self.logger.warning('Redis dump.rdb file does not exists')

    def _backup_redis_modules(self):
        # Backup content of Redis into JSON file
        redis_modules_raw = self.redis_connection.get_all_modules()
        redis_vendors_raw = self.redis_connection.get_all_vendors()
        redis_modules_dict = json.loads(redis_modules_raw)
        redis_modules = [module for module in redis_modules_dict.values()]
        redis_vendors = json.loads(redis_vendors_raw)

        os.makedirs(self.redis_json_backup, exist_ok=True)
        with open(os.path.join(self.redis_json_backup, 'backup.json'), 'w') as f:
            data = {
                'yang-catalog:catalog': {
                    'modules': redis_modules,
                    'vendors': redis_vendors
                }
            }
            json.dump(data, f)

        self.job_log_messages.extend([
            {'label': 'Saved modules', 'message': len(redis_modules)},
            {'label': 'Saved vendors', 'message': len(redis_vendors.get('vendor', []))}
        ])

    def load_data_from_backup_to_db(self):
        if self.args.file:
            self.args.file = os.path.join(self.confd_backups, self.args.file)
        else:
            list_of_backups = get_list_of_backups(self.confd_backups)
            self.args.file = os.path.join(self.confd_backups, list_of_backups[-1])
        redis_modules = self.redis_connection.get_all_modules()
        yang_catalog_module = self.redis_connection.get_module(self.yang_catalog_module_name)
        if '{}' in (redis_modules, yang_catalog_module):
            self._populate_data_from_redis_json_backup_to_redis()
        self._load_data_from_backup_to_confd()

    def _populate_data_from_redis_json_backup_to_redis(self):
        # RDB not exists - load from JSON
        modules, vendors = self._load_data_from_redis_json_backup()
        if modules or vendors:
            self.redis_connection.populate_modules(modules)
            self.redis_connection.populate_implementation(vendors)
            self.redis_connection.reload_modules_cache()
            self.redis_connection.reload_vendors_cache()
            self.logger.info('All the modules data set to Redis successfully')
        self.job_log_messages.extend([
            {'label': 'Loaded modules', 'message': len(modules)},
            {'label': 'Loaded vendors', 'message': len(vendors)}
        ])

    def _load_data_from_redis_json_backup(self) -> tuple[list, list]:
        backup_path = os.path.join(self.redis_json_backup, 'backup.json')
        modules = []
        vendors = []
        if os.path.exists(backup_path):
            with open(backup_path, 'r') as file_load:
                catalog_data = json.load(file_load)
                modules = catalog_data.get('yang-catalog:catalog', {}).get('modules', [])
                vendors = catalog_data.get('yang-catalog:catalog', {}).get('vendors', {}).get('vendor', [])
        elif self.args.file.endswith('.gz'):
            with gzip.open(self.args.file, 'r') as file_load:
                self.logger.info(f'Loading file {file_load.name}')
                catalog_data = json.loads(file_load.read().decode())
                modules = catalog_data.get('yang-catalog:catalog', {}).get('modules', {}).get('module', [])
                vendors = catalog_data.get('yang-catalog:catalog', {}).get('vendors', {}).get('vendor', [])
        elif self.args.file.endswith('.json'):
            with open(self.args.file, 'r') as file_load:
                self.logger.info(f'Loading file {file_load.name}')
                catalog_data = json.load(file_load)
                modules = catalog_data.get('yang-catalog:catalog', {}).get('modules', {}).get('module', [])
                vendors = catalog_data.get('yang-catalog:catalog', {}).get('vendors', {}).get('vendor', [])
        else:
            self.logger.info('Unable to load modules - ending')
        return modules, vendors

    def _load_data_from_backup_to_confd(self):
        tries = 4
        try:
            response = self.confd_service.head_confd()
            self.logger.info(f'Status code for HEAD request {response.status_code} ')
            if response.status_code == 200:
                yang_catalog_module = self.redis_connection.get_module(self.yang_catalog_module_name)
                error = self.confd_service.patch_modules([json.loads(yang_catalog_module)])
                if error:
                    self.logger.error(f'Error occurred while patching {self.yang_catalog_module_name} module')
                else:
                    self.logger.info(f'{self.yang_catalog_module_name} patched successfully')
        except ConnectionError:
            if tries == 0:
                self.logger.exception('Unable to connect to ConfD for over 5 minutes')
            tries -= 1
            sleep(60)


def main(script_conf: BaseScriptConfig = ScriptConfig()):
    Recovery(script_conf).start_process()


if __name__ == '__main__':
    main()
