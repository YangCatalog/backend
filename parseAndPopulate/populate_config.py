import typing as t

from utility.create_config import create_config
from utility.scriptConfig import Arg

config = create_config()
credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
save_file_dir = config.get('Directory-Section', 'save-file-dir')
result_dir = config.get('Web-Section', 'result-html-dir')
help = (
    'Parse hello messages and YANG files to a JSON dictionary. These '
    'dictionaries are used for populating the yangcatalog. This script first '
    'runs the parse_directory.py script to create JSON files which are '
    'used to populate database.'
)
args: t.List[Arg] = [
    {
        'flag': '--credentials',
        'help': 'Set authorization parameters username and password respectively.',
        'type': str,
        'nargs': 2,
        'default': credentials,
    },
    {
        'flag': '--dir',
        'help': 'Set directory where to look for hello message xml files',
        'type': str,
        'default': '/var/yang/nonietf/yangmodels/yang/vendor/huawei/network-router/8.20.0/atn980b',
    },
    {'flag': '--api', 'help': 'If request came from api', 'action': 'store_true', 'default': False},
    {
        'flag': '--sdo',
        'help': 'If we are processing sdo or vendor yang modules',
        'action': 'store_true',
        'default': False,
    },
    {
        'flag': '--notify-indexing',
        'help': 'Whether to send files for indexing',
        'action': 'store_true',
        'default': False,
    },
    {
        'flag': '--result-html-dir',
        'help': f'Set dir where to write HTML compilation result files. Default: {result_dir}',
        'type': str,
        'default': result_dir,
    },
    {
        'flag': '--save-file-dir',
        'help': f'Directory where the yang file will be saved. Default: {save_file_dir}',
        'type': str,
        'default': save_file_dir,
    },
    {
        'flag': '--force-parsing',
        'help': 'Force parse files (do not skip parsing for unchanged files).',
        'action': 'store_true',
        'default': False,
    },
    {
        'flag': '--force-indexing',
        'help': 'Force indexing files (do not skip indexing for unchanged files).',
        'action': 'store_true',
        'default': False,
    },
    {
        'flag': '--simple',
        'help': 'Skip running time-consuming complicated resolvers.',
        'action': 'store_true',
        'default': False,
    },
]
