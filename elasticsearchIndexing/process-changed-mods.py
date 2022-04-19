# Copyright The IETF Trust 2021, All Rights Reserved
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

__author__ = 'Miroslav Kovac, Joe Clarke'
__copyright__ = 'Copyright 2018 Cisco and its affiliates'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech, jclarke@cisco.com'

import argparse
import json
import logging
import os
import shutil
import sys

import requests
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import AuthorizationException
from utility import log, repoutil
from utility.create_config import create_config
from utility.util import fetch_module_by_schema, validate_revision

from elasticsearchIndexing.build_yindex import build_indices
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices


def load_changes_cache(changes_cache_path: str):
    changes_cache = {}

    try:
        with open(changes_cache_path, 'r') as f:
            changes_cache = json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        with open(changes_cache_path, 'w') as f:
            json.dump({}, f)

    return changes_cache


def load_delete_cache(delete_cache_path: str):
    delete_cache = []

    try:
        with open(delete_cache_path, 'r') as f:
            delete_cache = json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        with open(delete_cache_path, 'w') as f:
            json.dump([], f)

    return delete_cache


def backup_cache_files(cache_path: str):
    shutil.copyfile(cache_path, '{}.bak'.format(cache_path))
    empty = {}
    if 'deletes' in cache_path:
        empty = []
    with open(cache_path, 'w') as f:
        json.dump(empty, f)


def check_file_availability(module: dict, LOGGER: logging.Logger):
    if os.path.isfile(module['path']):
        return
    result = False
    url = 'https://yangcatalog.org/api/search/modules/{},{},{}'.format(
        module['name'], module['revision'], module['organization'])
    try:
        module_detail = requests.get(url).json().get('module', [])
        schema = module_detail[0].get('schema')
        result = fetch_module_by_schema(schema, module['path'])
        if not result:
            raise Exception
        LOGGER.info('File content successfully retrieved from GitHub using module schema')
    except Exception:
        msg = 'Unable to retrieve content of {}@{}'.format(module['name'], module['revision'])
        raise Exception(msg)


