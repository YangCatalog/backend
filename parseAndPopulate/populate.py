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
This script calls runCapabilities.py script with
option based on whether we are populating SDOs or vendors
and also whether this script was called via API or directly by
yangcatalog admin user. Once the metatadata are parsed
and json files are created it will populate the ConfD
with all the parsed metadata, reloads API and starts to
parse metadata that needs to use complicated algorthms.
For this we use class ModulesComplicatedAlgorithms.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import errno
import json
import multiprocessing
import os
import shutil
import sys
import time

import requests
import utility.log as log
from utility.confdService import ConfdService
from utility.create_config import create_config
from utility.staticVariables import json_headers
from utility.util import prepare_to_indexing, send_to_indexing2

from parseAndPopulate.fileHasher import FileHasher
from parseAndPopulate.modulesComplicatedAlgorithms import \
    ModulesComplicatedAlgorithms


class ScriptConfig:
    def __init__(self):
        config = create_config()
        self.log_directory = config.get('Directory-Section', 'logs')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        self.yang_models = config.get('Directory-Section', 'yang-models-dir')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.changes_cache_dir = config.get('Directory-Section', 'changes-cache')
        self.cache_dir = config.get('Directory-Section', 'cache')
        self.delete_cache_dir = config.get('Directory-Section', 'delete-cache')
        self.lock_file = config.get('Directory-Section', 'lock')
        self.ytree_dir = config.get('Directory-Section', 'json-ytree')
        credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
        self.__api_protocol = config.get('General-Section', 'protocol-api')
        self.__api_port = config.get('Web-Section', 'api-port')
        self.__api_host = config.get('Web-Section', 'ip')
        self.__save_file_dir = config.get('Directory-Section', 'save-file-dir')
        self.__result_dir = config.get('Web-Section', 'result-html-dir')
        self.help = 'Parse hello messages and YANG files to JSON dictionary. These' \
            ' dictionaries are used for populating a yangcatalog. This script runs' \
            ' first a runCapabilities.py script to create a JSON files which are' \
            ' used to populate database.'

        parser = argparse.ArgumentParser(description=self.help)
        parser.add_argument('--api-ip', default=self.__api_host, type=str,
                            help='Set host address where the API is started. Default: {}'.format(self.__api_host))
        parser.add_argument('--api-port', default=self.__api_port, type=int,
                            help='Set port where the API is started. Default: {}'.format(self.__api_port))
        parser.add_argument('--api-protocol', type=str, default=self.__api_protocol,
                            help='Whether API runs on http or https (This will be ignored if we are using uwsgi).'
                                 ' Default: {}'.format(self.__api_protocol))
        parser.add_argument('--credentials', help='Set authorization parameters username password respectively.',
                            nargs=2, default=credentials, type=str)
        parser.add_argument('--dir', default='/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC', type=str,
                            help='Set dir where to look for hello message xml files')
        parser.add_argument('--api', action='store_true', default=False, help='If request came from api')
        parser.add_argument('--sdo', action='store_true', default=False,
                            help='If we are processing sdo or vendor yang modules')
        parser.add_argument('--notify-indexing', action='store_true', default=False, help='Whether to send files for'
                                                                                          ' indexing')
        parser.add_argument('--result-html-dir', default=self.__result_dir, type=str,
                            help='Set dir where to write HTML compilation result files. Default: {}'.format(self.__result_dir))
        parser.add_argument('--save-file-dir', default=self.__save_file_dir,
                            type=str, help='Directory where the yang file will be saved. Default: {}'.format(self.__save_file_dir))
        parser.add_argument('--force-parsing', action='store_true', default=False,
                            help='Force to parse files (do not skip parsing for unchanged files).')
        self.args, _ = parser.parse_known_args()
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
        ret['options']['api'] = 'If request came from api'
        ret['options']['sdo'] = 'If we are processing sdo or vendor yang modules'
        ret['options']['notify_indexing'] = 'Whether to send files for indexing'
        ret['options']['result_html_dir'] = 'Set dir where to write HTML compilation result files. Default: {}'.format(self.__result_dir)
        ret['options']['save_file_dir'] = 'Directory where the yang file will be saved. Default: {}'.format(self.__save_file_dir)
        ret['options']['api_protocol'] = 'Whether API runs on http or https. Default: {}'.format(self.__api_protocol)
        ret['options']['api_port'] = 'Whether API runs on http or https (This will be ignored if we are using uwsgi).' \
                                     ' Default: {}'.format(self.__api_protocol)
        ret['options']['api_ip'] = 'Set host address where the API is started. Default: {}'.format(self.__api_host)
        ret['options']['force_parsing'] = 'Force to parse files (do not skip parsing for unchanged files).'
        return ret


