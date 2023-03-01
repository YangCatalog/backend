"""
PHASE I:
This script loops through each key in the Redis database (= each stored module)
and checks whether the necessary information about this module is also in the Elasticsearch database.
If module is missing in Elasticsearch database, check if it is stored in all_modules folder,
and dump it in format which can be directly used to insert to Elasticsearch.
PHASE II:
Search and scroll all the documents in the 'modules' index and check whether this modules
is also stored in Redis database
Finally, all the information are dumped into json file, so they can be reviewed later.
"""
import json
import os

from elasticsearch.exceptions import RequestError
from redis import Redis

import utility.log as log
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from utility.create_config import create_config


def check_module_in_redis(hits: dict, redis: Redis):
    redis_missing = []
    redis_missing_count = 0

    for key in hits:
        data = redis.get(key)
        if data == '{}':
            redis_missing.append(key)
            redis_missing_count += 1

    if redis_missing_count:
        LOGGER.info('{} out of {} missing in Redis'.format(redis_missing_count, len(hits)))

    return redis_missing


def main():
    config = create_config()
    redis_host = config.get('DB-Section', 'redis-host', fallback='localhost')
    redis_port = int(config.get('DB-Section', 'redis-port', fallback='6379'))
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')

    global LOGGER
    LOGGER = log.get_logger('sandbox', '{}/sandbox.log'.format(log_directory))

    # Create Redis and Elasticsearch connections
    redis = Redis(host=redis_host, port=redis_port, db=1)
    es_manager = ESManager()

    # Set up variables and counters
    es_missing_modules = []
    redis_missing_modules = []
    incorrect_format_modules = []
    modules_to_index_dict = {}
    modules_to_index_list = []
    redis_modules = 0

    # PHASE I: Check modules from Redis in Elasticsearch
    LOGGER.info('Starting PHASE I')
    for redis_key in redis.scan_iter():
        try:
            key = redis_key.decode('utf-8')
            name, rev_org = key.split('@')
            revision, organization = rev_org.split('/')
            redis_modules += 1
            module = {'name': name, 'revision': revision, 'organization': organization}
        except ValueError:
            continue
        try:
            in_es = es_manager.document_exists(ESIndices.AUTOCOMPLETE, module)
            if in_es:
                continue

            es_missing_modules.append(key)
            module_raw = redis.get(redis_key)
            module = json.loads(module_raw or '{}')
            # Check if this file is in /var/yang/all_modules folder
            all_modules_path = '{}/{}@{}.yang'.format(save_file_dir, name, revision)
            if not os.path.isfile(all_modules_path):
                LOGGER.warning('Trying to retreive file content from Github for module {}'.format(key))
                modules_to_index_dict[key] = all_modules_path
                modules_to_index_list.append(module)
            else:
                modules_to_index_dict[key] = all_modules_path
                modules_to_index_list.append(module)
        except RequestError:
            incorrect_format_modules.append(key)
            LOGGER.exception('Problem with module {}@{}. SKIPPING'.format(name, revision))
            continue
        except Exception:
            continue

    # PHASE II: Check modules from Elasticsearch in Redis
    LOGGER.info('Starting PHASE II')
    all_es_modules = es_manager.match_all(ESIndices.AUTOCOMPLETE)
    result = check_module_in_redis(all_es_modules, redis)
    redis_missing_modules.extend(result)

    # Log results
    LOGGER.info('REDIS')
    LOGGER.info('Number of modules in Redis: {}'.format(redis_modules))
    LOGGER.info('Number of modules with incorrect format {}'.format(len(incorrect_format_modules)))
    LOGGER.info('Number of Redis modules missing in ES: {}'.format(len(es_missing_modules)))
    LOGGER.info('Number of missing modules which can be immediately indexed: {}'.format(len(modules_to_index_dict)))

    LOGGER.info('ELASTICSEARCH')
    LOGGER.info('Number of modules in Elasticsearch: {}'.format(len(all_es_modules)))
    LOGGER.info('Number of ES modules missing in Redis: {}'.format(len(redis_missing_modules)))

    result = {
        'es_missing_modules_list': es_missing_modules,
        'redis_missing_modules_list': redis_missing_modules,
        'incorrect_format_modules_list': incorrect_format_modules,
        'modules_to_index': modules_to_index_dict,
    }
    with open('{}/compared_databases.json'.format(temp_dir), 'w') as writer:
        json.dump(result, writer)
    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
