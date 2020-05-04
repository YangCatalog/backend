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
from dateutil.parser import parse
from requests import ConnectionError

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

if __name__ == "__main__":
    config_path = '/etc/yangcatalog/yangcatalog.conf'
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    credentials = config.get('General-Section', 'credentials').split()
    confd_protocol = config.get('General-Section', 'protocol')
    confd_port = config.get('General-Section', 'confd-port')
    confd_host = config.get('General-Section', 'confd-ip')
    log_directory = config.get('Directory-Section', 'logs')
    parser = argparse.ArgumentParser(
        description='This serves to save or load all information in yangcatalog.org to json in'
                    ' case the server will go down and we would lose all the information we'
                    ' have got. We have two options in here. Saving makes a GET request to '
                    'file with name that would be set as a argument or it will be set to '
                    'a current time and date. Load will read the file and make a PUT request '
                    'to write all data to yangcatalog.org.')
    parser.add_argument('--port', default=confd_port, type=int,
                        help='Set port where the confd is started. Default -> {}'.format(confd_port))
    parser.add_argument('--ip', default=confd_host, type=str,
                        help='Set ip address where the confd is started. Default -> {}'.format(confd_host))
    parser.add_argument('--name_save', default=str(datetime.datetime.utcnow()).split('.')[0].replace(' ', '_') + '-UTC',
                        type=str, help='Set name of the file to save. Default name is date and time in UTC')
    parser.add_argument('--name_load', type=str,
                        help='Set name of the file to load. Default will take a last saved file')
    parser.add_argument('--type', default='save', type=str, choices=['save', 'load'],
                        help='Set weather you want to save a file or load a file. Default is save')
    parser.add_argument('--protocol', type=str, default=confd_protocol, help='Whether confd-6.6 runs on http or https.'
                                                                             ' Default is set to {}'.format(confd_protocol))

    args = parser.parse_args()
    LOGGER = log.get_logger('recovery', log_directory + '/yang.log')
    cache_directory = config.get('Directory-Section', 'cache')
    prefix = args.protocol + '://{}:{}'.format(args.ip, args.port)
    LOGGER.info('Starting {} process of confd database'.format(args.type))

    tries = 4
    try:
        response = requests.head(prefix + '/restconf/data',
                                 auth=(credentials[0], credentials[1]))
        LOGGER.info("status code for hear request {} ".format(response.status_code))
    except ConnectionError as e:
        if tries == 0:
            LOGGER.error('unnable to connect to conf for over a {} minuts'.format(tries))
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
                    response = requests.patch(prefix + '/restconf/data/yang-catalog:catalog', json.dumps(body), headers={
                        'Authorization': 'Basic ' + base64string,
                        'Content-type': 'application/yang-data+json',
                        'Accept': 'application/yang-data+json'})
                    code = response.status_code
                    LOGGER.info('Confd recoverd with status code {}'.format(code))
                except:
                    counter -= 1
            else:
                failed = False
            if counter == 0:
                LOGGER.error('failed to load data')
                break

        file_load.close()

