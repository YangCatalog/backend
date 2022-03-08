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

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import json
import multiprocessing
import os
import shutil
import sys
import time
import types
import typing as t
from argparse import Namespace
from importlib import import_module

import requests
import utility.log as log
from redisConnections.redisConnection import RedisConnection
from utility.confdService import ConfdService
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.staticVariables import json_headers
from utility.util import prepare_to_indexing, send_to_indexing2

from parseAndPopulate.fileHasher import FileHasher
from parseAndPopulate.modulesComplicatedAlgorithms import ModulesComplicatedAlgorithms


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        config = create_config()
        credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
        api_protocol = config.get('General-Section', 'protocol-api')
        api_port = config.get('Web-Section', 'api-port')
        api_host = config.get('Web-Section', 'ip')
        save_file_dir = config.get('Directory-Section', 'save-file-dir')
        result_dir = config.get('Web-Section', 'result-html-dir')
        help = 'Parse hello messages and YANG files to a JSON dictionary. These ' \
               'dictionaries are used for populating the yangcatalog. This script first ' \
               'runs the runCapabilities.py script to create JSON files which are ' \
               'used to populate database.'
        args: t.List[Arg] = [
            {
                'flag': '--api-ip',
                'help': 'Set host address where the API is started. Default: {}'.format(api_host),
                'type': str,
                'default': api_host
            },
            {
                'flag': '--api-port',
                'help': 'Set port where the API is started. Default: {}'.format(api_port),
                'type': int,
                'default': api_port
            },
            {
                'flag': '--api-protocol',
                'help': 'Whether API runs on http or https (This will be ignored if we are using uwsgi). '
                        'Default: {}'.format(api_protocol),
                'type': str,
                'default': api_protocol
            },
            {
                'flag': '--credentials',
                'help': 'Set authorization parameters username and password respectively.',
                'type': str,
                'nargs': 2,
                'default': credentials
            },
            {
                'flag': '--dir',
                'help': 'Set directory where to look for hello message xml files',
                'type': str,
                'default': '/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC'
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
                'flag': '--notify-indexing',
                'help': 'Whether to send files for indexing',
                'action': 'store_true',
                'default': False
            },
            {
                'flag': '--result-html-dir',
                'help': 'Set dir where to write HTML compilation result files. Default: {}'.format(result_dir),
                'type': str,
                'default': result_dir
            },
            {
                'flag': '--save-file-dir',
                'help': 'Directory where the yang file will be saved. Default: {}'.format(save_file_dir),
                'type': str,
                'default': save_file_dir
            },
            {
                'flag': '--force-parsing',
                'help': 'Force parse files (do not skip parsing for unchanged files).',
                'action': 'store_true',
                'default': False
            }
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])

        self.log_directory = config.get('Directory-Section', 'logs')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        self.yang_models = config.get('Directory-Section', 'yang-models-dir')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.changes_cache_dir = config.get('Directory-Section', 'changes-cache')
        self.cache_dir = config.get('Directory-Section', 'cache')
        self.delete_cache_dir = config.get('Directory-Section', 'delete-cache')
        self.lock_file = config.get('Directory-Section', 'lock')
        self.ytree_dir = config.get('Directory-Section', 'json-ytree')


def reload_cache_in_parallel(credentials: t.List[str], yangcatalog_api_prefix: str):
    LOGGER.info('Sending request to reload cache in different thread')
    url = '{}load-cache'.format(yangcatalog_api_prefix)
    response = requests.post(url, None,
                             auth=(credentials[0], credentials[1]),
                             headers=json_headers)
    if response.status_code != 201:
        LOGGER.warning('Could not send a load-cache request. Status code {}. message {}'
                       .format(response.status_code, response.text))
    LOGGER.info('Cache reloaded successfully')


def configure_runCapabilities(module: types.ModuleType, args: Namespace, json_dir: str)\
    -> BaseScriptConfig:
    """ Set values to ScriptConfig arguments to be able to run runCapabilities script.

    Arguments:
        :param submodule    (obj) submodule object
        :param args         (obj) populate script arguments
        :param direc        (str) Directory where json files to populate ConfD will be stored
    """
    script_conf = module.ScriptConfig()
    options = (
        ('json_dir', json_dir),
        ('result_html_dir', args.result_html_dir),
        ('dir', args.dir),
        ('save_file_dir', args.save_file_dir),
        ('api_ip', args.api_ip),
        ('api_port', repr(args.api_port)),
        ('api_protocol', args.api_protocol),
        ('api', args.api),
        ('sdo', args.sdo),
        ('save_file_hash', not args.force_parsing)
    )
    for attr, value in options:
        setattr(script_conf.args, attr, value)

    return script_conf


def create_dir_name(temp_dir: str) -> str:
    i = 0
    while True:
        i += 1
        new_dir_name = os.path.join(temp_dir, str(i))
        if not os.path.exists(new_dir_name):
            break
    return os.path.join(temp_dir, str(i))


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
    redisConnection = RedisConnection()
    LOGGER.info('Starting the populate script')
    start = time.time()
    if args.api:
        json_dir = args.dir
    else:
        json_dir = create_dir_name(temp_dir)
        os.makedirs(json_dir)
    LOGGER.info('Calling runCapabilities script')
    try:
        runCapabilities = import_module('parseAndPopulate.runCapabilities')
        script_conf = configure_runCapabilities(runCapabilities, args, json_dir)
        runCapabilities.main(scriptConf=script_conf)
    except Exception as e:
        LOGGER.exception('runCapabilities error:\n{}'.format(e))
        raise e

    body_to_send = {}
    if args.notify_indexing:
        LOGGER.info('Sending files for indexing')
        body_to_send = prepare_to_indexing(yangcatalog_api_prefix, os.path.join(json_dir, 'prepare.json'),
                                            LOGGER, args.save_file_dir, temp_dir, sdo_type=args.sdo, from_api=args.api)

    LOGGER.info('Populating yang catalog with data. Starting to add modules')
    with open(os.path.join(json_dir, 'prepare.json')) as data_file:
        data = data_file.read()
    modules = json.loads(data).get('module', [])
    errors = confdService.patch_modules(modules)
    redisConnection.populate_modules(modules)

    # In each json
    if os.path.exists(os.path.join(json_dir, 'normal.json')):
        LOGGER.info('Starting to add vendors')
        with open(os.path.join(json_dir, 'normal.json')) as data:
            try:
                vendors = json.loads(data.read())['vendors']['vendor']
            except KeyError as e:
                LOGGER.error('No files were parsed. This probably means the directory is missing capability xml files')
                raise e
        errors = errors or confdService.patch_vendors(vendors)
        redisConnection.populate_implementation(vendors)
    if body_to_send:
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
                                                             args.credentials, args.save_file_dir, json_dir, None,
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
        if not errors:
            path = os.path.join(json_dir, 'temp_hashes.json')
            fileHasher = FileHasher('backend_files_modification_hashes', cache_dir, not args.force_parsing, log_directory)
            updated_hashes = fileHasher.load_hashed_files_list(path)
            if updated_hashes:
                fileHasher.merge_and_dump_hashed_files_list(updated_hashes)

        if os.path.exists(json_dir):
            shutil.rmtree(json_dir)
    LOGGER.info('Populate script finished successfully')


if __name__ == '__main__':
    try:
        main()
    except:
        exit(1)
