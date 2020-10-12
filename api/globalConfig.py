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
from threading import Lock
import time

import redis

from api.sender import Sender
from utility import log

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

class YangCatalogApiGlobalConfig():

    loading = True

    def __init__(self):
        self.oidc = None
        self.config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(self.config_path)
        self.lock_uwsgi_cache1 = Lock()
        self.lock_uwsgi_cache2 = Lock()
        self.search_key = config.get('Secrets-Section', 'update-signature')
        self.secret_key = config.get('Secrets-Section', 'flask-secret-key')
        self.nginx_dir = config.get('Directory-Section', 'nginx-conf')
        self.result_dir = config.get('Web-Section', 'result-html-dir')
        self.dbHost = config.get('DB-Section', 'host')
        self.dbName = config.get('DB-Section', 'name-users')
        self.dbNameSearch = config.get('DB-Section', 'name-search')
        self.dbUser = config.get('DB-Section', 'user')
        self.dbPass = config.get('Secrets-Section', 'mysql-password')
        self.credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
        self.elk_credentials = config.get('Secrets-Section', 'elk-secret').strip('"').split(' ')
        self.confd_ip = config.get('Web-Section', 'confd-ip')
        self.confdPort = int(config.get('Web-Section', 'confd-port'))
        self.protocol = config.get('General-Section', 'protocol-confd')
        self.save_requests = config.get('Directory-Section', 'save-requests')
        self.save_file_dir = config.get('Directory-Section', 'save-file-dir')
        self.var_yang = config.get('Directory-Section', 'var')
        self.logs_dir = config.get('Directory-Section', 'logs')
        self.token = config.get('Secrets-Section', 'yang-catalog-token')
        self.admin_token = config.get('Secrets-Section', 'admin-token')
        self.oidc_client_secret = config.get('Secrets-Section', 'client-secret')
        self.oidc_client_id = config.get('Secrets-Section', 'client-id')
        self.commit_msg_file = config.get('Directory-Section', 'commit-dir')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.integrity_file_location = config.get('Web-Section', 'public-directory')
        self.diff_file_dir = config.get('Web-Section', 'save-diff-dir')
        self.ip = config.get('Web-Section', 'ip')
        self.oidc_redirects = config.get('Web-Section', 'redirect-oidc').split(' ')
        self.oidc_issuer = config.get('Web-Section', 'issuer')
        self.api_port = int(config.get('Web-Section', 'api-port'))
        self.api_protocol = config.get('General-Section', 'protocol-api')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        self.config_name = config.get('General-Section', 'repo-config-name')
        self.config_email = config.get('General-Section', 'repo-config-email')
        self.ys_users_dir = config.get('Directory-Section', 'ys-users')
        self.my_uri = config.get('Web-Section', 'my-uri')
        self.yang_models = config.get('Directory-Section', 'yang-models-dir')
        self.es_host = config.get('DB-Section', 'es-host')
        self.es_port = config.get('DB-Section', 'es-port')
        self.es_aws = config.get('DB-Section', 'es-aws')
        if self.es_aws == 'True':
            self.es_aws = True
        else:
            self.es_aws = False
        rabbitmq_host = config.get('RabbitMQ-Section', 'host', fallback='127.0.0.1')
        rabbitmq_port = int(config.get('RabbitMQ-Section', 'port', fallback='5672'))
        rabbitmq_virtual_host = config.get('RabbitMQ-Section', 'virtual-host', fallback='/')
        rabbitmq_username = config.get('RabbitMQ-Section', 'username', fallback='guest')
        rabbitmq_password = config.get('Secrets-Section', 'rabbitMq-password', fallback='guest')
        self.LOGGER = log.get_logger('api', self.logs_dir + '/yang.log')

        self.sender = Sender(self.logs_dir, self.temp_dir,
                             rabbitmq_host=rabbitmq_host,
                             rabbitmq_port=rabbitmq_port,
                             rabbitmq_virtual_host=rabbitmq_virtual_host,
                             rabbitmq_username=rabbitmq_username,
                             rabbitmq_password=rabbitmq_password,
                             )
        separator = ':'
        suffix = self.api_port
        if self.is_uwsgi == 'True':
            separator = '/'
            suffix = 'api'
        self.yangcatalog_api_prefix = '{}://{}{}{}/'.format(self.api_protocol, self.ip, separator, suffix)
        self.redis = redis.Redis(
            host='yc_redis_1',
            port=6379)
        self.check_wait_redis_connected()

    def load_config(self):
        self.config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(self.config_path)
        self.search_key = config.get('Secrets-Section', 'update-signature')
        self.secret_key = config.get('Secrets-Section', 'flask-secret-key')
        self.nginx_dir = config.get('Directory-Section', 'nginx-conf')
        self.result_dir = config.get('Web-Section', 'result-html-dir')
        self.dbHost = config.get('DB-Section', 'host')
        self.dbName = config.get('DB-Section', 'name-users')
        self.dbNameSearch = config.get('DB-Section', 'name-search')
        self.dbUser = config.get('DB-Section', 'user')
        self.dbPass = config.get('Secrets-Section', 'mysql-password')
        self.credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
        self.elk_credentials = config.get('Secrets-Section', 'elk-secret').strip('"').split(' ')
        self.oidc_client_secret = config.get('Secrets-Section', 'client-secret')
        self.oidc_client_id = config.get('Secrets-Section', 'client-id')
        self.confd_ip = config.get('Web-Section', 'confd-ip')
        self.confdPort = int(config.get('Web-Section', 'confd-port'))
        self.protocol = config.get('General-Section', 'protocol-confd')
        self.save_requests = config.get('Directory-Section', 'save-requests')
        self.save_file_dir = config.get('Directory-Section', 'save-file-dir')
        self.var_yang = config.get('Directory-Section', 'var')
        self.logs_dir = config.get('Directory-Section', 'logs')
        self.token = config.get('Secrets-Section', 'yang-catalog-token')
        self.admin_token = config.get('Secrets-Section', 'admin-token')
        self.commit_msg_file = config.get('Directory-Section', 'commit-dir')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.integrity_file_location = config.get('Web-Section', 'public-directory')
        self.diff_file_dir = config.get('Web-Section', 'save-diff-dir')
        self.ip = config.get('Web-Section', 'ip')
        self.api_port = int(config.get('Web-Section', 'api-port'))
        self.api_protocol = config.get('General-Section', 'protocol-api')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        self.config_name = config.get('General-Section', 'repo-config-name')
        self.config_email = config.get('General-Section', 'repo-config-email')
        self.ys_users_dir = config.get('Directory-Section', 'ys-users')
        self.my_uri = config.get('Web-Section', 'my-uri')
        self.oidc_redirects = config.get('Web-Section', 'redirect-oidc').split(' ')
        self.oidc_issuer = config.get('Web-Section', 'issuer')
        self.yang_models = config.get('Directory-Section', 'yang-models-dir')
        self.es_host = config.get('DB-Section', 'es-host')
        self.es_port = config.get('DB-Section', 'es-port')
        self.es_aws = config.get('DB-Section', 'es-aws')
        if self.es_aws == 'True':
            self.es_aws = True
        else:
            self.es_aws = False
        rabbitmq_host = config.get('RabbitMQ-Section', 'host', fallback='127.0.0.1')
        rabbitmq_port = int(config.get('RabbitMQ-Section', 'port', fallback='5672'))
        rabbitmq_virtual_host = config.get('RabbitMQ-Section', 'virtual-host', fallback='/')
        rabbitmq_username = config.get('RabbitMQ-Section', 'username', fallback='guest')
        rabbitmq_password = config.get('Secrets-Section', 'rabbitMq-password', fallback='guest')
        self.LOGGER = log.get_logger('api', self.logs_dir + '/yang.log')
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
            host='yc_redis_1',
            port=6379)
        self.check_wait_redis_connected()

    def check_wait_redis_connected(self):
        while not self.redis.ping():
            time.sleep(5)
            self.LOGGER.info("Waiting 5 seconds for redis to start")


yc_gc = YangCatalogApiGlobalConfig()
