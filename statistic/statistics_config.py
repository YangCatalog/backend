import os
import typing as t

from utility.scriptConfig import Arg

help = (
    'Run the statistics on all yang modules populated in yangcatalog.org and from yangModels/yang '
    'repository and auto generate html page on yangcatalog.org/statistics.html. This runs as a daily '
    'cronjob'
)
args: t.List[Arg] = [
    {
        'flag': '--config-path',
        'help': 'Set path to config file',
        'type': str,
        'default': os.environ['YANGCATALOG_CONFIG_PATH'],
    },
]
