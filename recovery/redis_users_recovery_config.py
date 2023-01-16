from utility.scriptConfig import Arg

help = 'Save or load the users database stored in redis. An automatic backup is made before a load is performed'
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
]
