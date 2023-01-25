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


import gzip
import json
import os
from argparse import Namespace
from configparser import ConfigParser
from datetime import datetime

import utility.log as log
from redisConnections.redisConnection import RedisConnection
from utility.create_config import create_config
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.staticVariables import backup_date_format
from utility.util import get_list_of_backups, job_log

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME]['args'],
    arglist=None if __name__ == '__main__' else [],
    mutually_exclusive_args=script_config_dict[FILENAME]['mutually_exclusive_args'],
)


class Recovery:
    def __init__(
        self,
        args: Namespace,
        config: ConfigParser = create_config(),
        redis_connection: RedisConnection = RedisConnection(),
    ):
        self.job_log_messages = []
        self.yang_catalog_module_name = 'yang-catalog@2018-04-03/ietf'
        self.process_type = ''

        self.args = args
        self.log_directory = config.get('Directory-Section', 'logs')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.cache_directory = config.get('Directory-Section', 'cache')
        self.redis_host = config.get('DB-Section', 'redis-host')
        self.redis_port = config.get('DB-Section', 'redis-port')
        self.var_yang = config.get('Directory-Section', 'var')

        self.redis_connection = redis_connection
        self.redis_backups = os.path.join(self.cache_directory, 'redis')
        self.redis_json_backup = os.path.join(self.cache_directory, 'redis-json')
        self.logger = log.get_logger('recovery', os.path.join(self.log_directory, 'yang.log'))

    @job_log(file_basename=BASENAME)
    def start_process(self):
        self.logger.info(f'Starting {self.process_type} process of Redis database')
        self._start_process()
        self.logger.info(f'{self.process_type} process of Redis database finished successfully')
        return self.job_log_messages

    def _start_process(self):
        """Main logic of the script"""
        raise NotImplementedError


class BackupDatabaseData(Recovery):
    def __init__(self, args: Namespace, config: ConfigParser = create_config()):
        super().__init__(args, config)
        self.job_log_filename = 'recovery - save'
        self.process_type = 'save'

    def _start_process(self):
        self.args.file = self.args.file or datetime.utcnow().strftime(backup_date_format)
        os.makedirs(self.redis_backups, exist_ok=True)
        self._backup_redis_rdb_file()
        self._backup_redis_modules()
        self.logger.info('Save completed successfully')

    def _backup_redis_rdb_file(self):
        # Redis dump.rdb file backup
        redis_rdb_file = os.path.join(self.var_yang, 'redis', 'dump.rdb')
        if os.path.exists(redis_rdb_file):
            redis_copy_file = os.path.join(self.redis_backups, f'{self.args.rdb_file}.rdb.gz')
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
        redis_modules = list(redis_modules_dict.values())
        redis_vendors = json.loads(redis_vendors_raw)

        os.makedirs(self.redis_json_backup, exist_ok=True)
        with open(os.path.join(self.redis_json_backup, f'{self.args.file}.json'), 'w') as f:
            data = {'yang-catalog:catalog': {'modules': redis_modules, 'vendors': redis_vendors}}
            json.dump(data, f)

        self.job_log_messages.extend(
            [
                {'label': 'Saved modules', 'message': len(redis_modules)},
                {'label': 'Saved vendors', 'message': len(redis_vendors.get('vendor', []))},
            ],
        )


class LoadDataFromBackupToDatabase(Recovery):
    def __init__(self, args: Namespace, config: ConfigParser = create_config()):
        super().__init__(args, config)
        self.process_type = 'load'

    def _start_process(self):
        if self.args.file:
            self.args.file = os.path.join(self.redis_json_backup, f'{self.args.file}.json')
        else:
            list_of_backups = get_list_of_backups(self.redis_json_backup)
            if not list_of_backups:
                error_message = 'Didn\'t find any backups, finishing execution of the script'
                self.logger.error(error_message)
                raise RuntimeError(error_message)
            self.args.file = os.path.join(self.redis_json_backup, list_of_backups[-1])
        redis_modules = self.redis_connection.get_all_modules()
        yang_catalog_module = self.redis_connection.get_module(self.yang_catalog_module_name)
        if '{}' in (redis_modules, yang_catalog_module):
            self._populate_data_from_redis_backup_to_redis()

    def _populate_data_from_redis_backup_to_redis(self):
        # RDB not exists - load from JSON
        modules, vendors = self._load_data_from_redis_backup()
        if modules or vendors:
            self.redis_connection.populate_modules(modules)
            self.redis_connection.populate_implementation(vendors)
            self.redis_connection.reload_modules_cache()
            self.redis_connection.reload_vendors_cache()
            self.logger.info('All the modules data set to Redis successfully')
        self.job_log_messages.extend(
            [
                {'label': 'Loaded modules', 'message': len(modules)},
                {'label': 'Loaded vendors', 'message': len(vendors)},
            ],
        )

    def _load_data_from_redis_backup(self) -> tuple[list, list]:
        modules = []
        vendors = []
        if self.args.file.endswith('.json'):
            with open(self.args.file, 'r') as file_load:
                self.logger.info(f'Loading file {file_load.name}')
                catalog_data = json.load(file_load)
                modules = catalog_data.get('yang-catalog:catalog', {}).get('modules', [])
                vendors = catalog_data.get('yang-catalog:catalog', {}).get('vendors', [])
        else:
            self.logger.info('Unable to load modules - ending')
        return modules, vendors


def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy(), config: ConfigParser = create_config()):
    args = script_conf.args
    if args.save:
        BackupDatabaseData(args, config).start_process()
    elif args.load:
        LoadDataFromBackupToDatabase(args, config).start_process()


if __name__ == '__main__':
    main()
