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

import utility.log as log
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError
from redis import Redis
from utility.create_config import create_config
from utility.util import fetch_module_by_schema


def create_query(name: str, revision: str):
    query = \
        {
            "query": {
                "bool": {
                    "must": [{
                        "match_phrase": {
                             "module.keyword": {
                                 "query": name
                             }
                             }
                    }, {
                        "match_phrase": {
                            "revision": {
                                "query": revision
                            }
                        }
                    }]
                }
            }
        }

    return query


def check_module_in_redis(hits: list):
    redis_missing = []
    redis_missing_count = 0

    for hit in hits:
        modules = hit['_source']
        key = '{}@{}/{}'.format(modules['module'], modules['revision'], modules['organization'])
        data = redis.get(key)
        if data == '{}':
            redis_missing.append(key)
            redis_missing_count += 1

    LOGGER.info('{} out of {} missing in Redis'.format(redis_missing_count, len(hits)))

    return redis_missing


if __name__ == '__main__':
    config = create_config()
    redis_host = config.get('DB-Section', 'redis-host', fallback='localhost')
    redis_port = config.get('DB-Section', 'redis-port', fallback='6379')
    es_aws = config.get('DB-Section', 'es-aws', fallback=False)
    es_host = config.get('DB-Section', 'es-host', fallback='localhost')
    es_port = config.get('DB-Section', 'es-port', fallback='9200')
    elk_credentials = config.get('Secrets-Section', 'elk-secret', fallback='').strip('"').split(' ')
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    api_protocol = config.get('General-Section', 'protocol-api', fallback='http')
    ip = config.get('Web-Section', 'ip', fallback='localhost')
    api_port = int(config.get('Web-Section', 'api-port', fallback=5000))
    is_uwsgi = config.get('General-Section', 'uwsgi', fallback='True')
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')

    LOGGER = log.get_logger('sandbox', '{}/sandbox.log'.format(log_directory))

    # Create Redis and Elasticsearch connections
    redis = Redis(host=redis_host, port=redis_port, db=1)

    if es_aws == 'True':
        es_aws = True
        es = Elasticsearch([es_host], http_auth=(elk_credentials[0], elk_credentials[1]), scheme='https', port=443)
    else:
        es_aws = False
        es = Elasticsearch([{'host': '{}'.format(es_host), 'port': es_port}])

    # Set up variables and counters
    es_missing_modules = []
    redis_missing_modules = []
    incorrect_format_modules = []
    modules_to_index_dict = {}
    modules_to_index_list = []
    es_modules = 0
    redis_modules = 0

    # PHASE I: Check modules from Redis in Elasticsearch
    for key in redis.scan_iter():
        try:
            key = key.decode('utf-8')
            name = key.split('@')[0]
            revision = key.split('@')[1].split('/')[0]
            organization = key.split('@')[1].split('/')[1]
            redis_modules += 1

            query = create_query(name, revision)
            es_result = es.search(index='modules', doc_type='modules', body=query)

            if es_result['hits']['total'] == 0:
                es_missing_modules.append(key)
                module = json.loads(redis.get(key))
                # Check if this file is in /var/yang/all_modules folder
                all_modules_path = '{}/{}@{}.yang'.format(save_file_dir, name, revision)
                if not os.path.isfile(all_modules_path):
                    schema = module.get('schema')
                    LOGGER.warning('Trying to retreive file content from Github for module {}'.format(key))
                    result = fetch_module_by_schema(schema, all_modules_path)
                    if result:
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
    match_all = {
        "query": {
            "match_all": {}
        }
    }
    es_result = es.search(index='modules', doc_type='modules', body=match_all, scroll=u'10s', size=250)
    scroll_id = es_result.get('_scroll_id')
    hits = es_result['hits']['hits']
    es_modules += len(hits)
    result = check_module_in_redis(hits)
    redis_missing_modules.extend(result)

    while len(es_result['hits']['hits']):
        es_result = es.scroll(
            scroll_id=scroll_id,
            scroll=u'10s'
        )

        scroll_id = es_result.get('_scroll_id')
        hits = es_result['hits']['hits']
        es_modules += len(hits)
        result = check_module_in_redis(hits)
        redis_missing_modules.extend(result)

    es.clear_scroll(body={'scroll_id': [scroll_id]}, ignore=(404, ))

    # Log results
    LOGGER.info('REDIS')
    LOGGER.info('Number of modules in Redis: {}'.format(redis_modules))
    LOGGER.info('Number of modules with incorrect format {}'.format(len(incorrect_format_modules)))
    LOGGER.info('Number of Redis modules missing in ES: {}'.format(len(es_missing_modules)))
    LOGGER.info('Number of missing modules which can be immediately indexed: {}'.format(len(modules_to_index_dict)))

    LOGGER.info('ELASTICSEARCH')
    LOGGER.info('Number of modules in Elasticsearch: {}'.format(es_modules))
    LOGGER.info('Number of ES modules missing in Redis: {}'.format(len(redis_missing_modules)))

    result = {}
    result['es_missing_modules_list'] = es_missing_modules
    result['redis_missing_modules_list'] = redis_missing_modules
    result['incorrect_format_modules_list'] = incorrect_format_modules
    result['modules_to_index'] = modules_to_index_dict
    with open('{}/compared_databases.json'.format(temp_dir), 'w') as f:
        json.dump(result, f)
    LOGGER.info('Job finished successfully')
