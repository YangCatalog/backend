import os
import typing as t

from utility.scriptConfig import Arg

help = (
    'Run populate script on all ietf RFC and DRAFT files to parse all ietf modules and populate the '
    'metadata to yangcatalog if there are any new. This runs as a daily cronjob'
)
args: t.List[Arg] = [
    {
        'flag': '--config-path',
        'help': 'Set path to config file',
        'type': str,
        'default': os.environ['YANGCATALOG_CONFIG_PATH'],
    },
]