def main():
    parser = argparse.ArgumentParser(description='Process changed modules in a git repo')
    parser.add_argument('--config-path', type=str, default=os.environ['YANGCATALOG_CONFIG_PATH'],
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = create_config(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    es_aws = config.get('DB-Section', 'es-aws')
    yang_models = config.get('Directory-Section', 'yang-models-dir')
    changes_cache_path = config.get('Directory-Section', 'changes-cache')
    failed_changes_cache_path = config.get('Directory-Section', 'changes-cache-failed')
    delete_cache_path = config.get('Directory-Section', 'delete-cache')
    lock_file = config.get('Directory-Section', 'lock')
    lock_file_cron = config.get('Directory-Section', 'lock-cron')
    json_ytree = config.get('Directory-Section', 'json-ytree')
    save_file_dir = config.get('Directory-Section', 'save-file-dir')
    threads = int(config.get('General-Section', 'threads'))
    elk_credentials = config.get('Secrets-Section', 'elk-secret').strip('"').split(' ')

    LOGGER = log.get_logger('process_changed_mods', os.path.join(log_directory, 'process-changed-mods.log'))
    LOGGER.info('Starting process-changed-mods.py script')

    if os.path.exists(lock_file) or os.path.exists(lock_file_cron):
        # we can exist since this is run by cronjob every 3 minutes of every day
        LOGGER.warning('Temporary lock file used by something else. Exiting script !!!')
        sys.exit()
    try:
        open(lock_file, 'w').close()
        open(lock_file_cron, 'w').close()
    except Exception:
        os.unlink(lock_file)
        os.unlink(lock_file_cron)
        LOGGER.error('Temporary lock file could not be created although it is not locked')
        sys.exit()

    changes_cache = load_changes_cache(changes_cache_path)
    delete_cache = load_delete_cache(delete_cache_path)

    if not changes_cache and not delete_cache:
        LOGGER.info('No new modules are added or removed. Exiting script!!!')
        os.unlink(lock_file)
        os.unlink(lock_file_cron)
        sys.exit()

    LOGGER.info('Pulling latest YangModels/yang repository')
    repoutil.pull(yang_models)

    LOGGER.info('Trying to initialize Elasticsearch')

    es_host_config = {
        'host': config.get('DB-Section', 'es-host', fallback='localhost'),
        'port': config.get('DB-Section', 'es-port', fallback='9200')
    }
    if es_aws == 'True':
        es = Elasticsearch(hosts=[es_host_config], http_auth=(elk_credentials[0], elk_credentials[1]), scheme='https')
    else:
        es = Elasticsearch(hosts=[es_host_config])

    with open(os.path.join(os.environ['BACKEND'], 'api/json/es/initialize_yindex_elasticsearch.json')) as f:
        initialize_body_yindex = json.load(f)
    with open(os.path.join(os.environ['BACKEND'], 'api/json/es/initialize_modules_elasticsearch.json')) as f:
        initialize_body_modules = json.load(f)

    LOGGER.info('Creating Elasticsearch indices')
    try:
        es.indices.create(index=ESIndices.YINDEX.value, body=initialize_body_yindex, ignore=400)
        es.indices.create(index=ESIndices.MODULES.value, body=initialize_body_modules, ignore=400)
    except AuthorizationException:
        # Reference: https://discuss.elastic.co/t/forbidden-12-index-read-only-allow-delete-api/110282/4
        for index in es.indices.get_alias('*'):
            read_only_query = {'index': {'blocks': {'read_only_allow_delete': 'false'}}}
            es.indices.put_settings(index=index, body=read_only_query)
        es.indices.create(index=ESIndices.YINDEX.value, body=initialize_body_yindex, ignore=400)
        es.indices.create(index=ESIndices.MODULES.value, body=initialize_body_modules, ignore=400)
    except Exception:
        LOGGER.exception('Error while creating ES indices')
        os.unlink(lock_file)
        os.unlink(lock_file_cron)
        sys.exit()

    es_manager = ESManager()
    if not es_manager.index_exists(ESIndices.AUTOCOMPLETE):
        es_manager.create_index(ESIndices.AUTOCOMPLETE)

    logging.getLogger('elasticsearch').setLevel(logging.ERROR)

    backup_cache_files(delete_cache_path)
    backup_cache_files(changes_cache_path)
    os.unlink(lock_file)

    if delete_cache:
        for module in delete_cache:
            name, rev_org = module.split('@')
            revision, organization = rev_org.split('/')
            revision = validate_revision(revision)

            module = {
                'name': name,
                'revision': revision,
                'organization': organization
            }
            es_manager.delete_from_indices(module)

    if changes_cache:
        recursion_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(50000)
        x = 0
        try:
            for module_key, module_path in changes_cache.items():
                x += 1
                name, rev_org = module_key.split('@')
                revision, organization = rev_org.split('/')
                revision = validate_revision(revision)
                name_revision = '{}@{}'.format(name, revision)

                module = {
                    'name': name,
                    'revision': revision,
                    'organization': organization,
                    'path': module_path
                }
                LOGGER.info('yindex on module {}. module {} out of {}'.format(name_revision, x, len(changes_cache)))
                check_file_availability(module, LOGGER)

                try:
                    build_indices(es_manager, module, save_file_dir, json_ytree, threads, LOGGER)
                except Exception:
                    LOGGER.exception('Problem while processing module {}'.format(module_key))
                    try:
                        with open(failed_changes_cache_path, 'r') as f:
                            failed_modules = json.load(f)
                    except (FileNotFoundError, json.decoder.JSONDecodeError):
                        failed_modules = {}
                    if module_key not in failed_modules:
                        failed_modules[module_key] = module_path
                    with open(failed_changes_cache_path, 'w') as f:
                        json.dump(failed_modules, f)
        except Exception:
            sys.setrecursionlimit(recursion_limit)
            os.unlink(lock_file_cron)
            LOGGER.exception('Error while running build_yindex.py script')
            LOGGER.info('Job failed execution')
            sys.exit()

        sys.setrecursionlimit(recursion_limit)
    os.unlink(lock_file_cron)
    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
