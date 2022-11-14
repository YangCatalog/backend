"""Reindex an Elasticsearch index."""

import argparse
import time

import utility.log as log
from elasticsearchIndexing.es_manager import ESManager
from utility.create_config import create_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=str, help='Source index with the old schema')
    parser.add_argument('dest', type=str, help='Target index with the updated schema')
    args = parser.parse_args()
    config = create_config()
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    logger = log.get_logger('reindex', '{}/sandbox.log'.format(log_directory))
    es = ESManager().es
    task_id = es.reindex(
        body={'source': {'index': args.source}, 'dest': {'index': args.dest}},
        wait_for_completion=False,
    )['task']
    while True:
        task_info = es.tasks.get(task_id=task_id)
        logger.info(f'{task_info["task"]["status"]["updated"]} out of {task_info["task"]["status"]["total"]}')
        if task_info['completed']:
            break
        time.sleep(10)
    logger.info('Updating by query completed')


if __name__ == '__main__':
    main()
