"""Populate maturity-level in yindex"""

import json
import os

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from redisConnections.redisConnection import RedisConnection
from utility import log
from utility.create_config import create_config

ES_CHUNK_SIZE = 100


def main():
    config = create_config()
    logger = log.get_logger(
        'populate_maturity_level_yindex',
        os.path.join(config.get('Directory-Section', 'logs'), 'sandbox.log'),
    )
    es_manager = ESManager()
    logger.info('Process started')
    for module_key, module in all_modules_generator():
        maturity_level = module.get('maturity-level')
        if (
            not maturity_level
            or (maturity_level and maturity_level.lower() == 'none')
            or not es_manager.document_exists(ESIndices.YINDEX, module)
        ):
            continue
        logger.info(f'Module: {module_key} has such maturity-level: {maturity_level}')
        query = {
            'query': {
                'bool': {
                    'must': [
                        {'term': {'module': module['name']}},
                        {'term': {'organization': module['organization']}},
                    ],
                },
            },
        }
        es_response = es_manager.generic_search(index=ESIndices.YINDEX, query=query, response_size=None)['hits']['hits']
        for result in es_response:
            doc_id = result['_id']
            logger.info(f'Setting {maturity_level} maturity-level to {doc_id}')
            es_manager.es.update(
                index=ESIndices.YINDEX.value,
                id=doc_id,
                body={'doc': {'maturity-level': maturity_level}},
                refresh='true',
            )
    es_manager.es.indices.refresh(index=ESIndices.YINDEX.value)
    logger.info('All modules are updated successfully')


def all_modules_generator():
    redis_connection = RedisConnection()
    for key in redis_connection.modulesDB.scan_iter():
        redis_key = key.decode('utf-8')
        if redis_key != 'modules-data' and ':' not in redis_key:
            yield redis_key, json.loads(redis_connection.get_module(redis_key))


if __name__ == '__main__':
    main()
