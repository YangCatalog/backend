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


class ScriptConfig:

    def __init__(self):
        config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(config_path)
        self.__api_protocol = config.get('General-Section', 'protocol-api')
        self.__api_port = config.get('Web-Section', 'api-port')
        self.__api_host = config.get('Web-Section', 'ip')
        self.__save_file_dir = config.get('Directory-Section', 'save-file-dir')
        self.__temp = config.get('Directory-Section', 'temp')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        self.help = 'This serves to save or load all information in yangcatalog.org in elk.' \
        'in case the server will go down and we would lose all the information we' \
        ' have got. We have two options in here.'

        parser = argparse.ArgumentParser(
            description=self.help)
        parser.add_argument('--api-ip', default=self.__api_host, type=str,
                            help='Set host where the API is started. Default: ' + self.__api_host)
        parser.add_argument('--api-port', default=self.__api_port, type=int,
                            help='Set port where the API is started. Default: ' + self.__api_port)
        parser.add_argument('--api-protocol', type=str, default=self.__api_protocol, help='Whether API runs on http or https.'
                                                                                ' Default: ' + self.__api_protocol)
        parser.add_argument('--save-file-dir', default=self.__save_file_dir, type=str,
                            help='Directory for all yang modules lookup. Default: ' + self.__save_file_dir)
        parser.add_argument('--temp', default=self.__temp, type=str,
                            help='Path to yangcatalog temporary directory. Default: ' + self.__temp)
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
        ret['options']['api_ip'] = 'Set host where the API is started. Default: ' + self.__api_host
        ret['options']['api_port'] = 'Set port where the API is started. Default: ' + self.__api_port
        ret['options']['api_protocol'] = 'Whether API runs on http or https. Default: ' + self.__api_protocol
        ret['options']['save_file_dir'] = 'Directory for all yang modules lookup. Default: ' + self.__save_file_dir
        ret['options']['temp'] = 'Path to yangcatalog temporary directory. Default: ' + self.__temp
        return ret


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    is_uwsgi = scriptConf.is_uwsgi

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
        value = '{}/{}@{}.yang'.format(args.save_file_dir, name, revision)
        create_dict[key] = value
    with open('{}/elasticsearch_data.json'.format(args.temp), 'w') as f:
        json.dump(create_dict, f)

if __name__ == "__main__":
    main()
