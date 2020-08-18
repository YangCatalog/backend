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
sdo (default true) this script will start to look
for xml files or it will start to parse all the yang
files in the directory ignoring all the vendor metadata
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import fnmatch
import os
import sys
import time

import utility.log as log
from parseAndPopulate import capability as cap
from parseAndPopulate import integrity
from parseAndPopulate.prepare import Prepare

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

class ScriptConfig():
    def __init__(self):
        self.help = "Parse modules on given directory and generate json with module metadata that can be populated" \
                    " to confd directory"
        parser = argparse.ArgumentParser()
        parser.add_argument('--dir', default='/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC', type=str,
                            help='Set dir where to look for hello message xml files or yang files if using "sdo" option')
        parser.add_argument('--save-modification-date', action='store_true', default=False,
                            help='if True than it will create a file with modification date and also it will check if '
                                'file was modified from last time if not it will skip it.')
        parser.add_argument('--api', action='store_true', default=False, help='If request came from api')
        parser.add_argument('--sdo', action='store_true', default=False,
                            help='If we are processing sdo or vendor yang modules')
        parser.add_argument('--run-integrity', action='store_true', default=False,
                            help='If we want to run integrity tool check')
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
                            default='/etc/yangcatalog/yangcatalog.conf',
                            help='Set path to config file')

        self.args = parser.parse_args()
        self.defaults = [parser.get_default(key) for key in self.args.__dict__.keys()]

    def get_args_list(self):
        args_dict = {}
        keys = [key for key in self.args.__dict__.keys()]
        types = [type(value).__name__ for value in self.args.__dict__.values()]

        i = 0
        for key in keys:
            args_dict[key] = dict(type=types[i], default=self.defaults[i])
            i += 1
        return args_dict

    def get_help(self):
        ret = {}
        ret['help'] = self.help
        ret['options'] = {}
        ret['options']['dir'] = 'Set dir where to look for hello message xml files or yang files if using "sdo" option'
        ret['options']['save-modification-date'] = 'if True than it will create a file with modification date and' \
                                                   ' also it will check if file was modified from last time if not it' \
                                                   ' will skip it'
        ret['options']['api'] = 'If request came from api'
        ret['options']['sdo'] = 'If we are processing sdo or vendor yang modules'
        ret['options']['run-integrity'] = 'If we want to run integrity tool check'
        ret['options']['json-dir'] = 'Directory where json files to populate confd will be stored'
        ret['options']['result-html-dir'] = 'Set dir where to write html compilation result files'
        ret['options']['save-file-dir'] = 'Directory where the yang file will be saved'
        ret['options']['api-protocol'] = 'Whether api runs on http or https. Default is set to https'
        ret['options']['api-port'] = 'Set port where the api is started (This will be ignored if we are using uwsgi)'
        ret['options']['api-ip'] = 'Set ip address where the api is started. Default -> yangcatalog.org'
        ret['options']['config-path'] = 'Set path to config file'
        return ret


def find_missing_hello(directory, pattern):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                if not any(".xml" in name for name in files):
                    yield root


def find_files(directory, pattern):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename


def create_integrity(yang_models):
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read('/etc/yangcatalog/yangcatalog.conf')
    path = '{}/.'.format(config.get('Web-Section', 'public-directory'))
    integrity_file = open('{}/integrity.html'.format(path), 'w')
    local_integrity.dumps(integrity_file, yang_models)
    integrity_file.close()


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args

    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    LOGGER = log.get_logger('runCapabilities', log_directory + '/parseAndPopulate.log')
    is_uwsgi = config.get('General-Section', 'uwsgi')
    private_dir = config.get('Web-Section', 'private-directory')
    yang_models = config.get('Directory-Section', 'yang-models-dir')

    temp_dir = config.get('Directory-Section', 'temp')

    separator = ':'
    suffix = args.api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(args.api_protocol,
                                                   args.api_ip, separator,
                                                   suffix)
    start = time.time()
    global local_integrity
    if args.run_integrity:
        local_integrity = integrity.Statistics(args.dir)
    else:
        local_integrity = None
    prepare = Prepare(log_directory, "prepare", yangcatalog_api_prefix)
    search_dirs = [args.dir]

    if args.run_integrity:
        stats_list = {'vendor': [yang_models + '/vendor/cisco']}
    LOGGER.info('Starting to iterate through files')
    if args.sdo:
        LOGGER.info('Found directory for sdo {}'.format(args.dir))

        capability = cap.Capability(log_directory, args.dir, prepare,
                                    local_integrity, args.api, args.sdo,
                                    args.json_dir, args.result_html_dir,
                                    args.save_file_dir, private_dir, yang_models)
        LOGGER.info('Starting to parse files in sdo directory')
        capability.parse_and_dump_sdo()
        prepare.dump_modules(args.json_dir)
    else:
        patterns = ['*ietf-yang-library*.xml', '*capabilit*.xml']
        for pattern in patterns:
            for filename in find_files(args.dir, pattern):
                update = True
                if not args.api and args.save_modification_date:
                    try:
                        file_modification = open(temp_dir + '/fileModificationDate/' + '-'.join(filename.split('/')[-4:]) +
                                                 '.txt', 'rw')
                        time_in_file = file_modification.readline()
                        if time_in_file in str(time.ctime(os.path.getmtime(filename))):
                            update = False
                            LOGGER.info('{} is not modified. Skipping this file'.format(filename))
                            file_modification.close()
                        else:
                            file_modification.seek(0)
                            file_modification.write(time.ctime(os.path.getmtime(filename)))
                            file_modification.truncate()
                            file_modification.close()
                    except IOError:
                        file_modification = open(temp_dir + '/fileModificationDate/' + '-'.join(filename.split('/')[-4:]) +
                                                 '.txt', 'w')
                        file_modification.write(str(time.ctime(os.path.getmtime(filename))))
                        file_modification.close()
                if update:
                    LOGGER.info('Found xml source {}'.format(filename))

                    capability = cap.Capability(log_directory, filename,
                                                prepare,
                                                local_integrity, args.api,
                                                args.sdo, args.json_dir,
                                                args.result_html_dir,
                                                args.save_file_dir,
                                                private_dir,
                                                yang_models,
                                                args.run_integrity)
                    if 'ietf-yang-library' in pattern:
                        capability.parse_and_dump_yang_lib()
                    else:
                        capability.parse_and_dump()
        if not args.run_integrity:
            prepare.dump_modules(args.json_dir)
            prepare.dump_vendors(args.json_dir)

    if local_integrity is not None and args.run_integrity:
        create_integrity(yang_models)
    end = time.time()
    LOGGER.info('Time taken to parse all the files {} seconds'.format(end - start))


if __name__ == "__main__":
    main()
