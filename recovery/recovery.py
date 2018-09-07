"""
This script will save or load all the modules that
we currently have in our yangcatalog. This script
should be run every day so we always have backup of
all the modules
"""
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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import base64
import datetime
import glob
import json
import os
import sys
from collections import OrderedDict

import requests

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='This serves to save or load all information in yangcatalog.org to json in'
                    ' case the server will go down and we would lose all the information we'
                    ' have got. We have two options in here. Saving makes a GET request to '
                    'file with name that would be set as a argument or it will be set to '
                    'a current time and date. Load will read the file and make a PUT request '
                    'to write all data to yangcatalog.org.')
    parser.add_argument('--port', default=8008, type=int,
                        help='Set port where the confd is started. Default -> 8008')
    parser.add_argument('--ip', default='localhost', type=str,
                        help='Set ip address where the confd is started. Default -> localhost')
    parser.add_argument('--credentials', help='Set authorization parameters username password respectively.'
                                              ' Default parameters are admin admin', nargs=2, default=['admin', 'admin']
                        , type=str)
    parser.add_argument('--name_save', default=str(datetime.datetime.utcnow()).split('.')[0].replace(' ', '_') + '-UTC',
                        type=str, help='Set name of the file to save. Default name is date and time in UTC')
    parser.add_argument('--name_load', type=str,
                        help='Set name of the file to load. Default will take a last saved file')
    parser.add_argument('--type', default='save', type=str, choices=['save', 'load'],
                        help='Set weather you want to save a file or load a file. Default is save')
    parser.add_argument('--protocol', type=str, default='https', help='Whether confd-6.6 runs on http or https.'
                                                                     ' Default is set to https')
    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')

    args = parser.parse_args()
    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    cache_directory = config.get('Directory-Section', 'cache')
    prefix = args.protocol + '://{}:{}'.format(args.ip, args.port)
    if 'save' is args.type:
        file_save = open(cache_directory + args.name_save + '.json', 'w')
        jsn = requests.get(prefix + '/api/config/catalog?deep',
                           auth=(args.credentials[0], args.credentials[1]),
                           headers={
                               'Accept': 'application/vnd.yang.data+json',
                               'Content-type': 'application/vnd.yang.data+json'}).json()
        file_save.write(jsn)
        file_save.close()
    else:
        if args.name_load:
            file_load = open(cache_directory + '/' + args.name_load)
        else:
            list_of_files = glob.glob(cache_directory + '/*')
            latest_file = max(list_of_files, key=os.path.getctime)
            file_load = open(latest_file, 'rw')
        body = json.load(file_load, object_pairs_hook=OrderedDict)
        base64string = base64.b64encode('%s:%s' % (args.credentials[0], args.credentials[1]))
        response = requests.put(prefix + '/api/config/catalog', json.dumps(body), headers={
            'Authorization': 'Basic ' + base64string,
            'Content-type': 'application/vnd.yang.data+json',
            'Accept': 'application/vnd.yang.data+json'})
        file_load.close()
