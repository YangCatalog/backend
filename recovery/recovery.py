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
This script will save or load all the modules that
we currently have in our yangcatalog. This script
should be run every day so we always have backup of
all the modules
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'


import datetime
import json
import logging
import os
import shutil
import time
import typing as t
from collections import OrderedDict
from time import sleep

import redis
import utility.log as log
from redisConnections.redisConnection import RedisConnection
from requests import ConnectionError
from utility.confdService import ConfdService
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.staticVariables import backup_date_format
from utility.util import get_list_of_backups, job_log


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'This serves to save or load all the information in yangcatalog.org to JSON file in' \
               ' case the server will go down and we would lose all the information we' \
               ' have got. We have two options in here. Saving makes a GET request to the ConfD' \
               ' and save modules to the file with name that would be passed as a argument or it will be set to' \
               ' the current datetime. Load will first load data to Redis either from saved JSON file or' \
               ' from snapshot of Redis. Then it will make PATCH request to write all the data to the ConfD.' \
               ' This runs as a daily cronjob to save latest state of ConfD and Redis.'
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
    confdService.patch_modules(modules)


def feed_confd_vendors(vendors_data: list, confdService: ConfdService, LOGGER: logging.Logger):
    # is there a reason for patching each software version separately?
    for vendor in vendors_data:
        vendor_name = vendor['name']
        for platform in vendor['platforms']['platform']:
            platform_name = platform['name']
            x = 1
            for software_version in platform['software-versions']['software-version']:
                LOGGER.info(
                    'Processing {} {} {} out of {}'.format(vendor_name, platform_name, x,
                                                           len(platform['software-versions']['software-version'])))
                x += 1
                vendors = [{
                    'name': vendor_name,
                    'platforms': {
                        'platform': [{
                            'name': platform_name,
                            'software-versions': {
                                'software-version': [software_version]
                            }
                        }]
                    }
                }]

                confdService.patch_vendors(vendors)


def feed_redis_from_json(redis_cache: redis.Redis, catalog_data: dict, LOGGER: logging.Logger):
    redis_cache.set('modules-data', '{}')
    redis_cache.set('vendors-data', '{}')

    for module in catalog_data['yang-catalog:catalog']['modules']['module']:
        if module['name'] == 'yang-catalog' and module['revision'] == '2018-04-03':
            redis_cache.set('yang-catalog@2018-04-03/ietf', json.dumps(module))
            break
    LOGGER.debug('yang-catalog@2018-04-03/ietf module set')

    catalog = catalog_data['yang-catalog:catalog']
    modules = catalog['modules']
    vendors = catalog.get('vendors', {})
    redis_cache.set('modules-data', json.dumps(modules))
    redis_cache.set('vendors-data', json.dumps(vendors))

    if len(modules) != 0:
        existing_keys = ['modules-data', 'vendors-data', 'all-catalog-data']
        # recreate keys to redis if there are any
        for mod in modules['module']:
            key = '{}@{}/{}'.format(mod['name'], mod['revision'], mod['organization'])
            existing_keys.append(key)
            value = json.dumps(mod)
            redis_cache.set(key, value)
        list_to_delete_keys_from_redis = []
        for key in redis_cache.scan_iter():
            if key.decode('utf-8') not in existing_keys:
                list_to_delete_keys_from_redis.append(key)
        if len(list_to_delete_keys_from_redis) != 0:
            redis_cache.delete(*list_to_delete_keys_from_redis)

    LOGGER.info('All the modules data set to Redis successfully')


