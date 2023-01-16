import os
import typing as t

from utility.scriptConfig import Arg

help = (
    'Parse modules on given directory and generate json with module metadata '
    'that can be populated to Redis database.'
)
args: t.List[Arg] = [
    {
        'flag': '--dir',
        'help': 'Set dir where to look for hello message xml files or yang files if using "sdo" option',
        'type': str,
        'default': '/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC',
    },
    {
        'flag': '--save-file-hash',
        'help': 'if True then it will check if content of the file changed '
        '(based on hash values) and it will skip parsing if nothing changed.',
        'action': 'store_true',
        'default': False,
    },
    {'flag': '--api', 'help': 'If request came from api', 'action': 'store_true', 'default': False},
    {
        'flag': '--sdo',
        'help': 'If we are processing sdo or vendor yang modules',
        'action': 'store_true',
        'default': False,
    },
    {
        'flag': '--json-dir',
        'help': 'Directory where json files to populate Redis will be stored',
        'type': str,
        'default': '/var/yang/tmp/',
    },
    {
        'flag': '--result-html-dir',
        'help': 'Set dir where to write html compilation result files',
        'type': str,
        'default': '/usr/share/nginx/html/results',
    },
    {
        'flag': '--save-file-dir',
        'help': 'Directory where the yang file will be saved',
        'type': str,
        'default': '/var/yang/all_modules',
    },
    {
        'flag': '--config-path',
        'help': 'Set path to config file',
        'type': str,
        'default': os.environ['YANGCATALOG_CONFIG_PATH'],
    },
]
