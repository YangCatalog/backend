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
import glob
import json
import os
import sys
import time
from collections import OrderedDict
from time import sleep

import requests
import utility.log as log
from utility.util import job_log
from dateutil.parser import parse
from requests import ConnectionError

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


class ScriptConfig:

    def __init__(self):
        self.help = 'This serves to save or load all information in yangcatalog.org to json in' \
                    ' case the server will go down and we would lose all the information we' \
                    ' have got. We have two options in here. Saving makes a GET request to ' \
                    'file with name that would be set as a argument or it will be set to ' \
                    'a current time and date. Load will read the file and make a PUT request ' \
                    'to write all data to yangcatalog.org. This runs as a daily cronjob to save latest state of confd'
        config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(config_path)
        self.credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
        self.__confd_protocol = config.get('General-Section', 'protocol-confd')
        self.__confd_port = config.get('Web-Section', 'confd-port')
        self.__confd_host = config.get('Web-Section', 'confd-ip')
        self.log_directory = config.get('Directory-Section', 'logs')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.cache_directory = config.get('Directory-Section', 'cache')
        self.api_port = config.get('Web-Section', 'api-port')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        self.api_protocol = config.get('General-Section', 'protocol-api')
        self.api_host = config.get('Web-Section', 'ip')
        parser = argparse.ArgumentParser(
            description=self.help)
        parser.add_argument('--port', default=self.__confd_port, type=int,
                            help='Set port where the confd is started. Default -> {}'.format(self.__confd_port))
        parser.add_argument('--ip', default=self.__confd_host, type=str,
                            help='Set ip address where the confd is started. Default -> {}'.format(self.__confd_host))
        parser.add_argument('--name_save',
                            default=str(datetime.datetime.utcnow()).split('.')[0].replace(' ', '_') + '-UTC',
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
    api_port = scriptConf.api_port
    is_uwsgi = scriptConf.is_uwsgi
    api_protocol = scriptConf.api_protocol
    api_host = scriptConf.api_host

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
            LOGGER.error('Unable to connect to confd for over a {} minutes'.format(tries))
            e = 'Unable to connect to confd'
            job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
            raise e
        tries -= 1
        sleep(60)

    if 'save' == args.type:
        file_save = open(cache_directory + '/' + args.name_save + '.json', 'w')
        jsn = requests.get(prefix + '/restconf/data/yang-catalog:catalog',
                           auth=(credentials[0], credentials[1]),
                           headers={
                               'Accept': 'application/yang-data+json',
                               'Content-type': 'application/yang-data+json'}).json()
        file_save.write(json.dumps(jsn))
        file_save.close()
        LOGGER.info('Save completed successfully')
    else:
        if args.name_load:
            file_load = open(cache_directory + '/' + args.name_load, 'r')
        else:
            list_of_files = glob.glob(cache_directory + '/*')
            list_of_files = [i.split('/')[-1][:-5].replace('_', ' ')[:-4] for i in list_of_files]
            list_of_dates = []
            for f in list_of_files:
                try:
                    datetime_parsed = parse(f)
                    file_name = '{}/{}-UTC.json'.format(cache_directory, f.replace(' ', '_'))
                    if os.stat(file_name).st_size == 0:
                        continue
                    list_of_dates.append(datetime_parsed)
                except ValueError as e:
                    pass
            list_of_dates = sorted(list_of_dates)
            file_name = '{}/{}-UTC.json'.format(cache_directory, str(list_of_dates[-1]).replace(' ', '_'))
            file_load = open(file_name, 'r')
        LOGGER.info('Loading file {}'.format(file_load.name))
        body = json.load(file_load, object_pairs_hook=OrderedDict)
        str_to_encode = '%s:%s' % (credentials[0], credentials[1])
        if sys.version_info >= (3, 4):
            str_to_encode = str_to_encode.encode(encoding='utf-8', errors='strict')
        base64string = base64.b64encode(str_to_encode)
        if sys.version_info >= (3, 4):
            base64string = base64string.decode(encoding='utf-8', errors='strict')
        code = 500
        failed = True
        counter = 5
        while failed:
            if not str(code).startswith('2'):
                time.sleep(10)
                counter -= 1
                try:
                    catalog = body.get('yang-catalog:catalog')

                    modules_json = catalog['modules']['module']
                    x = -1
                    for x in range(0, int(len(modules_json) / 1000)):
                        LOGGER.info('{} out of {}'.format(x, int(len(modules_json) / 1000)))
                        json_modules_data = json.dumps({
                            'modules':
                                {
                                    'module': modules_json[x * 1000: (x * 1000) + 1000]
                                }
                        })

                        url = prefix + '/restconf/data/yang-catalog:catalog/modules/'
                        response = requests.patch(url, json_modules_data,
                                                  headers={
                                                      'Authorization': 'Basic ' + base64string,
                                                      'Accept': 'application/yang-data+json',
                                                      'Content-type': 'application/yang-data+json'})
                        if response.status_code < 200 or response.status_code > 299:
                            LOGGER.info('Request with body on path {} failed with {}'
                                        .format(url, response.text))
                    json_modules_data = json.dumps({
                        'modules':
                            {
                                'module': modules_json[(x * 1000) + 1000:]
                            }
                    })
                    url = prefix + '/restconf/data/yang-catalog:catalog/modules/'
                    response = requests.patch(url, json_modules_data,
                                              headers={
                                                  'Authorization': 'Basic ' + base64string,
                                                  'Accept': 'application/yang-data+json',
                                                  'Content-type': 'application/yang-data+json'})

                    if response.status_code < 200 or response.status_code > 299:
                        LOGGER.info('Request with body on path {} failed with {}'
                                    .format(url, response.text))

                    # In each json
                    LOGGER.info('Starting to add vendors')
                    x = -1
                    vendors = catalog['vendors']['vendor']
                    for v in vendors:
                        name = v['name']
                        for p in v['platforms']['platform']:
                            pname = p['name']
                            for s in p['software-versions']['software-version']:
                                LOGGER.info(
                                    '{} out of {}'.format(name, len(p['software-versions']['software-version'])))
                                json_implementations_data = json.dumps({
                                    'vendors':
                                        {
                                            'vendor': [{
                                                'name': name,
                                                'platforms': {
                                                    'platform': [{
                                                        'name': pname,
                                                        'software-versions': {
                                                            'software-version': [s]
                                                        }
                                                    }]
                                                }
                                            }]
                                        }
                                })

                                # Make a PATCH request to create a root for each file
                                url = prefix + '/restconf/data/yang-catalog:catalog/vendors/'
                                response = requests.patch(url, json_implementations_data,
                                                          headers={
                                                              'Authorization': 'Basic ' + base64string,
                                                              'Accept': 'application/yang-data+json',
                                                              'Content-type': 'application/yang-data+json'})
                                if response.status_code < 200 or response.status_code > 299:
                                    LOGGER.info('Request with body on path {} failed with {}'.
                                                format(url, response.text))
                    code = 200
                    LOGGER.info('Confd recoverd with status code 200')
                except:
                    counter -= 1
            else:
                failed = False
            if counter == 0:
                LOGGER.error('failed to load data')
                break

        file_load.close()
        separator = ':'
        suffix = api_port
        if is_uwsgi == 'True':
            separator = '/'
            suffix = 'api'
        yangcatalog_api_prefix = '{}://{}{}{}/'.format(api_protocol,
                                                       api_host.split('/')[-1], separator,
                                                       suffix)
        url = (yangcatalog_api_prefix + 'load-cache')

        response = requests.post(url, None, auth=(credentials[0], credentials[1]),
                                 headers={'Accept': 'application/json'})
        if response.status_code != 201:
            LOGGER.warning('Could not send a load-cache request. Status code {}. message {}'
                           .format(response.status_code, response.text))
        LOGGER.info('Cache reloaded')
    job_log(start_time, temp_dir, status='Success', filename=os.path.basename(__file__))
    LOGGER.info('Job finished successfully')


if __name__ == "__main__":
    main()