def feed_confd_from_json(catalog_data: dict, confdService: ConfdService, LOGGER: logging.Logger):
    for counter in range(5, 0, -1):
        try:
            catalog = catalog_data.get('yang-catalog:catalog')

            LOGGER.info('Starting to add modules')
            feed_confd_modules(catalog['modules']['module'], confdService)

            LOGGER.info('Starting to add vendors')
            feed_confd_vendors(catalog['vendors']['vendor'], confdService, LOGGER)

            break
        except Exception:
            LOGGER.exception('Failed to load data. Counter: {}'.format(counter))
            time.sleep(10)
    else:
        LOGGER.error('Failed to load vendor data')

    LOGGER.info('Cache loaded to ConfD. Starting to load data into Redis.')


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    cache_directory = scriptConf.cache_directory
    log_directory = scriptConf.log_directory
    temp_dir = scriptConf.temp_dir
    redis_host = scriptConf.redis_host
    redis_port = scriptConf.redis_port
    var_yang = scriptConf.var_yang
    confdService = ConfdService()

    confd_backups = os.path.join(cache_directory, 'confd')
    redis_backups = os.path.join(cache_directory, 'redis')

    LOGGER = log.get_logger('recovery', os.path.join(log_directory, 'yang.log'))
    LOGGER.info('Starting {} process of ConfD database'.format(args.type))

    tries = 4
    try:
        response = confdService.head_confd()
        LOGGER.info('Status code for HEAD request {} '.format(response.status_code))
    except ConnectionError as e:
        if tries == 0:
            LOGGER.exception('Unable to connect to ConfD for over 5 minutes')
            e = Exception('Unable to connect to ConfD')
            filename = '{} - save'.format(os.path.basename(__file__).split('.py')[0])
            job_log(start_time, temp_dir, error=str(e), status='Fail', filename=filename)
            raise e
        tries -= 1
        sleep(60)

    if 'save' == args.type:
        # ConfD backup
        jsn = confdService.get_catalog_data().json()
        confd_backup_file = os.path.join(confd_backups, '{}.json'.format(args.name_save))
        with open(confd_backup_file, 'w') as file_save:
            json.dump(jsn, file_save)
        LOGGER.info('Data dumped into {}'.format(confd_backup_file))
        num_of_modules = len(jsn['yang-catalog:catalog'].get('modules', {}).get('module', []))
        num_of_vendors = len(jsn['yang-catalog:catalog'].get('vendors', {}).get('vendor', []))
        messages = [
            {'label': 'Saved modules', 'message': num_of_modules},
            {'label': 'Saved vendors', 'message': num_of_vendors}
        ]

        # Redis backup
        redis_backup_file = '{}/redis/dump.rdb'.format(var_yang)
        if os.path.exists(redis_backup_file):
            redis_copy_file = os.path.join(redis_backups, '{}.rdb'.format(args.name_save))
            shutil.copy2(redis_backup_file, redis_copy_file)
            LOGGER.info('Backup of Redis dump.rdb file created')
        else:
            LOGGER.warning('Redis dump.rdb file does not exists')
        LOGGER.info('Save completed successfully')
        filename = '{} - save'.format(os.path.basename(__file__).split('.py')[0])
        job_log(start_time, temp_dir, messages=messages, status='Success', filename=filename)
    else:
        if args.name_load:
            file_name = os.path.join(confd_backups, args.name_load)
        else:
            list_of_backups = get_list_of_backups(confd_backups)
            file_name = os.path.join(confd_backups, ''.join(list_of_backups[-1]))

        catalog_data = None
        response = confdService.head_catalog()
        if response.status_code != 200:
            # Fill ConfD from JSON file if empty
            with open(file_name, 'r') as file_load:
                LOGGER.info('Loading file {}'.format(file_load.name))
                catalog_data = json.load(file_load, object_pairs_hook=OrderedDict)

            LOGGER.info('Loading data into ConfD')
            catalog = catalog_data.get('yang-catalog:catalog')

            LOGGER.info('Starting to add modules')
            feed_confd_modules(catalog['modules']['module'], confdService)

            LOGGER.info('Starting to add vendors')
            feed_confd_vendors(catalog['vendors']['vendor'], confdService, LOGGER)

            LOGGER.info('Adding data to Redis db=0')
            redis_cache = redis.Redis(host=redis_host, port=redis_port)
            feed_redis_from_json(redis_cache, catalog_data, LOGGER)
        else:
            LOGGER.info('ConfD loaded from backup files')

        redisConnection = RedisConnection()
        redis_modules = redisConnection.get_all_modules()
        yang_catalog_module = redisConnection.get_module('yang-catalog@2018-04-03/ietf')

        if '{}' in (redis_modules, yang_catalog_module):
            # Feed Redis db=1 fron ConfD
            LOGGER.info('Loading data from ConfD into Redis')

            if not catalog_data:
                response = confdService.get_catalog_data()
                catalog_data = json.loads(response.text, object_pairs_hook=OrderedDict)
            modules = catalog_data['yang-catalog:catalog']['modules']['module']

            redisConnection.populate_modules(modules)
            redisConnection.reload_modules_cache()
        else:
            LOGGER.info('Redis loaded from backup file')

    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
