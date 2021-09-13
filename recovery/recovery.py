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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import base64
import datetime
import json
import os
import sys
import time
from collections import OrderedDict
from time import sleep

import redis
import requests
import utility.log as log
from requests import ConnectionError
from utility.create_config import create_config
from utility.staticVariables import confd_headers, backup_date_format
from utility.util import job_log, get_list_of_backups


class ScriptConfig:

    def __init__(self):
        self.help = 'This serves to save or load all information in yangcatalog.org to json in' \
                    ' case the server will go down and we would lose all the information we' \
                    ' have got. We have two options in here. Saving makes a GET request to ' \
                    'file with name that would be set as a argument or it will be set to ' \
                    'a current time and date. Load will read the file and make a PUT request ' \
                    'to write all data to yangcatalog.org. This runs as a daily cronjob to save latest state of confd'
        config = create_config()
        self.credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
        self.__confd_protocol = config.get('General-Section', 'protocol-confd')
        self.__confd_port = config.get('Web-Section', 'confd-port')
        self.__confd_host = config.get('Web-Section', 'confd-ip')
        self.log_directory = config.get('Directory-Section', 'logs')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.cache_directory = config.get('Directory-Section', 'cache')
        self.redis_host = config.get('DB-Section', 'redis-host')
        self.redis_port = config.get('DB-Section', 'redis-port')
        parser = argparse.ArgumentParser(
            description=self.help)
        parser.add_argument('--port', default=self.__confd_port, type=int,
                            help='Set port where the confd is started. Default -> {}'.format(self.__confd_port))
        parser.add_argument('--ip', default=self.__confd_host, type=str,
                            help='Set ip address where the confd is started. Default -> {}'.format(self.__confd_host))
        parser.add_argument('--name_save',
                            default=datetime.datetime.utcnow().strftime(backup_date_format),
                            type=str, help='Set name of the file to save. Default name is date and time in UTC')
        parser.add_argument('--name_load', type=str, default='',
                            help='Set name of the file to load. Default will take a last saved file')
        parser.add_argument('--type', default='save', type=str, choices=['save', 'load'],
                            help='Set whether you want to save a file or load a file. Default is save')
        parser.add_argument('--protocol', type=str, default=self.__confd_protocol,
                            help='Whether confd runs on http or https.'
                                 ' Default is set to {}'.format(self.__confd_protocol))

        self.args, extra_args = parser.parse_known_args()
        self.defaults = [parser.get_default(key) for key in self.args.__dict__.keys()]

    def get_args_list(self):
        args_dict = {}
        keys = [key for key in self.args.__dict__.keys()]
        types = [type(value).__name__ for value in self.args.__dict__.values()]

        i = 0
        for key in keys:
            args_dict[key] = dict(type=types[i], default=self.defaults[i])
            i += 1
        return args_dict

    def get_help(self):
        ret = {}
        ret['help'] = self.help
        ret['options'] = {}
        ret['options']['port'] = 'Set port where the confd is started. Default -> {}'.format(self.__confd_port)
        ret['options']['type'] = 'Set whether you want to save a file or load a file. Default is save'
        ret['options']['name_load'] = 'Set name of the file to load. Default will take a last saved file'
        ret['options']['protocol'] = 'Whether confd runs on http or https. Default is set to {}'.format(
            self.__confd_protocol)
        ret['options']['name_save'] = 'Set name of the file to save. Default name is date and time in UTC'
        ret['options']['ip'] = 'Set ip address where the confd is started. Default -> {}'.format(self.__confd_host)
        return ret


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    cache_directory = scriptConf.cache_directory
    credentials = scriptConf.credentials
    log_directory = scriptConf.log_directory
    temp_dir = scriptConf.temp_dir
    redis_host = scriptConf.redis_host
    redis_port = scriptConf.redis_port

    confd_backups = os.path.join(cache_directory, 'confd')

    LOGGER = log.get_logger('recovery', log_directory + '/yang.log')
    prefix = args.protocol + '://{}:{}'.format(args.ip, args.port)
    LOGGER.info('Starting {} process of confd database'.format(args.type))

    tries = 4
    try:
        response = requests.head(prefix + '/restconf/data',
                                 auth=(credentials[0], credentials[1]))
        LOGGER.info('Status code for hear request {} '.format(response.status_code))
    except ConnectionError as e:
        if tries == 0:
            LOGGER.exception('Unable to connect to confd for over a {} minutes'.format(tries))
            e = 'Unable to connect to confd'
            filename='{} - save'.format(os.path.basename(__file__).split('.py')[0])
            job_log(start_time, temp_dir, error=str(e), status='Fail', filename=filename)
            raise e
        tries -= 1
        sleep(60)

    if 'save' == args.type:
        file_save = open(os.path.join(confd_backups, '{}.json'.format(args.name_save)), 'w')
        jsn = requests.get('{}/restconf/data/yang-catalog:catalog'.format(prefix),
                           auth=(credentials[0], credentials[1]),
                           headers=confd_headers).json()
        file_save.write(json.dumps(jsn))
        file_save.close()
        num_of_modules = 0 if not jsn['yang-catalog:catalog'].get('modules', {}).get('module') \
                            else len(jsn['yang-catalog:catalog'].get('modules').get('module'))
        num_of_vendors = 0 if not jsn['yang-catalog:catalog'].get('vendors', {}).get('vendor') \
                            else len(jsn['yang-catalog:catalog'].get('vendors').get('vendor'))
        messages = [
            {'label': 'Saved modules', 'message': num_of_modules},
            {'label': 'Saved vendors', 'message': num_of_vendors}
        ]
        LOGGER.info('Save completed successfully')
        filename='{} - save'.format(os.path.basename(__file__).split('.py')[0])
        job_log(start_time, temp_dir, messages=messages, status='Success', filename=filename)
    else:
        if args.name_load:
            file_load = open(os.path.join(confd_backups, args.name_load), 'r')
        else:
            list_of_backups = get_list_of_backups(confd_backups)
            file_name = os.path.join(confd_backups, ''.join(list_of_backups[-1]))
            file_load = open(file_name, 'r')
        LOGGER.info('Loading file {}'.format(file_load.name))
        catalog_data = json.load(file_load, object_pairs_hook=OrderedDict)
        str_to_encode = ':'.join(credentials)
        str_to_encode = str_to_encode.encode(encoding='utf-8', errors='strict')
        base64string = base64.b64encode(str_to_encode)
        base64string = base64string.decode(encoding='utf-8', errors='strict')
        counter = 5
        while True:
            if counter == 0:
                LOGGER.error('failed to load vendor data')
                break
            try:
                catalog = catalog_data.get('yang-catalog:catalog')

                modules_json = catalog['modules']['module']
                for x in range(0, len(modules_json), 1000):
                    LOGGER.info('{} out of {}'.format(x // 1000, len(modules_json) // 1000))
                    json_modules_data = json.dumps({
                        'modules':
                            {
                                'module': modules_json[x: x + 1000]
                            }
                    })

                    url = '{}/restconf/data/yang-catalog:catalog/modules/'.format(prefix)
                    response = requests.patch(url, json_modules_data,
                                                headers={
                                                    'Authorization': 'Basic {}'.format(base64string),
                                                    **confd_headers})
                    if response.status_code < 200 or response.status_code > 299:
                        LOGGER.info('Request with body on path {} failed with {}'
                                    .format(url, response.text))

                # In each json
                LOGGER.info('Starting to add vendors')
                vendors = catalog['vendors']['vendor']
                for vendor in vendors:
                    vendor_name = vendor['name']
                    for platform in vendor['platforms']['platform']:
                        platform_name = platform['name']
                        for software_version in platform['software-versions']['software-version']:
                            LOGGER.info(
                                '{} out of {}'.format(vendor_name,
                                                      len(platform['software-versions']['software-version'])))
                            json_implementations_data = json.dumps({
                                'vendors': {
                                    'vendor': [{
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
                                }
                            })

                            # Make a PATCH request to create a root for each file
                            url = '{}/restconf/data/yang-catalog:catalog/vendors/'.format(prefix)
                            response = requests.patch(url, json_implementations_data,
                                                        headers={
                                                            'Authorization': 'Basic {}'.format(base64string),
                                                            **confd_headers})
                            if response.status_code < 200 or response.status_code > 299:
                                LOGGER.info('Request with body on path {} failed with {}'
                                            .format(url, response.text))
                break
            except:
                LOGGER.warning('Failed to load data. Counter: {}'.format(counter))
                counter -= 1
                time.sleep(10)

        file_load.close()
        LOGGER.info('Cache reloaded to ConfD. Starting to load data into Redis.')

        # Init Redis and set values to empty dicts
        redis_cache = redis.Redis(
            host=redis_host,
            port=redis_port)
        redis_cache.set('modules-data', '{}')
        redis_cache.set('vendors-data', '{}')
        redis_cache.set('all-catalog-data', '{}')

        for module in modules_json:
            if module['name'] == 'yang-catalog' and module['revision'] == '2018-04-03':
                redis_cache.set('yang-catalog@2018-04-03/ietf', json.dumps(module))
                break
        LOGGER.debug('yang-catalog@2018-04-03/ietf module set')

        catalog_data_json = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(json.dumps(catalog_data))['yang-catalog:catalog']
        modules = catalog_data_json['modules']
        if catalog_data_json.get('vendors'):
            vendors = catalog_data_json['vendors']
        else:
            vendors = {}
        redis_cache.set('modules-data', json.dumps(modules))
        redis_cache.set('vendors-data', json.dumps(vendors))
        redis_cache.set('all-catalog-data', json.dumps(catalog_data))

        if len(modules) != 0:
            existing_keys = ['modules-data', 'vendors-data', 'all-catalog-data']
            # recreate keys to redis if there are any
            for i, mod in enumerate(modules['module']):
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

    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
