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
This script will create JSON file which is used to
populate Elasticsearch from all the modules saved in Redis database.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'


import json
import os
import sys
import typing as t

import utility.log as log
from utility.create_config import create_config
from utility.fetch_modules import fetch_modules
from utility.scriptConfig import Arg, BaseScriptConfig


class ScriptConfig(BaseScriptConfig):
    def __init__(self):
        help = (
            'This script creates a dictionary of all the modules currently stored in the Redis database. '
            'The key is in <name>@<revision>/<organization> format and the value is the path to the .yang file. '
            'The entire dictionary is then stored in a JSON file - '
            'the content of this JSON file can then be used as an input for indexing modules into Elasticsearch.'
        )
        args: t.List[Arg] = [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])


def main(script_conf: BaseScriptConfig = ScriptConfig()):
    args = script_conf.args

    config = create_config(args.config_path)
    save_file_dir = config.get('Directory-Section', 'save-file-dir')
    temp = config.get('Directory-Section', 'temp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    logger = log.get_logger('sandbox', f'{log_directory}/sandbox.log')

    logger.info('Fetching all of the modules from API.')
    try:
        all_modules = fetch_modules(logger)
    except RuntimeError:
        logger.error('Failed to get list of modules from response')
        sys.exit(1)

    modules_dict = {}
    for module in all_modules:
        name = module['name']
        org = module['organization']
        revision = module['revision']
        if '' in [name, revision, org]:
            logger.warning(f'module: {module} wrong data')
            continue
        key = f'{name}@{revision}/{org}'
        value = f'{save_file_dir}/{name}@{revision}.yang'
        modules_dict[key] = value

    output_path = os.path.join(temp, 'elasticsearch_data.json')
    with open(output_path, 'w') as writer:
        json.dump(modules_dict, writer)

    logger.info(f'Dictionary of {len(modules_dict)} modules dumped into file')


if __name__ == '__main__':
    main()
