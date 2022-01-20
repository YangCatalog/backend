# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Python script to start parsing all the yang files.
Based on the provided directory and boolean option
sdo (default False) this script will start to look
for xml files or it will start to parse all the yang
files in the directory ignoring all the vendor metadata
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import os
import time
import typing as t

import utility.log as log
from parseAndPopulate.capability import Capability
from parseAndPopulate.fileHasher import FileHasher
from parseAndPopulate.prepare import Prepare
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.util import find_files


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'Parse modules on given directory and generate json with module metadata that can be populated' \
               ' to ConfD/Redis database.'
        args: t.List[Arg] = [
            {
                'flag': '--dir',
                'help': 'Set dir where to look for hello message xml files or yang files if using "sdo" option',
                'type': str,
                'default': '/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC'
            },
            {
                'flag': '--save-file-hash',
                'help': 'if True then it will check if content of the file changed '
                        '(based on hash values) and it will skip parsing if nothing changed.',
                'action': 'store_true',
                'default': False
            },
            {
                'flag': '--api',
                'help': 'If request came from api',
                'action': 'store_true',
                'default': False
            },
            {
                'flag': '--sdo',
                'help': 'If we are processing sdo or vendor yang modules',
                'action': 'store_true',
                'default': False
            },
            {
                'flag': '--json-dir',
                'help': 'Directory where json files to populate ConfD/Redis will be stored',
                'type': str,
                'default': '/var/yang/tmp/'
            },
            {
                'flag': '--result-html-dir',
                'help': 'Set dir where to write html compilation result files',
                'type': str,
                'default': '/usr/share/nginx/html/results'
            },
            {
                'flag': '--save-file-dir',
                'help': 'Directory where the yang file will be saved',
                'type': str,
                'default': '/var/yang/all_modules'
            },
            {
                'flag': '--api-protocol',
                'help': 'Whether api runs on http or https. Default is set to https',
                'type': str,
                'default': 'https'
            },
            {
                'flag': '--api-port',
                'help': 'Set port where the api is started (This will be ignored if we are using uwsgi)',
                'type': int,
                'default': 8443
            },
            {
                'flag': '--api-ip',
                'help': 'Set ip address where the api is started. Default: yangcatalog.org',
                'type': str,
                'default': 'yangcatalog.org'
            },
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH']
            },
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args

    config_path = args.config_path
    config = create_config(config_path)
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    LOGGER = log.get_logger('runCapabilities',  '{}/parseAndPopulate.log'.format(log_directory))
    is_uwsgi = config.get('General-Section', 'uwsgi', fallback='True')
    private_dir = config.get('Web-Section', 'private-directory', fallback='tests/resources/html/private')
    yang_models = config.get('Directory-Section', 'yang-models-dir', fallback='tests/resources/yangmodels/yang')
    cache_dir = config.get('Directory-Section', 'cache', fallback='tests/resources/cache')

    separator = ':'
    suffix = args.api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(args.api_protocol, args.api_ip, separator, suffix)

    start = time.time()
    prepare = Prepare(log_directory, 'prepare', yangcatalog_api_prefix)
    fileHasher = FileHasher('backend_files_modification_hashes', cache_dir, args.save_file_hash, log_directory)

    LOGGER.info('Starting to iterate through files')
    if args.sdo:
        LOGGER.info('Found directory for sdo {}'.format(args.dir))

        # If yang-parameters.xml exists -> parsing IANA-maintained modules
        if os.path.isfile('{}/yang-parameters.xml'.format(args.dir)):
            LOGGER.info('yang-parameters.xml file found')

            xml_path = '{}/yang-parameters.xml'.format(args.dir)
            capability = Capability(log_directory, xml_path, prepare,
                                    None, args.api, args.sdo,
                                    args.json_dir, args.result_html_dir,
                                    args.save_file_dir, private_dir, yang_models, fileHasher)
            capability.parse_and_dump_iana()
        else:
            capability = Capability(log_directory, args.dir, prepare,
                                    None, args.api, args.sdo,
                                    args.json_dir, args.result_html_dir,
                                    args.save_file_dir, private_dir, yang_models, fileHasher)
            LOGGER.info('Starting to parse files in sdo directory')
            capability.parse_and_dump_sdo()

        prepare.dump_modules(args.json_dir)
    else:
        patterns = ['*ietf-yang-library*.xml', '*capabilit*.xml']
        for pattern in patterns:
            for root, basename in find_files(args.dir, pattern):
                filename = os.path.join(root, basename)
                LOGGER.info('Found xml source {}'.format(filename))

                capability = Capability(log_directory, filename,
                                        prepare,
                                        None, args.api,
                                        args.sdo, args.json_dir,
                                        args.result_html_dir,
                                        args.save_file_dir,
                                        private_dir,
                                        yang_models,
                                        fileHasher)
                if 'ietf-yang-library' in pattern:
                    capability.parse_and_dump_yang_lib()
                else:
                    try:
                        capability.parse_and_dump_vendor()
                    except Exception as e:
                        LOGGER.warning('Skipping {}, error while parsing:\n{}'.format(filename, e))
        prepare.dump_modules(args.json_dir)
        prepare.dump_vendors(args.json_dir)

    end = time.time()
    LOGGER.info('Time taken to parse all the files {} seconds'.format(int(end - start)))

    # Dump updated hashes into temporary directory
    if len(fileHasher.updated_hashes) > 0:
        fileHasher.dump_tmp_hashed_files_list(fileHasher.updated_hashes, args.json_dir)


if __name__ == '__main__':
    main()
