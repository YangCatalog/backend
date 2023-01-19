# Copyright The IETF Trust 2023, All Rights Reserved
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

__author__ = 'Dmytro Kyrychenko'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'dmytro.kyrychenko@pantheon.tech'

import os
import typing as t
from datetime import datetime

from utility.create_config import create_config
from utility.scriptConfig import Arg
from utility.staticVariables import backup_date_format


class BaseScriptConfigInfo(t.TypedDict):
    help: str


class ScriptConfigInfo(BaseScriptConfigInfo, total=False):
    args: t.Optional[list[Arg]]
    mutually_exclusive_args: t.Optional[list[list[Arg]]]


config = create_config()
credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
save_file_dir = config.get('Directory-Section', 'save-file-dir')
result_dir = config.get('Web-Section', 'result-html-dir')

script_config_dict: dict[str, ScriptConfigInfo] = {
    'process_changed_mods': {
        'help': 'Process changed modules in a git repo',
        'args': [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
        ],
    },
    'draftPull': {
        'help': (
            ' Pull the latest IETF files and add any new IETF draft files to GitHub. Remove old files and ensure all '
            'filenames have a <name>@<revision>.yang format. If there are new RFC files, produce an automated message '
            'that will be sent to the Cisco Webex Teams and admin emails notifying that these need to be added to the '
            'YangModels/yang GitHub repository manually. This script runs as a daily cronjob. '
        ),
        'args': [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
            {
                'flag': '--send-message',
                'help': 'Whether to send a notification',
                'action': 'store_true',
                'default': False,
            },
        ],
    },
    'draftPullLocal': {
        'help': (
            'Run populate script on all ietf RFC and DRAFT files to parse all ietf modules and populate the '
            'metadata to yangcatalog if there are any new. This runs as a daily cronjob'
        ),
        'args': [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
        ],
    },
    'ianaPull': {
        'help': 'Pull the latest IANA-maintained files and add them to the Github if there are any new.',
        'args': [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
        ],
    },
    'openconfigPullLocal': {
        'help': (
            'Run populate script on all openconfig files to parse all modules and populate the'
            ' metadata to yangcatalog if there are any new. This runs as a daily cronjob'
        ),
        'args': [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
        ],
    },
    'integrity': {
        'help': '',
        'args': [
            {
                'flag': '--sdo',
                'help': 'If we are processing sdo or vendor yang modules',
                'action': 'store_true',
                'default': False,
            },
            {
                'flag': '--dir',
                'help': 'Set directory where to look for hello message xml files',
                'type': str,
                'default': '/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC',
            },
            {'flag': '--output', 'help': 'Output json file', 'type': str, 'default': 'integrity.json'},
        ],
    },
    'parse_directory': {
        'help': (
            'Parse modules on given directory and generate json with module metadata '
            'that can be populated to Redis database.'
        ),
        'args': [
            {
                'flag': '--dir',
                'help': 'Set dir where to look for hello message xml files or yang files if using "sdo" option',
                'type': str,
                'default': '/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC',
            },
            {
                'flag': '--save-file-hash',
                'help': 'if True then it will check if content of the file changed '
                '(based on hash values) and it will skip parsing if nothing changed.',
                'action': 'store_true',
                'default': False,
            },
            {'flag': '--api', 'help': 'If request came from api', 'action': 'store_true', 'default': False},
            {
                'flag': '--sdo',
                'help': 'If we are processing sdo or vendor yang modules',
                'action': 'store_true',
                'default': False,
            },
            {
                'flag': '--json-dir',
                'help': 'Directory where json files to populate Redis will be stored',
                'type': str,
                'default': '/var/yang/tmp/',
            },
            {
                'flag': '--result-html-dir',
                'help': 'Set dir where to write html compilation result files',
                'type': str,
                'default': '/usr/share/nginx/html/results',
            },
            {
                'flag': '--save-file-dir',
                'help': 'Directory where the yang file will be saved',
                'type': str,
                'default': '/var/yang/all_modules',
            },
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
        ],
    },
    'populate': {
        'help': (
            'Parse hello messages and YANG files to a JSON dictionary. These '
            'dictionaries are used for populating the yangcatalog. This script first '
            'runs the parse_directory.py script to create JSON files which are '
            'used to populate database.'
        ),
        'args': [
            {
                'flag': '--credentials',
                'help': 'Set authorization parameters username and password respectively.',
                'type': str,
                'nargs': 2,
                'default': credentials,
            },
            {
                'flag': '--dir',
                'help': 'Set directory where to look for hello message xml files',
                'type': str,
                'default': '/var/yang/nonietf/yangmodels/yang/vendor/huawei/network-router/8.20.0/atn980b',
            },
            {'flag': '--api', 'help': 'If request came from api', 'action': 'store_true', 'default': False},
            {
                'flag': '--sdo',
                'help': 'If we are processing sdo or vendor yang modules',
                'action': 'store_true',
                'default': False,
            },
            {
                'flag': '--notify-indexing',
                'help': 'Whether to send files for indexing',
                'action': 'store_true',
                'default': False,
            },
            {
                'flag': '--result-html-dir',
                'help': f'Set dir where to write HTML compilation result files. Default: {result_dir}',
                'type': str,
                'default': result_dir,
            },
            {
                'flag': '--save-file-dir',
                'help': f'Directory where the yang file will be saved. Default: {save_file_dir}',
                'type': str,
                'default': save_file_dir,
            },
            {
                'flag': '--force-parsing',
                'help': 'Force parse files (do not skip parsing for unchanged files).',
                'action': 'store_true',
                'default': False,
            },
            {
                'flag': '--force-indexing',
                'help': 'Force indexing files (do not skip indexing for unchanged files).',
                'action': 'store_true',
                'default': False,
            },
            {
                'flag': '--simple',
                'help': 'Skip running time-consuming complicated resolvers.',
                'action': 'store_true',
                'default': False,
            },
        ],
    },
    'resolve_expiration': {
        'help': (
            'Resolve expiration metadata for each module and set it to Redis if changed. '
            'This runs as a daily cronjob'
        ),
    },
    'reviseSemver': {
        'help': (
            'Parse modules on given directory and generate json with module metadata that can be populated'
            ' to confd directory'
        ),
    },
    'elk_fill': {
        'help': (
            'This script creates a dictionary of all the modules currently stored in the Redis database. '
            'The key is in <name>@<revision>/<organization> format and the value is the path to the .yang file. '
            'The entire dictionary is then stored in a JSON file - '
            'the content of this JSON file can then be used as an input for indexing modules into Elasticsearch.'
        ),
        'args': [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
        ],
    },
    'elk_recovery': {
        'help': ' Create or restore backups of our Elasticsearch database. ',
        'mutually_exclusive_args': [
            [
                {
                    'flag': '--save',
                    'help': 'Set whether you want to create snapshot.',
                    'action': 'store_true',
                    'default': False,
                },
                {
                    'flag': '--load',
                    'help': 'Set whether you want to load from snapshot.',
                    'action': 'store_true',
                    'default': False,
                },
            ],
        ],
        'args': [
            {
                'flag': '--file',
                'help': (
                    'Set name of the file to save data to/load data from. Default name is empty. '
                    'If name is empty: load operation will use the last backup file, '
                    'save operation will use date and time in UTC.'
                ),
                'type': str,
                'default': '',
            },
            {
                'flag': '--compress',
                'help': 'Set whether to compress snapshot files. Default is True',
                'action': 'store_true',
                'default': True,
            },
        ],
    },
    'recovery': {
        'help': (
            'Backup or restore all yangcatalog data. Redis .rdb files are prioritized. JSON dumps are used if .rdb '
            'files aren\'t present. Load additionally makes a PATCH request to write the yang-catalog@2018-04-03 module'
            ' to ConfD. This script runs as a daily cronjob. '
        ),
        'mutually_exclusive_args': [
            [
                {
                    'flag': '--save',
                    'help': 'Set true if you want to backup data',
                    'action': 'store_true',
                    'default': False,
                },
                {
                    'flag': '--load',
                    'help': 'Set true if you want to load data from backup to the database',
                    'action': 'store_true',
                    'default': False,
                },
            ],
        ],
        'args': [
            {
                'flag': '--file',
                'help': (
                    'Set name of the file (without file format) to save data to/load data from. Default name is empty. '
                    'If name is empty: load operation will use the last available json backup file, '
                    'save operation will use date and time in UTC.'
                ),
                'type': str,
                'default': '',
            },
            {
                'flag': '--rdb_file',
                'help': (
                    'Set name of the file to save data from redis database rdb file to. '
                    'Default name is current UTC datetime.'
                ),
                'type': str,
                'default': datetime.utcnow().strftime(backup_date_format),
            },
        ],
    },
    'redis_users_recovery': {
        'help': 'Save or load the users database stored in redis. An autobackup is made before a load is performed',
        'mutually_exclusive_args': [
            [
                {
                    'flag': '--save',
                    'help': 'Set true if you want to backup data',
                    'action': 'store_true',
                    'default': False,
                },
                {
                    'flag': '--load',
                    'help': 'Set true if you want to load data from backup to the database',
                    'action': 'store_true',
                    'default': False,
                },
            ],
        ],
        'args': [
            {
                'flag': '--file',
                'help': (
                    'Set name of the file to save data to/load data from. Default name is empty. '
                    'If name is empty: load operation will use the last backup file, '
                    'save operation will use date and time in UTC.'
                ),
                'type': str,
                'default': '',
            },
        ],
    },
    'runYANGallstats': {
        'help': 'Count all YANG modules + related stats for a directory and its subdirectories',
        'args': [
            {
                'flag': '--rootdir',
                'help': 'The root directory where to find the source YANG models. Default is "."',
                'type': str,
                'default': '.',
            },
            {
                'flag': '--excludedir',
                'help': 'The root directory from which to exclude YANG models. '
                'This directory should be under rootdir.',
                'type': str,
                'default': '',
            },
            {
                'flag': '--excludekeyword',
                'help': 'Exclude some keywords from the YANG module name.',
                'type': str,
                'default': '',
            },
            {
                'flag': '--removedup',
                'help': 'Remove duplicate YANG module. Default is False.',
                'type': bool,
                'default': False,
            },
            {'flag': '--debug', 'help': 'Debug level; the default is 0', 'type': int, 'default': 0},
        ],
    },
    'statistics': {
        'help': (
            'Run the statistics on all yang modules populated in yangcatalog.org and from yangModels/yang '
            'repository and auto generate html page on yangcatalog.org/statistics.html. This runs as a daily '
            'cronjob'
        ),
        'args': [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
        ],
    },
    'revise_tree_type': {
        'help': 'Resolve the tree-type for modules that are no longer the latest revision. Runs as a daily cronjob.',
    },
}
