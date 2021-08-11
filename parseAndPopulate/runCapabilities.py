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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import fnmatch
import json
import os
import sys
import time

import utility.log as log
from utility.util import create_config

from parseAndPopulate import integrity
from parseAndPopulate.capability import Capability
from parseAndPopulate.fileHasher import FileHasher
from parseAndPopulate.prepare import Prepare


class ScriptConfig:
    def __init__(self):
        self.help = 'Parse modules on given directory and generate json with module metadata that can be populated' \
                    ' to confd directory'
        parser = argparse.ArgumentParser()
        parser.add_argument('--dir', default='/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC', type=str,
                            help='Set dir where to look for hello message xml files or yang files if using "sdo" option')
        parser.add_argument('--save-file-hash', action='store_true', default=False,
                            help='if True then it will check if content of the file changed '
                            '(based on hash values) and it will skip parsing if nothing changed.')
        parser.add_argument('--api', action='store_true', default=False, help='If request came from api')
        parser.add_argument('--sdo', action='store_true', default=False,
                            help='If we are processing sdo or vendor yang modules')
        parser.add_argument('--json-dir', default='/var/yang/tmp/', type=str,
                            help='Directory where json files to populate confd will be stored')
        parser.add_argument('--result-html-dir', default='/usr/share/nginx/html/results', type=str,
                            help='Set dir where to write html compilation result files')
        parser.add_argument('--save-file-dir', default='/var/yang/all_modules',
                            type=str, help='Directory where the yang file will be saved')
        parser.add_argument('--api-protocol', type=str, default='https',
                            help='Whether api runs on http or https. Default is set to https')
        parser.add_argument('--api-port', default=8443, type=int,
                            help='Set port where the api is started (This will be ignored if we are using uwsgi)')
        parser.add_argument('--api-ip', default='yangcatalog.org', type=str,
                            help='Set ip address where the api is started. Default -> yangcatalog.org')
        parser.add_argument('--config-path', type=str,
                            default=os.environ['YANGCATALOG_CONFIG_PATH'],
                            help='Set path to config file')

        self.args, extra_args = parser.parse_known_args()
        self.defaults = [parser.get_default(key) for key in self.args.__dict__.keys()]

    def get_args_list(self):
        """ Return a list of the arguments of the script, along with the default values.
        """
        args_dict = {}
        keys = [key for key in self.args.__dict__.keys()]
        types = [type(value).__name__ for value in self.args.__dict__.values()]

        i = 0
        for key in keys:
            args_dict[key] = dict(type=types[i], default=self.defaults[i])
            i += 1
        return args_dict

    def get_help(self):
        """ Return script help along with help for each argument.
        """
        ret = {}
        ret['help'] = self.help
        ret['options'] = {}
        ret['options']['dir'] = 'Set dir where to look for hello message xml files or yang files if using "sdo" option'
        ret['options']['save_file_hash'] = 'if True then it will check if content of the file changed' \
            ' (based on hash values) and it will skip parsing if nothing changed.'
        ret['options']['api'] = 'If request came from api'
        ret['options']['sdo'] = 'If we are processing sdo or vendor yang modules'
        ret['options']['json_dir'] = 'Directory where json files to populate confd will be stored'
        ret['options']['result_html_dir'] = 'Set dir where to write html compilation result files'
        ret['options']['save_file_dir'] = 'Directory where the yang file will be saved'
        ret['options']['api_protocol'] = 'Whether api runs on http or https. Default is set to https'
        ret['options']['api_port'] = 'Set port where the api is started (This will be ignored if we are using uwsgi)'
        ret['options']['api_ip'] = 'Set ip address where the api is started. Default -> yangcatalog.org'
        ret['options']['config_path'] = 'Set path to config file'
        return ret


def find_files(directory: str, pattern: str):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename


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
            for filename in find_files(args.dir, pattern):
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
                    capability.parse_and_dump_vendor()
        prepare.dump_modules(args.json_dir)
        prepare.dump_vendors(args.json_dir)

    end = time.time()
    LOGGER.info('Time taken to parse all the files {} seconds'.format(int(end - start)))

    # Dump updated hashes into temporary directory
    if len(fileHasher.updated_hashes) > 0:
        fileHasher.dump_tmp_hashed_files_list(fileHasher.updated_hashes, args.json_dir)


if __name__ == "__main__":
    main()
