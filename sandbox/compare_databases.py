"""
This script loops through each key in the Redis database,
which means through each stored module,
and checks whether the necessary information about this module
is also in the Elasticsearch database.
If module is missing in Elasticsearch databes,
check if it is stored in all_modules folder,
and dump it in format which can be directly used to insert to
Elasticsearch.
"""
import argparse
import configparser as ConfigParser
import json
import sys
import os

import redis
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError


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


if __name__ == '__main__':
    config_path = '/etc/yangcatalog/yangcatalog.conf'
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    redis_host = config.get('DB-Section', 'redis-host', fallback='localhost')
    redis_port = config.get('DB-Section', 'redis-port', fallback='6379')
    es_aws = config.get('DB-Section', 'es-aws', fallback=False)
    es_host = config.get('DB-Section', 'es-host', fallback='localhost')
    es_port = config.get('DB-Section', 'es-port', fallback='9200')
    elk_credentials = config.get('Secrets-Section', 'elk-secret', fallback='').strip('"').split(' ')
    redis = redis.Redis(host=redis_host, port=redis_port)

    if es_aws == 'True':
        es_aws = True
        es = Elasticsearch([es_host], http_auth=(elk_credentials[0], elk_credentials[1]), scheme='https', port=443)
    else:
        es_aws = False
        es = Elasticsearch([{'host': '{}'.format(es_host), 'port': es_port}])

    es_missing_modules = []
    incorrect_format_modules = []
    modules_to_index = {}
    redis_modules = 0
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
                # Check if this file is in /var/yang/all_modules folder
                all_modules_path = '/var/yang/all_modules/{}@{}.yang'.format(name, revision)
                if os.path.isfile(all_modules_path):
                    modules_to_index[key] = all_modules_path

        except RequestError:
            incorrect_format_modules.append(key)
            print('Problem with module {}@{}. SKIPPING'.format(name, revision))
            continue
        except:
            continue

    print('Number of modules in Redis: {}'.format(redis_modules))
    print('Number of modules with incorrect format {}'.format(len(incorrect_format_modules)))
    print('Number of missing modules in ES: {}'.format(len(es_missing_modules)))
    print('Number of missing modules which can be immediately indexed: {}'.format(len(modules_to_index)))

    result = {}
    result['missing_modules_list'] = es_missing_modules
    result['incorrect_format_modules_list'] = incorrect_format_modules
    result['modules_to_index'] = modules_to_index
    with open('/var/yang/tmp/es_missing_modules.json', 'w') as f:
        json.dump(result, f)
