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
Save or load the users database stored on redis. An automatic backup is made
before a load is performed.
"""

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'

import datetime
import json
import os
from configparser import ConfigParser

from redis import Redis

import utility.log as log
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


class RedisUsersRecovery:
    def __init__(
        self,
        script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy(),
        config: ConfigParser = create_config(),
    ):
        self.start_time = None
        self.args = script_conf.args
        self.log_directory = config.get('Directory-Section', 'logs')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.cache_directory = config.get('Directory-Section', 'cache')
        self.redis_host = config.get('DB-Section', 'redis-host')
        self.redis_port = int(config.get('DB-Section', 'redis-port'))
        self.backups = os.path.join(self.cache_directory, 'redis-users')
        self.redis = Redis(host=self.redis_host, port=self.redis_port, db=2)
        self.logger = log.get_logger('recovery', os.path.join(self.log_directory, 'yang.log'))

    @job_log(file_basename=BASENAME)
    def start_process(self):
        process_type = 'save' if self.args.save else 'load'
        self.logger.info(f'Starting {process_type} process of redis users database')
        if self.args.save:
            self.backup_data_from_redis()
        elif self.args.load:
            self.load_data_from_backup_to_redis()
        self.logger.info(f'{process_type} process of redis users database finished successfully')

    def backup_data_from_redis(self):
        data = {}
        cursor = 0
        while True:
            cursor, keys = self.redis.scan(cursor)
            for key in keys:
                key_type = self.redis.type(key).decode()
                try:
                    if key_type == 'string':
                        value = value if (value := self.redis.get(key)) is None else value.decode()
                    elif key_type == 'set':
                        value = [member.decode() for member in self.redis.smembers(key)]
                    elif key_type == 'hash':
                        hash_table = self.redis.hgetall(key)
                        value = {hash_key.decode(): hash_table[hash_key].decode() for hash_key in hash_table}
                    else:
                        raise ValueError(f'Key of unknown type ({key_type}) was found while saving data from redis')
                except ValueError as e:
                    self.logger.exception(str(e))
                    raise e
                data[key.decode()] = value
            if cursor == 0:
                break
        os.makedirs(self.backups, exist_ok=True)
        self.args.file = self.args.file or datetime.datetime.utcnow().strftime(backup_date_format)
        self.args.file = f'{self.args.file}.json'
        with open(os.path.join(self.backups, self.args.file), 'w') as f:
            json.dump(data, f)
        self.logger.info(f'Data saved to {self.args.file} successfully')

    def load_data_from_backup_to_redis(self):
        if self.args.file:
            file_name = f'{os.path.join(self.backups, self.args.file)}.json'
        else:
            list_of_backups = get_list_of_backups(self.backups)
            file_name = os.path.join(self.backups, list_of_backups[-1])

        with open(file_name) as f:
            data = json.load(f)

        self.redis.flushdb()
        for key, value in data.items():
            if isinstance(value, str):
                self.redis.set(key, value)
            elif isinstance(value, list):
                self.redis.sadd(key, *value)
            elif isinstance(value, dict):
                self.redis.hset(key, mapping=value)

        self.logger.info(f'Data loaded from {file_name} successfully')


def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()):
    RedisUsersRecovery(script_conf=script_conf).start_process()


if __name__ == '__main__':
    main()
