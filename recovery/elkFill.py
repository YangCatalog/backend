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
This script will create json file to populate Elasticsearch
from all the modules saved in Redis database.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'


import json

import requests
from utility.create_config import create_config
from utility.scriptConfig import BaseScriptConfig


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        config = create_config()
        api_protocol = config.get('General-Section', 'protocol-api')
        api_port = config.get('Web-Section', 'api-port')
        api_host = config.get('Web-Section', 'ip')
        save_file_dir = config.get('Directory-Section', 'save-file-dir')
        temp = config.get('Directory-Section', 'temp')
        help = 'This serves to save or load all information in yangcatalog.org in elk.' \
               'in case the server will go down and we would lose all the information we' \
               ' have got. We have two options in here.'
        args = [
            {
                'flag': '--api-ip',
                'help':'Set host where the API is started. Default: {}'.format(api_host),
                'type': str,
                'default': api_host
            },
            {
                'flag': '--api-port',
                'help': 'Set port where the API is started. Default: {}'.format(api_port),
                'type': int,
                'default': api_port
            },
            {
                'flag': '--api-protocol',
                'help': 'Whether API runs on http or https. Default: {}'.format(api_protocol),
                'type': str,
                'default': api_protocol
            },
            {
                'flag': '--save-file-dir',
                'help': 'Directory for all yang modules lookup. Default: {}'.format(save_file_dir),
                'type': str,
                'default': save_file_dir
            },
            {
                'flag': '--temp',
                'help': 'Path to yangcatalog temporary directory. Default: {}'.format(temp),
                'type': str,
                'default': temp
            }
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])

        self.is_uwsgi = config.get('General-Section', 'uwsgi')


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
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(args.api_protocol, args.api_ip, separator, suffix)
    all_modules = requests.get('{}search/modules'.format(yangcatalog_api_prefix)).json()['module']
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
