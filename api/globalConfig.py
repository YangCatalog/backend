# Copyright The IETF Trust 2020, All Rights Reserved
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

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright The IETF Trust 2020, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import time
from threading import Lock

import redis

from utility import log
from utility.create_config import create_config


class YangCatalogApiGlobalConfig:
    loading = True

    def __init__(self):
        self.lock_uwsgi_cache1 = Lock()
        self.lock_uwsgi_cache2 = Lock()
        self.load_config()

    def load_config(self):
        config = create_config()
        self.secret_key = config.get('Secrets-Section', 'flask-secret-key', fallback='S3CR3T!')
        self.nginx_dir = config.get('Directory-Section', 'nginx-conf', fallback='')
        self.result_dir = config.get('Web-Section', 'result-html-dir', fallback='tests/resources/html/results')
        self.private_dir = config.get('Web-Section', 'private-directory', fallback='tests/resources/html/private')
        self.register_user_email = config.get('Message-Section', 'email-to', fallback='')
        self.credentials = (
            config.get('Secrets-Section', 'confd-credentials', fallback='admin admin').strip('"').split(' ')
        )
        self.elk_credentials = config.get('Secrets-Section', 'elk-secret', fallback='').strip('"').split(' ')
        self.cache_dir = config.get('Directory-Section', 'cache', fallback='tests/resources/cache')
        self.save_requests = config.get('Directory-Section', 'save-requests', fallback='/var/yang/test-requests')
        self.save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
        self.var_yang = config.get('Directory-Section', 'var', fallback='/var/yang')
        self.logs_dir = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
        self.token = config.get('Secrets-Section', 'yang-catalog-token', fallback='')
        self.admin_token = config.get('Secrets-Section', 'admin-token', fallback='')
        self.oidc_client_secret = config.get('Secrets-Section', 'client-secret', fallback='')
        self.oidc_client_id = config.get('Secrets-Section', 'client-id', fallback='')
        self.commit_msg_file = config.get('Directory-Section', 'commit-dir', fallback='')
        self.temp_dir = config.get('Directory-Section', 'temp', fallback='tests/resources/tmp')
        self.diff_file_dir = config.get('Web-Section', 'save-diff-dir', fallback='tests/resources/html')
        self.ip = config.get('Web-Section', 'ip', fallback='localhost')
        self.oidc_redirects = config.get('Web-Section', 'redirect-oidc', fallback='').split(' ')
        self.oidc_issuer = config.get('Web-Section', 'issuer', fallback='')
        self.is_prod = config.get('General-Section', 'is-prod', fallback='False')
        self.is_uwsgi = config.get('General-Section', 'uwsgi', fallback=True)
        self.ys_users_dir = config.get('Directory-Section', 'ys-users', fallback='')
        self.my_uri = config.get('Web-Section', 'my-uri', fallback='http://localhost')
        self.yang_models = config.get(
            'Directory-Section',
            'yang-models-dir',
            fallback='tests/resources/yangmodels/yang',
        )
        self.es_host = config.get('DB-Section', 'es-host', fallback='localhost')
        self.es_port = config.get('DB-Section', 'es-port', fallback='9200')
        self.es_aws = config.get('DB-Section', 'es-aws', fallback=False)
        self.redis_host = config.get('DB-Section', 'redis-host', fallback='localhost')
        self.redis_port = config.get('DB-Section', 'redis-port', fallback='6379')
        self.json_ytree = config.get('Directory-Section', 'json-ytree', fallback='/var/yang/ytrees')
        self.yangcatalog_api_prefix = config.get(
            'Web-Section',
            'yangcatalog-api-prefix',
            fallback='http://localhost/api',
        )
        self.domain_prefix = config.get('Web-Section', 'domain-prefix', fallback='http://localhost')
        self.es_aws = self.es_aws == 'True'

        self.LOGGER = log.get_logger('api.yc_gc', '{}/yang.log'.format(self.logs_dir))

        self.LOGGER.info('yangcatalog configuration reloaded')
        self.redis = redis.Redis(host=self.redis_host, port=self.redis_port)  # pyright: ignore
        self.check_wait_redis_connected()

    def check_wait_redis_connected(self):
        while not self.redis.ping():
            time.sleep(5)
            self.LOGGER.info('Waiting 5 seconds for redis to start')


yc_gc = YangCatalogApiGlobalConfig()
