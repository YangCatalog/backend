import typing as t

from utility.scriptConfig import Arg

help = 'Count all YANG modules + related stats for a directory and its subdirectories'
args: t.List[Arg] = [
    {
        'flag': '--rootdir',
        'help': 'The root directory where to find the source YANG models. Default is "."',
        'type': str,
        'default': '.',
    },
    {
        'flag': '--excludedir',
        'help': 'The root directory from which to exclude YANG models. ' 'This directory should be under rootdir.',
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
]
