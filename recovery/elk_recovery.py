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
This script will save or load all the records saved in
Elasticsearch database snapshots.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import datetime
import sys
import typing as t

from elasticsearchIndexing.es_snapshots_manager import ESSnapshotsManager
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.staticVariables import backup_date_format


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'This serves to save or load all information in yangcatalog.org in elk.' \
               'in case the server will go down and we would lose all the information we' \
               ' have got. We have two options in here. This runs as a cronjob to create snapshot'
        args: t.List[Arg] = [
            {
                'flag': '--name_save',
                'help': 'Set name of the file to save. Default name is date and time in UTC',
                'type': str,
                'default': datetime.datetime.utcnow().strftime(backup_date_format).lower()
            },
            {
                'flag': '--name_load',
                'help': 'Set name of the file to load. Default will take a last saved file',
                'type': str,
                'default': ''
            },
            {
                'flag': '--save',
                'help': 'Set whether you want to create snapshot. Default is True',
                'action': 'store_true',
                'default': True
            },
            {
                'flag': '--load',
                'help': 'Set whether you want to load from snapshot. Default is False',
                'action': 'store_true',
                'default': False
            },
            {
                'flag': '--latest',
                'help': 'Set whether to load the latest snapshot',
                'action': 'store_true',
                'default': True
            },
            {
                'flag': '--compress',
                'help': 'Set whether to compress snapshot files. Default is True',
                'action': 'store_true',
                'default': True
            }
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args

    save = args.save
    if args.load:
        save = False

    es_snapshots_manager = ESSnapshotsManager()
    es_snapshots_manager.create_snapshot_repository(args.compress)

    if save:
        es_snapshots_manager.create_snapshot(args.name_save)
    else:
        if not args.latest:
            snapshot_name = args.name_load

        sorted_snapshots = es_snapshots_manager.get_sorted_snapshots()
        if not sorted_snapshots:
            print('There are no snapshots to restore')
            sys.exit(1)
        snapshot_name = sorted_snapshots[-1]['snapshot']
        restore_result = es_snapshots_manager.restore_snapshot(snapshot_name)
        print('Restore result:\n{}'.format(restore_result))


if __name__ == '__main__':
    main()
