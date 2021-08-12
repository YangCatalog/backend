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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright The IETF Trust 2020, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import sys
import time
from threading import Lock

import redis
from elasticsearch import Elasticsearch
from flask_oidc import OpenIDConnect
from flask_sqlalchemy import SQLAlchemy
from utility import log

from api.sender import Sender

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


class YangCatalogApiGlobalConfig():
    loading = True

    def __init__(self):
        self.oidc = OpenIDConnect()
        self.sqlalchemy = SQLAlchemy(engine_options={'future': True})
        self.lock_uwsgi_cache1 = Lock()
        self.lock_uwsgi_cache2 = Lock()
        self.load_config()

    def load_config(self):
        self.config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(self.config_path)
        self.search_key = config.get('Secrets-Section', 'update-signature', fallback='')
        self.secret_key = config.get('Secrets-Section', 'flask-secret-key', fallback='S3CR3T!')
        self.nginx_dir = config.get('Directory-Section', 'nginx-conf', fallback='')
        self.result_dir = config.get('Web-Section', 'result-html-dir', fallback='tests/resources/html/results')
        self.private_dir = config.get('Web-Section', 'private-directory', fallback='tests/resources/html/private')
        self.dbHost = config.get('DB-Section', 'host', fallback='127.0.0.1')
        self.dbName = config.get('DB-Section', 'name-users', fallback='yang_catalog')
        self.dbNameSearch = config.get('DB-Section', 'name-search', fallback='yang')
        self.dbUser = config.get('DB-Section', 'user', fallback='yang')
        self.dbPass = config.get('Secrets-Section', 'mysql-password', fallback='pass')
        self.register_user_email = config.get('Message-Section', 'email-to', fallback='')
        self.credentials = config.get('Secrets-Section', 'confd-credentials', fallback='').strip('"').split(' ')
        self.elk_credentials = config.get('Secrets-Section', 'elk-secret', fallback='').strip('"').split(' ')
        self.confd_ip = config.get('Web-Section', 'confd-ip', fallback='yangcatalog.org')
        self.confdPort = int(config.get('Web-Section', 'confd-port', fallback=8008))
        self.protocol = config.get('General-Section', 'protocol-confd', fallback='http')
        self.cache_dir = config.get('Directory-Section', 'cache', fallback='tests/resources/cache')
        self.save_requests = config.get('Directory-Section', 'save-requests', fallback='tests/resources/requests')
        self.save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
        self.var_yang = config.get('Directory-Section', 'var', fallback='tests/resources')
        self.logs_dir = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
        self.token = config.get('Secrets-Section', 'yang-catalog-token', fallback='')
        self.admin_token = config.get('Secrets-Section', 'admin-token', fallback='')
        self.oidc_client_secret = config.get('Secrets-Section', 'client-secret', fallback='')
        self.oidc_client_id = config.get('Secrets-Section', 'client-id', fallback='')
        self.commit_msg_file = config.get('Directory-Section', 'commit-dir', fallback='')
        self.temp_dir = config.get('Directory-Section', 'temp', fallback='tests/resources/tmp')
        self.integrity_file_location = config.get('Web-Section', 'public-directory', fallback='tests/resources/html')
        self.diff_file_dir = config.get('Web-Section', 'save-diff-dir', fallback='tests/resources/html')
        self.ip = config.get('Web-Section', 'ip', fallback='localhost')
        self.oidc_redirects = config.get('Web-Section', 'redirect-oidc', fallback='').split(' ')
        self.oidc_issuer = config.get('Web-Section', 'issuer', fallback='')
        self.api_port = int(config.get('Web-Section', 'api-port', fallback=5000))
        self.api_protocol = config.get('General-Section', 'protocol-api', fallback='https')
        self.is_prod = config.get('General-Section', 'is-prod', fallback='False')
        self.is_uwsgi = config.get('General-Section', 'uwsgi', fallback=True)
        self.ys_users_dir = config.get('Directory-Section', 'ys-users', fallback='')
        self.my_uri = config.get('Web-Section', 'my-uri', fallback='http://localhost')
        self.yang_models = config.get('Directory-Section', 'yang-models-dir',
                                      fallback='tests/resources/yangmodels/yang')
        self.es_host = config.get('DB-Section', 'es-host', fallback='localhost')
        self.es_port = config.get('DB-Section', 'es-port', fallback='9200')
        self.es_aws = config.get('DB-Section', 'es-aws', fallback=False)
        self.redis_host = config.get('DB-Section', 'redis-host', fallback='localhost')
        self.redis_port = config.get('DB-Section', 'redis-port', fallback='6379')
        self.json_ytree = config.get('Directory-Section', 'json-ytree', fallback='/var/yang/ytrees')
        if self.es_aws == 'True':
            self.es_aws = True
        else:
            self.es_aws = False
        if self.es_aws:
            self.es = Elasticsearch([self.es_host], http_auth=(self.elk_credentials[0], self.elk_credentials[1]),
                                    scheme="https", port=443)
        else:
            self.es = Elasticsearch([{'host': '{}'.format(self.es_host), 'port': self.es_port}])

        rabbitmq_host = config.get('RabbitMQ-Section', 'host', fallback='127.0.0.1')
        rabbitmq_port = int(config.get('RabbitMQ-Section', 'port', fallback='5672'))
        rabbitmq_virtual_host = config.get('RabbitMQ-Section', 'virtual-host', fallback='/')
        rabbitmq_username = config.get('RabbitMQ-Section', 'username', fallback='guest')
        rabbitmq_password = config.get('Secrets-Section', 'rabbitMq-password', fallback='guest')
        self.LOGGER = log.get_logger('api.yc_gc', '{}/yang.log'.format(self.logs_dir))
        self.sender = Sender(self.logs_dir, self.temp_dir,
                             rabbitmq_host=rabbitmq_host,
                             rabbitmq_port=rabbitmq_port,
                             rabbitmq_virtual_host=rabbitmq_virtual_host,
                             rabbitmq_username=rabbitmq_username,
                             rabbitmq_password=rabbitmq_password
                             )
        separator = ':'
        suffix = self.api_port
        if self.is_uwsgi == 'True':
            separator = '/'
            suffix = 'api'
        self.yangcatalog_api_prefix = '{}://{}{}{}/'.format(self.api_protocol, self.ip, separator, suffix)
        self.LOGGER.info('yangcatalog configuration reloaded')
        self.redis = redis.Redis(
            host=self.redis_host,
            port=self.redis_port)
        self.check_wait_redis_connected()

    def check_wait_redis_connected(self):
        while not self.redis.ping():
            time.sleep(5)
            self.LOGGER.info("Waiting 5 seconds for redis to start")


yc_gc = YangCatalogApiGlobalConfig()
