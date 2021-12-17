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

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'

import argparse
import datetime
import json
import os
import time

from redis import Redis

import utility.log as log
from utility.create_config import create_config
from utility.staticVariables import backup_date_format
from utility.util import get_list_of_backups, job_log

class ScriptConfig:

    def __init__(self):
        self.help = 'Save or load the users database stored on redis. An automatic backup is made' \
                    ' before a load is performed'
        config = create_config()
        self.log_directory = config.get('Directory-Section', 'logs')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.cache_directory = config.get('Directory-Section', 'cache')
        self.redis_host = config.get('DB-Section', 'redis-host')
        self.redis_port = config.get('DB-Section', 'redis-port')
        # self.var_yang = config.get('Directory-Section', 'var')
        parser = argparse.ArgumentParser(description=self.help)
        parser.add_argument('--name_save',
                            default=datetime.datetime.utcnow().strftime(backup_date_format),
                            type=str, help='Set name of the file to save. Default name is date and time in UTC')
        parser.add_argument('--name_load', type=str, default='',
                            help='Set name of the file to load. Default will take a last saved file')
        parser.add_argument('--type', default='save', type=str, choices=['save', 'load'],
                            help='Set whether you want to save a file or load a file. Default is save')

        self.args = parser.parse_args()
        self.defaults = [parser.get_default(key) for key in self.args.__dict__.keys()]

    def get_args_list(self):
        args_dict = {}
        keys = list(self.args.__dict__.keys())
        types = [type(value).__name__ for value in self.args.__dict__.values()]

        for i, key in enumerate(keys):
            args_dict[key] = dict(type=types[i], default=self.defaults[i])
        return args_dict

    def get_help(self):
        ret = {}
        ret['help'] = self.help
        ret['options'] = {}
        ret['options']['type'] = 'Set whether you want to save a file or load a file. Default is save'
        ret['options']['name_load'] = 'Set name of the file to load. Default will take a last saved file'
        ret['options']['name_save'] = 'Set name of the file to save. Default name is date and time in UTC'
        return ret


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    log_directory = scriptConf.log_directory
    cache_directory = scriptConf.cache_directory
    temp_dir = scriptConf.temp_dir
    redis_host = scriptConf.redis_host
    redis_port = scriptConf.redis_port
    args = scriptConf.args
    backups = os.path.join(cache_directory, 'redis-users')

    LOGGER = log.get_logger('recovery', os.path.join(log_directory, 'yang.log'))
    LOGGER.info('Starting {} process of redis users database'.format(args.type))


    if args.type == 'save':
        data = {}
        redis = Redis(host=redis_host, port=redis_port, db=2)
        cursor = 0
        while 1:
            cursor, keys = redis.scan(cursor)
            for key in keys:
                key_type = redis.type(key).decode()
                if key_type == 'string':
                    value = redis.get(key).decode()
                elif key_type == 'set':
                    value = [i.decode() for i in redis.smembers(key)]
                elif key_type == 'hash':
                    hash_table = redis.hgetall(key)
                    value = {hash_key.decode(): hash_table[hash_key].decode() for hash_key in hash_table}
                else:
                    print(key_type)
                    assert False
                data[key.decode()] = value
            if cursor == 0:
                break
        if not os.path.isdir(backups):
            os.mkdir(backups)
        args.name_save += '.json'
        with open(os.path.join(backups, args.name_save), 'w') as f:
            json.dump(data, f)
        LOGGER.info('Data saved to {} successfully'.format(args.name_save))
        filename = '{} - save'.format(os.path.basename(__file__).split('.py')[0])
        job_log(start_time, temp_dir, filename, status='Success')

    elif args.type == 'load':
        if args.name_load:
            file_name = '{}.json'.format(os.path.join(backups, args.name_load))
        else:
            list_of_backups = get_list_of_backups(backups)
            file_name = os.path.join(backups, list_of_backups[-1])

        with open(file_name) as f:
            data = json.load(f)

        redis = Redis(host=redis_host, port=redis_port, db=2)
        redis.flushdb()
        for key, value in data.items():
            if isinstance(value, str):
                redis.set(key, value)
            elif isinstance(value, list):
                redis.sadd(key, *value)
            elif isinstance(value, dict):
                redis.hset(key, mapping=value)
        
        LOGGER.info('Data loaded from {} successfully'.format(file_name))
    
    LOGGER.info('Job finished successfully')

if __name__ == '__main__':
    main()
