import os
import typing as t

from utility.scriptConfig import Arg

help = 'Process changed modules in a git repo'
args: t.List[Arg] = [
    {
        'flag': '--config-path',
        'help': 'Set path to config file',
        'type': str,
        'default': os.environ['YANGCATALOG_CONFIG_PATH'],
    },
]
