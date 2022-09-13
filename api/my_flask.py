import configparser
import json
import logging
import os
import threading
import time
from datetime import timedelta
from urllib.error import URLError

import flask
import requests
from flask.app import Flask
from flask.config import Config
from flask.globals import g, request
from flask.logging import default_handler
from flask_pyoidc.user_session import UserSession
from redis import Redis
from werkzeug.exceptions import abort

import api.authentication.auth as auth
from api.matomo_tracker import (MatomoTrackerData, get_headers_dict,
                                record_analytic)
from api.sender import Sender
from elasticsearchIndexing.es_manager import ESManager
from redisConnections.redisConnection import RedisConnection
from redisConnections.redis_users_connection import RedisUsersConnection
from utility.confdService import ConfdService
from utility.util import revision_to_date


class MyFlask(Flask):

    class MyConfig(Config):

        def __getattr__(self, name: str):
            try:
                return self[name.upper().replace('_', '-')]
            except KeyError:
                raise AttributeError(name)

    config_class = MyConfig
    config: MyConfig

    def __init__(self, import_name):
        self.loading = True
        super(MyFlask, self).__init__(import_name)
        self.ys_set = 'set'
        self.waiting_for_reload = False
        self.special_id = ''
        self.special_id_counter = {}
        self.release_locked = []
        self.permanent_session_lifetime = timedelta(minutes=20)
        self.load_config()
        self.logger.debug('API initialized at {}'.format(self.config.w_yangcatalog_api_prefix))
        self.logger.debug('Starting api')
        self.secret_key = self.config.s_flask_secret_key
        self.confdService = ConfdService()
        self.redisConnection = RedisConnection()

    def load_config(self):
        self.init_config()
        self.config.from_file(os.environ['YANGCATALOG_CONFIG_PATH'], load=self.config_reader)
        self.setup_logger()
        self.post_config_load()

    def config_reader(self, file):
        parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        parser.read(file.name)
        mapping = {}
        for section in parser.sections():
            section_prefix = ''.join((x for x in section.split('-')[0] if x.isupper()))
            for key, value in parser.items(section):
                key = '{}-{}'.format(section_prefix, key.upper())
                mapping[key] = value
        mapping['CONFIG-PARSER'] = parser
        return mapping

    def init_config(self):
        self.config['LOCK-UWSGI-CACHE1'] = threading.Lock()
        self.config['LOCK-UWSGI-CACHE2'] = threading.Lock()

    def setup_logger(self):
        self.logger.removeHandler(default_handler)
        file_name_path = '{}/yang.log'.format(self.config.d_logs)
        os.makedirs(os.path.dirname(file_name_path), exist_ok=True)
        FORMAT = '%(asctime)-15s %(levelname)-8s %(filename)s api => %(message)s - %(lineno)d'
        DATEFMT = '%Y-%m-%d %H:%M:%S'
        handler = logging.FileHandler(file_name_path)
        handler.setFormatter(logging.Formatter(FORMAT, DATEFMT))
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)
        if not os.path.isfile(file_name_path):
            os.chmod(file_name_path, 0o664)

    def post_config_load(self):
        self.config['S-ELK-CREDENTIALS'] = self.config.s_elk_secret.strip('"').split()
        self.config['S-CONFD-CREDENTIALS'] = self.config.s_confd_credentials.strip('"').split()
        self.config['ES-MANAGER'] = ESManager()

        rabbitmq_host = self.config.config_parser.get('RabbitMQ-Section', 'host', fallback='127.0.0.1')
        rabbitmq_port = int(self.config.config_parser.get('RabbitMQ-Section', 'port', fallback='5672'))
        rabbitmq_virtual_host = self.config.config_parser.get('RabbitMQ-Section', 'virtual-host', fallback='/')
        rabbitmq_username = self.config.config_parser.get('RabbitMQ-Section', 'username', fallback='guest')
        rabbitmq_password = self.config.config_parser.get('Secrets-Section', 'rabbitmq-password', fallback='guest')
        self.config['SENDER'] = Sender(
            self.config.d_logs, self.config.d_temp,
            rabbitmq_host=rabbitmq_host,
            rabbitmq_port=rabbitmq_port,
            rabbitmq_virtual_host=rabbitmq_virtual_host,
            rabbitmq_username=rabbitmq_username,
            rabbitmq_password=rabbitmq_password
        )

        self.config['G-IS-PROD'] = self.config.g_is_prod == 'True'
        self.config['REDIS'] = Redis(
            host=self.config.db_redis_host,
            port=self.config.db_redis_port
        )
        self.config['REDIS-USERS'] = RedisUsersConnection()
        auth.users = self.config.redis_users
        self.check_wait_redis_connected()

    def check_wait_redis_connected(self):
        while not self.config.redis.ping():
            time.sleep(5)
            self.logger.info('Waiting 5 seconds for redis to start')

    def process_response(self, response):
        response = super().process_response(response)
        self.create_response_only_latest_revision(response)

        try:
            if g.special_id != 0 and g.special_id not in self.release_locked:
                self.release_locked.append(g.special_id)
                self.response_waiting = response
                self.waiting_for_reload = False
        except AttributeError:
            pass
        return response

    def preprocess_request(self):
        super().preprocess_request()
        g.special_id = 0
        if not 'admin/' in request.path or not 'api/job/' in request.path:
            self.logger.info(request.path)
            client_ip = request.remote_addr
            data = MatomoTrackerData(self.config.m_matomo_api_url, self.config.m_matomo_site_id)
            headers_dict = get_headers_dict(request)
            try:
                record_analytic(headers_dict, data, client_ip)
            except URLError:
                self.logger.error('Unable to record API analytic')
        if 'api/admin' in request.path and not 'api/admin/healthcheck' in request.path and not 'api/admin/ping' in request.path:
            logged_in = UserSession(flask.session, 'default').is_authenticated()
            self.logger.info('User logged in {}'.format(logged_in))
            if self.config.g_is_prod and not logged_in and 'login' not in request.path:
                return abort(401, description='not yet Authorized')

    def create_response_only_latest_revision(self, response):
        if request.args.get('latest-revision'):
            if 'True' == request.args.get('latest-revision'):
                if response.data:
                    decoded_string = response.data.decode(encoding='utf-8', errors='strict')
                    json_data = json.loads(decoded_string)
                else:
                    return response
                modules = None
                if json_data.get('yang-catalog:modules') is not None:
                    if json_data.get('yang-catalog:modules').get(
                            'module') is not None:
                        modules = json_data.get('yang-catalog:modules').get(
                            'module')
                elif json_data.get('module') is not None:
                    modules = json_data.get('module')
                modules_to_remove = []
                if modules:
                    if len(modules) > 0:
                        newlist = sorted(modules, key=lambda k: k['name'])
                        temp_module = {}
                        i = 0
                        for mod in newlist:
                            name = mod['name']
                            if temp_module:
                                if temp_module['name'] == name:
                                    revisions = []
                                    mod['index'] = i
                                    revisions.append(revision_to_date(temp_module['revision']))
                                    revisions.append(revision_to_date(mod['revision']))
                                    latest = revisions.index(max(revisions))
                                    if latest == 0:
                                        modules_to_remove.append(mod['index'])
                                    elif latest == 1:
                                        modules_to_remove.append(temp_module['index'])
                                else:
                                    mod['index'] = i
                                    temp_module = mod
                            else:
                                mod['index'] = i
                                temp_module = mod
                            i += 1
                        for mod_to_remove in reversed(modules_to_remove):
                            newlist.remove(newlist[mod_to_remove])
                        for mod in newlist:
                            if mod.get('index'):
                                del mod['index']
                        response.data = json.dumps(newlist)

    def get_dependencies(self, mod, mods, inset):
        if mod.get('dependencies'):
            for dep in mod['dependencies']:
                if dep['name'] in inset:
                    continue
                if dep.get('revision'):
                    mods.add(dep['name'] + '@' + dep[
                        'revision'] + '.yang')
                    inset.add(dep['name'])
                    search_filter = json.dumps({
                        'input': {
                            'name': dep['name'],
                            'revision': dep['revision']
                        }
                    })
                    rp = requests.post('{}/search-filter'.format(
                        self.config.w_yangcatalog_api_prefix), search_filter,
                        headers={
                            'Content-type': 'application/json',
                            'Accept': 'application/json'}
                    )
                    mo = rp.json()['yang-catalog:modules']['module'][0]
                    self.get_dependencies(mo, mods, inset)
                else:
                    rp = requests.get('{}/search/name/{}'
                                      .format(self.config.w_yangcatalog_api_prefix,
                                              dep['name']))
                    if rp.status_code == 404:
                        continue
                    mo = rp.json()['yang-catalog:modules']['module']
                    revisions = [revision_to_date(m['revision']) for m in mo]
                    latest = revisions.index(max(revisions))
                    inset.add(dep['name'])
                    mods.add('{}@{}.yang'.format(dep['name'],
                                                 mo[latest][
                                                     'revision']))
                    self.get_dependencies(mo[latest], mods, inset)


app: MyFlask
