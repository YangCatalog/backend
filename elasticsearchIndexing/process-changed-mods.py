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

import argparse
import configparser
import json
import logging
import os
import sys

import dateutil.parser
from elasticsearch import Elasticsearch, NotFoundError
from utility import log

from elasticsearchIndexing import build_yindex

__author__ = "Miroslav Kovac, Joe Clarke"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech, jclarke@cisco.com"

from utility.repoutil import pull

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process changed modules in a git repo")
    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = configparser.ConfigParser()
    config._interpolation = configparser.ExtendedInterpolation()
    config.read(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    LOGGER = log.get_logger('process_changed_mods', '{}/process-changed-mods.log'.format(log_directory))

    LOGGER.info('Initializing script loading config parameters')
    es_host = config.get('DB-Section', 'es-host')
    es_port = config.get('DB-Section', 'es-port')
    es_aws = config.get('DB-Section', 'es-aws')
    if es_aws == 'True':
        es_aws = True
    else:
        es_aws = False
    yang_models = config.get('Directory-Section', 'yang-models-dir')
    changes_cache_dir = config.get('Directory-Section', 'changes-cache')
    failed_changes_cache_dir = config.get('Directory-Section', 'changes-cache-failed')
    delete_cache_dir = config.get('Directory-Section', 'delete-cache')
    temp_dir = config.get('Directory-Section', 'temp')
    lock_file = config.get('Directory-Section', 'lock')
    lock_file_cron = config.get('Directory-Section', 'lock-cron')
    ytree_dir = config.get('Directory-Section', 'json-ytree')
    save_file_dir = config.get('Directory-Section', 'save-file-dir')
    threads = config.get('General-Section', 'threads')
    processes = int(config.get('General-Section', 'yProcesses'))
    elk_credentials = config.get('Secrets-Section', 'elk-secret').strip('"').split(' ')
    recursion_limit = sys.getrecursionlimit()
    if os.path.exists(lock_file) or os.path.exists(lock_file_cron):
        # we can exist since this is run by cronjob every minute of every day
        LOGGER.warning('Temporary lock file used by something else. Exiting script !!!')
        sys.exit()
    try:
        open(lock_file, 'w').close()
        open(lock_file_cron, 'w').close()
    except:
        os.unlink(lock_file)
        os.unlink(lock_file_cron)
        LOGGER.error('Temporary lock file could not be created although it is not locked')
        sys.exit()

    changes_cache = {}
    delete_cache = []
    if ((not os.path.exists(changes_cache_dir) or os.path.getsize(changes_cache_dir) <= 0)
            and (not os.path.exists(delete_cache_dir) or os.path.getsize(delete_cache_dir) <= 0)):
        LOGGER.info('No new modules are added or removed. Exiting script!!!')
        os.unlink(lock_file)
        os.unlink(lock_file_cron)
        sys.exit()
    else:
        if os.path.exists(changes_cache_dir) and os.path.getsize(changes_cache_dir) > 0:
            LOGGER.info('Loading changes cache')
            f = open(changes_cache_dir, 'r+')
            changes_cache = json.load(f)

            # Backup the contents just in case
            with open('{}.bak'.format(changes_cache_dir), 'w') as bfd:
                json.dump(changes_cache, bfd)

            f.truncate(0)
            f.close()

        if os.path.exists(delete_cache_dir) and os.path.getsize(delete_cache_dir) > 0:
            LOGGER.info('Loading delete cache')
            f = open(delete_cache_dir, 'r+')
            delete_cache = json.load(f)

            # Backup the contents just in case
            with open('{}.bak'.format(delete_cache_dir), 'w') as bfd:
                json.dump(delete_cache, bfd)

            f.truncate(0)
            f.close()
        os.unlink(lock_file)

    if len(delete_cache) > 0:
        if es_aws:
            es = Elasticsearch([es_host], http_auth=(elk_credentials[0], elk_credentials[1]), scheme="https", port=443)
        else:
            es = Elasticsearch([{'host': '{}'.format(es_host), 'port': es_port}])
        initialize_body_yindex = json.load(open('json/initialize_yindex_elasticsearch.json', 'r'))
        initialize_body_modules = json.load(open('json/initialize_module_elasticsearch.json', 'r'))

        es.indices.create(index='yindex', body=initialize_body_yindex, ignore=400)
        es.indices.create(index='modules', body=initialize_body_modules, ignore=400)

        logging.getLogger('elasticsearch').setLevel(logging.ERROR)

        for mod in delete_cache:
            mname = mod.split('@')[0]
            mrev_org = mod.split('@')[1]
            mrev = mrev_org.split('/')[0]
            morg = '/'.join(mrev_org.split('/')[1:])

            try:
                dateutil.parser.parse(mrev)
            except ValueError:
                if mrev[-2:] == '29' and mrev[-5:-3] == '02':
                    mrev = mrev.replace('02-29', '02-28')
                else:
                    mrev = '1970-01-01'

            try:
                query = \
                    {
                        "query": {
                            "bool": {
                                "must": [{
                                    "match_phrase": {
                                        "module.keyword": {
                                            "query": mname
                                        }
                                    }
                                }, {
                                    "match_phrase": {
                                        "revision": {
                                            "query": mrev
                                        }
                                    }
                                }]
                            }
                        }
                    }
                es.delete_by_query(index='yindex', body=query, doc_type='modules', conflicts='proceed',
                                   request_timeout=40)
                query['query']['bool']['must'].append({
                    "match_phrase": {
                        "organization": {
                            "query": morg
                        }
                    }
                })
                LOGGER.info('deleting {}'.format(query))
                es.delete_by_query(index='modules', body=query, doc_type='modules', conflicts='proceed',
                                   request_timeout=40)
            except NotFoundError:
                LOGGER.exception('Module not found')
                pass

    if len(changes_cache) == 0:
        LOGGER.info('No module to be processed. Exiting.')
        os.unlink(lock_file_cron)
        sys.exit(0)

    LOGGER.info('Pulling latest YangModels/yang repository')
    pull(yang_models)

    mod_args = []
    if type(changes_cache) is list:
        for module_path in changes_cache:
            if not module_path.startswith('/'):
                module_path = '{}/{}'.format(yang_models, module_path)
            mod_args.append(module_path)
    else:
        for key, module_path in changes_cache.items():
            mparts = key.split('/')
            if len(mparts) == 2:
                module_path += ':' + mparts[1]
            if not module_path.startswith('/'):
                module_path = '{}/{}'.format(yang_models, module_path)
            mod_args.append(module_path)
    sys.setrecursionlimit(50000)
    try:
        if es_aws:
            es = Elasticsearch([es_host], http_auth=(elk_credentials[0], elk_credentials[1]), scheme="https", port=443)
        else:
            es = Elasticsearch([{'host': '{}'.format(es_host), 'port': es_port}])
    except:
        sys.setrecursionlimit(recursion_limit)
        os.unlink(lock_file_cron)
        LOGGER.exception('Unable to initialize Elasticsearch')
        LOGGER.info('Job failed execution')
        sys.exit()

    build_yindex.build_yindex(ytree_dir, mod_args, LOGGER, save_file_dir, es, threads,
                              log_directory + '/process-changed-mods.log', failed_changes_cache_dir, temp_dir)
    sys.setrecursionlimit(recursion_limit)
    os.unlink(lock_file_cron)
    LOGGER.info('Job finished successfully')
