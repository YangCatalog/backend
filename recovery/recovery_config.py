import typing as t
from datetime import datetime

from utility.scriptConfig import Arg
from utility.staticVariables import backup_date_format

help = (
    'Backup or restore all yangcatalog data. Redis .rdb files are prioritized. JSON dumps are used if .rdb '
    'files aren\'t present. Load additionally makes a PATCH request to write the yang-catalog@2018-04-03 module '
    'to ConfD. This script runs as a daily cronjob. '
)
mutually_exclusive_args: list[list[Arg]] = [
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
]
args: t.List[Arg] = [
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
]
