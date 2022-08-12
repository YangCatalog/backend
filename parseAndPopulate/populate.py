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
This script calls parse_directory.py script with
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
from utility.util import prepare_for_es_indexing, send_for_es_indexing

from parseAndPopulate.file_hasher import FileHasher
from parseAndPopulate.modulesComplicatedAlgorithms import \
    ModulesComplicatedAlgorithms


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        config = create_config()
        credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
        save_file_dir = config.get('Directory-Section', 'save-file-dir')
        result_dir = config.get('Web-Section', 'result-html-dir')
        help = 'Parse hello messages and YANG files to a JSON dictionary. These ' \
               'dictionaries are used for populating the yangcatalog. This script first ' \
               'runs the parse_directory.py script to create JSON files which are ' \
               'used to populate database.'
        args: t.List[Arg] = [
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
            },
            {
                'flag': '--force-indexing',
                'help': 'Force indexing files (do not skip indexing for unchanged files).',
                'action': 'store_true',
                'default': False
            }
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])

        self.log_directory = config.get('Directory-Section', 'logs')
        self.yang_models = config.get('Directory-Section', 'yang-models-dir')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.changes_cache_path = config.get('Directory-Section', 'changes-cache')
        self.cache_dir = config.get('Directory-Section', 'cache')
        self.delete_cache_path = config.get('Directory-Section', 'delete-cache')
        self.lock_file = config.get('Directory-Section', 'lock')
        self.failed_changes_cache_path = config.get('Directory-Section', 'changes-cache-failed')
        self.json_ytree = config.get('Directory-Section', 'json-ytree')
        self.yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')


def reload_cache_in_parallel(credentials: t.List[str], yangcatalog_api_prefix: str):
    LOGGER.info('Sending request to reload cache in different thread')
    url = '{}/load-cache'.format(yangcatalog_api_prefix)
    response = requests.post(url, None,
                             auth=(credentials[0], credentials[1]),
                             headers=json_headers)
    if response.status_code != 201:
        LOGGER.warning('Could not send a load-cache request. Status code {}. message {}'
                       .format(response.status_code, response.text))
    LOGGER.info('Cache reloaded successfully')


def configure_parse_directory(module: types.ModuleType, args: Namespace, json_dir: str)\
        -> BaseScriptConfig:
    """ Set values to ScriptConfig arguments to be able to run parse_directory script.

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
    yang_models = scriptConf.yang_models
    temp_dir = scriptConf.temp_dir
    cache_dir = scriptConf.cache_dir
    json_ytree = scriptConf.json_ytree
    yangcatalog_api_prefix = scriptConf.yangcatalog_api_prefix
    global LOGGER
    LOGGER = log.get_logger('populate', '{}/parseAndPopulate.log'.format(log_directory))

    confd_service = ConfdService()
    redis_connection = RedisConnection()
    LOGGER.info('Starting the populate script')
    start = time.time()
    if args.api:
        json_dir = args.dir
    else:
        json_dir = create_dir_name(temp_dir)
        os.makedirs(json_dir)
    LOGGER.info('Calling parse_directory script')
    try:
        parse_directory = import_module('parseAndPopulate.parse_directory')
        script_conf = configure_parse_directory(parse_directory, args, json_dir)
        parse_directory.main(scriptConf=script_conf)
    except Exception as e:
        LOGGER.exception('parse_directory error:\n{}'.format(e))
        raise e

    body_to_send = {}
    if args.notify_indexing:
        LOGGER.info('Sending files for indexing')
        body_to_send = prepare_for_es_indexing(yangcatalog_api_prefix, os.path.join(json_dir, 'prepare.json'),
                                               LOGGER, args.save_file_dir, force_indexing=args.force_indexing)

    LOGGER.info('Populating yang catalog with data. Starting to add modules')
    with open(os.path.join(json_dir, 'prepare.json')) as data_file:
        data = data_file.read()
    modules = json.loads(data).get('module', [])
    errors = confd_service.patch_modules(modules)
    redis_connection.populate_modules(modules)

    # In each json
    if os.path.exists(os.path.join(json_dir, 'normal.json')):
        LOGGER.info('Starting to add vendors')
        with open(os.path.join(json_dir, 'normal.json')) as data:
            try:
                vendors = json.loads(data.read())['vendors']['vendor']
            except KeyError as e:
                LOGGER.error('No files were parsed. This probably means the directory is missing capability xml files')
                raise e
        errors = errors or confd_service.patch_vendors(vendors)
        redis_connection.populate_implementation(vendors)
    if body_to_send:
        LOGGER.info('Sending files for indexing')
        indexing_paths = {
            'cache_path': scriptConf.changes_cache_path,
            'deletes_path': scriptConf.delete_cache_path,
            'failed_path': scriptConf.failed_changes_cache_path,
            'lock_path': scriptConf.lock_file
        }
        send_for_es_indexing(body_to_send, LOGGER, indexing_paths)
    if modules:
        process_reload_cache = multiprocessing.Process(target=reload_cache_in_parallel,
                                                       args=(args.credentials, yangcatalog_api_prefix,))
        process_reload_cache.start()
        LOGGER.info('Running ModulesComplicatedAlgorithms from populate.py script')
        recursion_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(50000)
        complicated_algorithms = ModulesComplicatedAlgorithms(log_directory, yangcatalog_api_prefix,
                                                              args.credentials, args.save_file_dir, json_dir, None,
                                                              yang_models, temp_dir, json_ytree)
        complicated_algorithms.parse_non_requests()
        LOGGER.info('Waiting for cache reload to finish')
        process_reload_cache.join()
        complicated_algorithms.parse_requests()
        sys.setrecursionlimit(recursion_limit)
        LOGGER.info('Populating with new data of complicated algorithms')
        complicated_algorithms.populate()
        end = time.time()
        LOGGER.info('Populate took {} seconds with the main and complicated algorithm'.format(int(end - start)))

        # Keep new hashes only if the ConfD was patched successfully
        if not errors:
            path = os.path.join(json_dir, 'temp_hashes.json')
            fileHasher = FileHasher('backend_files_modification_hashes', cache_dir, not args.force_parsing, log_directory)
            updated_hashes = fileHasher.load_hashed_files_list(path)
            if updated_hashes:
                fileHasher.merge_and_dump_hashed_files_list(updated_hashes)

    LOGGER.info('Populate script finished successfully')


if __name__ == '__main__':
    try:
        main()
    except:
        exit(1)
