import typing as t

from utility.create_config import create_config
from utility.scriptConfig import Arg

config = create_config()
help = ''
args: t.List[Arg] = [
    {
        'flag': '--sdo',
        'help': 'If we are processing sdo or vendor yang modules',
        'action': 'store_true',
        'default': False,
    },
    {
        'flag': '--dir',
        'help': 'Set directory where to look for hello message xml files',
        'type': str,
        'default': '/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC',
    },
    {'flag': '--output', 'help': 'Output json file', 'type': str, 'default': 'integrity.json'},
]
yang_models = config.get('Directory-Section', 'yang-models-dir')
