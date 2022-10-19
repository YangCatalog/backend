# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2019 Cisco and its affiliates
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
Create or restore backups of our Elasticsearch database.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import datetime
import sys

from elasticsearchIndexing.es_snapshots_manager import ESSnapshotsManager
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.staticVariables import backup_date_format


class ScriptConfig(BaseScriptConfig):
    def __init__(self):
        help = __doc__
        mutually_exclusive_args: list[list[Arg]] = [
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
        ]
        args: list[Arg] = [
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
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [], mutually_exclusive_args)


def main(script_conf: BaseScriptConfig = ScriptConfig()):
    args = script_conf.args

    es_snapshots_manager = ESSnapshotsManager()
    es_snapshots_manager.create_snapshot_repository(args.compress)

    if args.save:
        args.file = args.file or datetime.datetime.utcnow().strftime(backup_date_format)
        es_snapshots_manager.create_snapshot(args.file)
    elif args.load:
        if args.file:
            snapshot_name = args.file
        else:
            sorted_snapshots = es_snapshots_manager.get_sorted_snapshots()
            if not sorted_snapshots:
                print('There are no snapshots to restore')
                sys.exit(1)
            snapshot_name = sorted_snapshots[-1]['snapshot']
        restore_result = es_snapshots_manager.restore_snapshot(snapshot_name)
        print(f'Restore result:\n{restore_result}')


if __name__ == '__main__':
    main()
