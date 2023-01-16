from utility.scriptConfig import Arg

help = ' Create or restore backups of our Elasticsearch database. '
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
