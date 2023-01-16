import os
import typing as t

from utility.scriptConfig import Arg

help = (
    ' Pull the latest IETF files and add any new IETF draft files to GitHub. Remove old files and ensure all '
    'filenames have a <name>@<revision>.yang format. If there are new RFC files, produce an automated message '
    'that will be sent to the Cisco Webex Teams and admin emails notifying that these need to be added to the '
    'YangModels/yang GitHub repository manually. This script runs as a daily cronjob. '
)
args: t.List[Arg] = [
    {
        'flag': '--config-path',
        'help': 'Set path to config file',
        'type': str,
        'default': os.environ['YANGCATALOG_CONFIG_PATH'],
    },
    {
        'flag': '--send-message',
        'help': 'Whether to send a notification',
        'action': 'store_true',
        'default': False,
    },
]