def reload_cache_in_parallel(credentials: list, yangcatalog_api_prefix: str):
    LOGGER.info('Sending request to reload cache in different thread')
    url = '{}load-cache'.format(yangcatalog_api_prefix)
    response = requests.post(url, None,
                             auth=(credentials[0], credentials[1]),
                             headers=json_headers)
    if response.status_code != 201:
        LOGGER.warning('Could not send a load-cache request. Status code {}. message {}'
                       .format(response.status_code, response.text))
    LOGGER.info('Cache reloaded successfully')


def __set_runcapabilities_script_conf(submodule, args, direc: str):
    """ Set values to ScriptConfig arguments to be able to run runCapabilities script.

    Arguments:
        :param submodule    (obj) submodule object
        :param args         (obj) populate script arguments
        :param direc        (str) Directory where json files to populate ConfD will be stored
    """
    script_conf = submodule.ScriptConfig()
    script_conf.args.__setattr__('json_dir', direc)
    script_conf.args.__setattr__('result_html_dir', args.result_html_dir)
    script_conf.args.__setattr__('dir', args.dir)
    script_conf.args.__setattr__('save_file_dir', args.save_file_dir)
    script_conf.args.__setattr__('api_ip', args.api_ip)
    script_conf.args.__setattr__('api_port', repr(args.api_port))
    script_conf.args.__setattr__('api_protocol', args.api_protocol)
    script_conf.args.__setattr__('api', args.api)
    script_conf.args.__setattr__('sdo', args.sdo)
    script_conf.args.__setattr__('save_file_hash', not args.force_parsing)

    return script_conf


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    log_directory = scriptConf.log_directory
    is_uwsgi = scriptConf.is_uwsgi
    yang_models = scriptConf.yang_models
    temp_dir = scriptConf.temp_dir
    cache_dir = scriptConf.cache_dir
    ytree_dir = scriptConf.ytree_dir
    global LOGGER
    LOGGER = log.get_logger('populate', '{}/parseAndPopulate.log'.format(log_directory))

    separator = ':'
    suffix = args.api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(args.api_protocol, args.api_ip, separator, suffix)
    confdService = ConfdService()
    LOGGER.info('Starting the populate script')
    start = time.time()
    if args.api:
        direc = args.dir
        args.dir += '/temp'
    else:
        direc = 0
        while True:
            try:
                os.makedirs('{}/{}'.format(temp_dir, repr(direc)))
                break
            except OSError as e:
                direc += 1
                if e.errno != errno.EEXIST:
                    raise
        direc = '{}/{}'.format(temp_dir, repr(direc))
    LOGGER.info('Calling runcapabilities script')
    try:
        module = __import__('parseAndPopulate', fromlist=['runCapabilities'])
        submodule = getattr(module, 'runCapabilities')
        script_conf = __set_runcapabilities_script_conf(submodule, args, direc)
        submodule.main(scriptConf=script_conf)
    except Exception as e:
        LOGGER.exception('runCapabilities error:\n{}'.format(e))
        raise e

    body_to_send = {}
    if args.notify_indexing:
        LOGGER.info('Sending files for indexing')
        body_to_send = prepare_to_indexing(yangcatalog_api_prefix, '{}/prepare.json'.format(direc), args.credentials,
                                           LOGGER, args.save_file_dir, temp_dir, sdo_type=args.sdo, from_api=args.api)

    LOGGER.info('Populating yang catalog with data. Starting to add modules')
    confd_patched = True
    x = -1
    with open('{}/prepare.json'.format(direc)) as data_file:
        read = data_file.read()
        modules_json = json.loads(read).get('module', [])
        for x in range(0, int(len(modules_json) / 1000)):
            json_modules_data = json.dumps({
                'modules':
                    {
                        'module': modules_json[x * 1000: (x * 1000) + 1000]
                    }
            })

            if '{"module": []}' not in read:
                response = confdService.patch_modules(json_modules_data)

                if response.status_code < 200 or response.status_code > 299:
                    confd_patched = False
                    path_to_file = '{}/modules-confd-data-{}'.format(direc, x)
                    with open(path_to_file, 'w') as f:
                        json.dump(json_modules_data, f)
                    LOGGER.error('Request with body {} failed to patch modules with {}'
                                 .format(path_to_file, response.text))
    json_modules_data = json.dumps({
        'modules':
            {
                'module': modules_json[(x * 1000) + 1000:]
            }
    })
    if '{"module": []}' not in json_modules_data:
        response = confdService.patch_modules(json_modules_data)

        if response.status_code < 200 or response.status_code > 299:
            confd_patched = False
            path_to_file = '{}/modules-confd-data-rest'.format(direc)
            with open(path_to_file, 'w') as f:
                json.dump(json_modules_data, f)
            LOGGER.error('Request with body {} failed to patch modules with {}'
                         .format(path_to_file, response.text))

    # In each json
    if os.path.exists('{}/normal.json'.format(direc)):
        LOGGER.info('Starting to add vendors')
        x = -1
        with open('{}/normal.json'.format(direc)) as data:
            vendors = json.loads(data.read())['vendors']['vendor']
            for x in range(0, int(len(vendors) / 1000)):
                json_implementations_data = json.dumps({
                    'vendors':
                        {
                            'vendor': vendors[x * 1000: (x * 1000) + 1000]
                        }
                })

                # Make a PATCH request to create a root for each file
                response = confdService.patch_vendors(json_implementations_data)

                if response.status_code < 200 or response.status_code > 299:
                    confd_patched = False
                    path_to_file = '{}/vendors-confd-data-{}'.format(direc, x)
                    with open(path_to_file, 'w') as f:
                        json.dump(json_modules_data, f)
                    LOGGER.error('Request with body {} failed to patch vendors with {}'
                                 .format(path_to_file, response.text))
            json_implementations_data = json.dumps({
                'vendors':
                    {
                        'vendor': vendors[(x * 1000) + 1000:]
                    }
            })
            response = confdService.patch_vendors(json_implementations_data)

            if response.status_code < 200 or response.status_code > 299:
                confd_patched = False
                path_to_file = '{}/vendors-confd-data-rest'.format(direc)
                with open(path_to_file, 'w') as f:
                    json.dump(json_modules_data, f)
                LOGGER.error('Request with body {} failed to patch vendors with {}'
                             .format(json_implementations_data, response.text))
    if len(body_to_send) > 0:
        LOGGER.info('Sending files for indexing')
        send_to_indexing2(body_to_send, LOGGER, scriptConf.changes_cache_dir, scriptConf.delete_cache_dir,
                          scriptConf.lock_file)
    if not args.api:
        process_reload_cache = multiprocessing.Process(target=reload_cache_in_parallel,
                                                       args=(args.credentials, yangcatalog_api_prefix,))
        process_reload_cache.start()
        LOGGER.info('Running ModulesComplicatedAlgorithms from populate.py script')
        recursion_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(50000)
        complicatedAlgorithms = ModulesComplicatedAlgorithms(log_directory, yangcatalog_api_prefix,
                                                             args.credentials, args.save_file_dir, direc, None,
                                                             yang_models, temp_dir, ytree_dir)
        complicatedAlgorithms.parse_non_requests()
        LOGGER.info('Waiting for cache reload to finish')
        process_reload_cache.join()
        complicatedAlgorithms.parse_requests()
        sys.setrecursionlimit(recursion_limit)
        LOGGER.info('Populating with new data of complicated algorithms')
        complicatedAlgorithms.populate()
        end = time.time()
        LOGGER.info('Populate took {} seconds with the main and complicated algorithm'.format(int(end - start)))

        # Keep new hashes only if the ConfD was patched successfully
        if confd_patched:
            path = '{}/temp_hashes.json'.format(direc)
            fileHasher = FileHasher('backend_files_modification_hashes', cache_dir, not args.force_parsing, log_directory)
            updated_hashes = fileHasher.load_hashed_files_list(path)
            if len(updated_hashes) > 0:
                fileHasher.merge_and_dump_hashed_files_list(updated_hashes)

        try:
            shutil.rmtree('{}'.format(direc))
        except OSError:
            # Be happy if deleted
            pass
    LOGGER.info('Populate script finished successfully')


if __name__ == "__main__":
    main()
