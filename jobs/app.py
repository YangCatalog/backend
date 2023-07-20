import logging
import os

import requests
from celery import Celery

from redisConnections.redisConnection import RedisConnection
from utility import log
from utility.create_config import create_config
from utility.opensearch_util import ESIndexingPaths
from utility.staticVariables import json_headers


class BackendCeleryApp(Celery):
    logger: logging.Logger
    redis_connection: RedisConnection
    notify_indexing: bool
    save_file_dir: str
    yangcatalog_api_prefix: str
    indexing_paths: ESIndexingPaths
    confd_credentials: tuple[str, str]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_config()

    def load_config(self):
        config = create_config()
        log_directory = config.get('Directory-Section', 'logs')
        self.logger = log.get_logger('job_runner', os.path.join(log_directory, 'job_runner.log'))
        self.redis_connection = RedisConnection(config=config)
        self.notify_indexing = config.get('General-Section', 'notify-index') == 'True'
        self.save_file_dir = config.get('Directory-Section', 'save-file-dir')
        changes_cache_path = config.get('Directory-Section', 'changes-cache')
        delete_cache_path = config.get('Directory-Section', 'delete-cache')
        failed_changes_cache_path = config.get('Directory-Section', 'changes-cache-failed')
        lock_file = config.get('Directory-Section', 'lock')
        self.yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')
        self.indexing_paths = ESIndexingPaths(
            cache_path=changes_cache_path,
            deletes_path=delete_cache_path,
            failed_path=failed_changes_cache_path,
            lock_path=lock_file,
        )
        self.confd_credentials = tuple(config.get('Secrets-Section', 'confd-credentials').strip('"').split())
        self.logger.info('Config loaded succesfully')

    def reload_cache(self):
        requests.post(f'{self.yangcatalog_api_prefix}/load-cache', auth=self.confd_credentials, headers=json_headers)
