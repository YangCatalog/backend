# Copyright The IETF Trust 2019, All Rights Reserved
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
This script will create json file to populate elasticsearch
from all the modules saved in confd database
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import json
import sys

import requests

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

if __name__ == "__main__":
    config_path = '/etc/yangcatalog/yangcatalog.conf'
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    api_protocol = config.get('General-Section', 'protocol-api')
    api_port = config.get('General-Section', 'api-port')
    api_host = config.get('DraftPullLocal-Section', 'api-ip')
    is_uwsgi = config.get('General-Section', 'uwsgi')
    parser = argparse.ArgumentParser(
        description='This serves to save or load all information in yangcatalog.org in elk.'
                    'in case the server will go down and we would lose all the information we'
                    ' have got. We have two options in here.')
    parser.add_argument('--api-ip', default=api_host, type=str,
                        help='Set host where the API is started. Default: ' + api_host)
    parser.add_argument('--api-port', default=api_port, type=int,
                        help='Set port where the API is started. Default: ' + api_port)
    parser.add_argument('--api-protocol', type=str, default=api_protocol, help='Whether API runs on http or https.'
                                                                               ' Default: ' + api_protocol)
    args = parser.parse_args()

    separator = ':'
    suffix = args.api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(args.api_protocol,
                                                   args.api_ip, separator,
                                                   suffix)
    all_modules = requests.get("{}search/modules".format(yangcatalog_api_prefix)).json()['module']
    create_dict = dict()
    for module in all_modules:
        name = module['name']
        org = module['organization']
        revision = module['revision']
        if name == '' or org == '' or revision == '':
            print('module: {} wrong data'.format(module))
            continue
        key = '{}@{}/{}'.format(name, revision, org)
        value = '/var/yang/all_modules/{}@{}.yang'.format(name, revision)
        create_dict[key] = value
    with open('elasticsearch_data.json', 'w') as f:
        json.dump(create_dict, f)
