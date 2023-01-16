import os
import typing as t

from utility.scriptConfig import Arg

help = 'Pull the latest IANA-maintained files and add them to the Github if there are any new.'
args: t.List[Arg] = [
    {
        'flag': '--config-path',
        'help': 'Set path to config file',
        'type': str,
        'default': os.environ['YANGCATALOG_CONFIG_PATH'],
    },
]
