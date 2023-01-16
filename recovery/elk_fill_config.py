import os
import typing as t

from utility.scriptConfig import Arg

help = (
    'This script creates a dictionary of all the modules currently stored in the Redis database. '
    'The key is in <name>@<revision>/<organization> format and the value is the path to the .yang file. '
    'The entire dictionary is then stored in a JSON file - '
    'the content of this JSON file can then be used as an input for indexing modules into Elasticsearch.'
)
args: t.List[Arg] = [
    {
        'flag': '--config-path',
        'help': 'Set path to config file',
        'type': str,
        'default': os.environ['YANGCATALOG_CONFIG_PATH'],
    },
]
