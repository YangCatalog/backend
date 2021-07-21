# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
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

"""
This is an API script that holds several endpoints for
various usage. Contributors can use this for adding,
updating and deleting of the yang modules. For this they
need to sign up first and use their credentials. Their
credentials needs to be approved by one of the yangcatalog.org
admin users. Otherwise they will not be able to contribute to
the database.

All the users can read the metadata of the yangmodules at any time.
For this there is no need of credentials. They can search for specific
modules or filter out several modules by providing keywords in payload.

Finally there are endpoints that are used by automated jobs. These
jobs use basic or http signature authorization.

Documentation for all these endpoints can be found in
../documentation/source/index.html.md or on the yangcatalog.org/doc
website
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import collections
import errno
import grp
import json
import os
import pwd
import shutil
import sys
import threading
import time
import uuid
import stat
import logging
from datetime import datetime, timedelta
from threading import Lock

import requests
from flask import (Flask, Response, abort, jsonify, make_response, redirect,
                   request)
from flask.logging import default_handler
from flask_cors import CORS
from flask_oidc import OpenIDConnect, discovery

from api.authentication.auth import auth, get_password, hash_pw
from api.globalConfig import yc_gc
from api.views.errorHandlers.errorHandler import app as error_handling_app
from api.views.healthCheck.healthCheck import app as healthcheck_app
from api.views.userSpecificModuleMaintenace.moduleMaintanace import \
    app as user_maintenance_app
from api.views.yangSearch.yangSearch import app as yang_search_app
from api.views.ycJobs.ycJobs import app as jobs_app
from api.views.ycSearch.ycSearch import app as search_app


class MyFlask(Flask):

    def __init__(self, import_name):
        self.loading = True
        super(MyFlask, self).__init__(import_name)
        self.ys_set = 'set'
        self.waiting_for_reload = False
        self.response_waiting = None
        self.special_id = None
        self.special_id_counter = {}
        self.release_locked = []
        self.secret_key = yc_gc.secret_key
        self.permanent_session_lifetime = timedelta(minutes=20)

    def process_response(self, response):
        response = super().process_response(response)
        self.create_response_only_latest_revision(response)
        #self.create_response_with_yangsuite_link(response)

        try:
            if not 'admin' in request.path:
                application.logger.debug('after request response processing have {}'.format(request.special_id))
            if request.special_id != 0:
                if request.special_id not in self.release_locked:
                    self.release_locked.append(request.special_id)
                    self.response_waiting = response
                    self.waiting_for_reload = False
        except:
            pass
        return response

    def preprocess_request(self):
        super().preprocess_request()
        request.special_id = 0
        if not 'admin' in request.path:
           application.logger.info(request.path)
        if 'api/admin' in request.path and not 'api/admin/healthcheck' in request.path and not 'api/admin/ping' in request.path:
            application.logger.info('User logged in {}'.format(yc_gc.oidc.user_loggedin))
            if not yc_gc.oidc.user_loggedin and 'login' not in request.path:
                return abort(401, description='not yet Authorized')

    def create_response_only_latest_revision(self, response):
        if request.args.get('latest-revision'):
            if 'True' == request.args.get('latest-revision'):
                if response.data:
                        if sys.version_info >= (3, 4):
                            decoded_string = response.data.decode(encoding='utf-8', errors='strict')
                        else:
                            decoded_string = response.data
                        json_data = json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(decoded_string)
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
                        temp_module = None
                        i = 0
                        for mod in newlist:
                            name = mod['name']
                            if temp_module:
                                if temp_module['name'] == name:
                                    revisions = []
                                    mod['index'] = i
                                    year = int(temp_module['revision'].split('-')[0])
                                    month = int(temp_module['revision'].split('-')[1])
                                    day = int(temp_module['revision'].split('-')[2])
                                    try:
                                        revisions.append(datetime(year, month, day))
                                    except ValueError:
                                        if day == 29 and month == 2:
                                            revisions.append(datetime(year, month, 28))
                                    year = int(mod['revision'].split('-')[0])
                                    month = int(mod['revision'].split('-')[1])
                                    day = int(mod['revision'].split('-')[2])
                                    try:
                                        revisions.append(datetime(year, month, day))
                                    except ValueError:
                                        if day == 29 and month == 2:
                                            revisions.append(datetime(year, month, 28))
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
                    rp = requests.post('{}search-filter'.format(
                        yc_gc.yangcatalog_api_prefix), search_filter,
                        headers={
                            'Content-type': 'application/json',
                            'Accept': 'application/json'}
                    )
                    mo = rp.json()['yang-catalog:modules']['module'][0]
                    self.get_dependencies(mo, mods, inset)
                else:
                    rp = requests.get('{}search/name/{}'
                                      .format(yc_gc.yangcatalog_api_prefix,
                                              dep['name']))
                    if rp.status_code == 404:
                        continue
                    mo = rp.json()['yang-catalog:modules']['module']
                    revisions = []
                    for m in mo:
                        revision = m['revision']
                        year = int(revision.split('-')[0])
                        month = int(revision.split('-')[1])
                        day = int(revision.split('-')[2])
                        revisions.append(datetime(year, month, day))
                    latest = revisions.index(max(revisions))
                    inset.add(dep['name'])
                    mods.add('{}@{}.yang'.format(dep['name'],
                                                 mo[latest][
                                                     'revision']))
                    self.get_dependencies(mo[latest], mods, inset)

    def create_response_with_yangsuite_link(self, response):
        if request.headers.environ.get('HTTP_YANGSUITE'):
            if 'true' != request.headers.environ['HTTP_YANGSUITE']:
                return response
            if request.headers.environ.get('HTTP_YANGSET_NAME'):
                self.ys_set = request.headers.environ.get(
                    'HTTP_YANGSET_NAME').replace('/', '_')
        else:
            return response

        if response.data:
            json_data = json.loads(response.data)
        else:
            return response
        modules = None
        if json_data.get('yang-catalog:modules') is not None:
            if json_data.get('yang-catalog:modules').get('module') is not None:
                modules = json_data.get('yang-catalog:modules').get('module')
        elif json_data.get('module') is not None:
            modules = json_data.get('module')
        if modules:
            if len(modules) > 0:
                ys_dir = yc_gc.ys_users_dir

                id = uuid.uuid4().hex
                ys_dir += '/' + id + '/repositories/' + modules[0]['name'].lower()
                try:
                    os.makedirs(ys_dir)
                except OSError as e:
                    # be happy if someone already created the path
                    if e.errno != errno.EEXIST:
                        return 'Server error - could not create directory'
                mods = set()
                inset = set()
                if len(modules) == 1:
                    defmod = modules[0]['name']
                for mod in modules:
                    name = mod['name']
                    if name in inset:
                        continue
                    name += '@{}.yang'.format(mod['revision'])
                    mods.add(name)
                    inset.add(mod['name'])
                    self.get_dependencies(mod, mods, inset)
                if (('openconfig-interfaces' in inset
                    or 'ietf-interfaces' in inset)
                    and 'iana-if-type' not in inset):
                    resp = requests.get(
                        '{}search/name/iana-if-type?latest-revision=True'.format(yc_gc.yangcatalog_api_prefix),
                        headers={
                            'Content-type': 'application/json',
                            'Accept': 'application/json'})
                    name = '{}@{}.yang'.format(resp.json()[0]['name'],
                                               resp.json()[0]['revision'])
                    mods.add(name)
                    inset.add(resp.json()[0]['name'])
                    self.get_dependencies(resp.json()[0], mods, inset)

                modules = []
                for mod in mods:
                    if not os.path.exists(yc_gc.save_file_dir + '/' + mod):
                        continue
                    shutil.copy(yc_gc.save_file_dir + '/' + mod, ys_dir)
                    modules.append([mod.split('@')[0], mod.split('@')[1]
                                   .replace('.yang', '')])
                ys_dir = yc_gc.ys_users_dir
                ys_dir += '/' + id + '/yangsets'
                try:
                    os.makedirs(ys_dir)
                except OSError as e:
                    # be happy if someone already created the path
                    if e.errno != errno.EEXIST:
                        return 'Server error - could not create directory'
                json_set = {'owner': id,
                            'repository': id + '+' + defmod.split('@')[0],
                            'setname': defmod.split('@')[0],
                            'defmod': defmod.split('@')[0],
                            'modules': modules}

                with open(ys_dir + '/' + defmod.split('@')[0].lower(), 'w') as f:
                    f.write(json.dumps(json_set, indent=4))
                uid = pwd.getpwnam("yang").pw_uid
                gid = grp.getgrnam("yang-dev").gr_gid
                path = yc_gc.ys_users_dir + '/' + id
                for root, dirs, files in os.walk(path):
                    for momo in dirs:
                        os.chown(os.path.join(root, momo), uid, gid)
                    for momo in files:
                        os.chown(os.path.join(root, momo), uid, gid)
                os.chown(path, uid, gid)
                json_data['yangsuite-url'] = (
                    '{}yangsuite/{}'.format(yc_gc.yangcatalog_api_prefix, id))
                response.data = json.dumps(json_data)
                return response
            else:
                return response
        else:
            return response

application = MyFlask(__name__)
application.config["OIDC_CLIENT_SECRETS"] = "secrets_oidc.json"
application.config["OIDC_COOKIE_SECURE"] = False
application.config["OIDC_CALLBACK_ROUTE"] = "/api/admin/ping"
application.config["OIDC_SCOPES"] = ["openid", "email", "profile"]
application.config["OIDC_ID_TOKEN_COOKIE_NAME"] = "oidc_token"

# configure the logger
application.logger.removeHandler(default_handler)
file_name_path = '{}/yang.log'.format(yc_gc.logs_dir)
if os.path.isfile(file_name_path):
    exists = True
FORMAT = '%(asctime)-15s %(levelname)-8s %(filename)s api => %(message)s - %(lineno)d'
DATEFMT = '%Y-%m-%d %H:%M:%S'
handler = logging.FileHandler(file_name_path)
handler.setFormatter(logging.Formatter(FORMAT, DATEFMT))
application.logger.setLevel(logging.DEBUG)
application.logger.addHandler(handler)
if not exists:
    os.chmod(file_name_path, 0o664 | stat.S_ISGID)

application.logger.debug('API initialized at ' + yc_gc.yangcatalog_api_prefix)
application.logger.debug('Starting api')


def create_secrets(discovered_secrets: dict):
    """
    Create secrets object and fill with actual user information.
    Dump created secrets object into secrets_oidc.json file.
    :param discovered_secrets:  (dict) Information about the provided OpenID Provider

    :return: Returns created secrets object filled with information
    :rtype: dict
    """
    secrets = dict()
    secrets['web'] = dict()
    secrets['web']['auth_uri'] = discovered_secrets['authorization_endpoint']
    secrets['web']['token_uri'] = discovered_secrets['token_endpoint']
    secrets['web']['userinfo_uri'] = discovered_secrets['userinfo_endpoint']
    secrets['web']['redirect_uris'] = yc_gc.oidc_redirects
    secrets['web']['issuer'] = yc_gc.oidc_issuer
    secrets['web']['client_secret'] = yc_gc.oidc_client_secret
    secrets['web']['client_id'] = yc_gc.oidc_client_id

    with open('secrets_oidc.json', 'w') as f:
        json.dump(secrets, f)

    return secrets

def retry_OP_discovery():
    """
    Try to get information about the provided OpenID Provider in loop.
    This method is executed in two scenarios:
    I. discovered_secrets were loaded from Redis, because getting from OpenID Provider failed
    II. discovered_secrets is None because getting from OpenID Provider failed and Redis does not yet contain discovered_secrets
    """
    while True:
        try:
            discovered_secrets = discovery.discover_OP_information(yc_gc.oidc_issuer)
            create_secrets(discovered_secrets)
            yc_gc.redis.set('secrets-oidc', json.dumps(discovered_secrets))
            application.logger.info('OpenID Provider information discovered successfully')
            break
        except:
            application.logger.warning('OpenID Provider information discovery failed')
            time.sleep(30)
    return True

discovered = False
discovered_secrets = None
try:
    discovered_secrets = discovery.discover_OP_information(yc_gc.oidc_issuer)
    application.logger.info('OpenID Provider information discovered successfully')
    yc_gc.redis.set('secrets-oidc', json.dumps(discovered_secrets))
    discovered = True
    application.logger.debug('Newly OpenID Provider discovered information saved to cache')
except:
    data = yc_gc.redis.get('secrets-oidc')

    if data is not None:
        data = data.decode('utf-8')
        discovered_secrets = json.loads(data)
        application.logger.info('OpenID Provider information loaded from cache')

if discovered_secrets is not None:
    create_secrets(discovered_secrets)

yc_gc.oidc = OpenIDConnect(application)
from api.views.admin.admin import app as admin_app

# Register blueprint(s)
application.register_blueprint(admin_app)
application.register_blueprint(error_handling_app, url_prefix="/api")
application.register_blueprint(user_maintenance_app, url_prefix="/api")
application.register_blueprint(jobs_app, url_prefix="/api")
application.register_blueprint(search_app, url_prefix="/api")
application.register_blueprint(healthcheck_app, url_prefix="/api/admin/healthcheck")
application.register_blueprint(yang_search_app, url_prefix="/api/yang-search/v2")

CORS(application, supports_credentials=True)
#csrf = CSRFProtect(application)
# monitor(application)              # to monitor requests using prometheus
lock_for_load = Lock()

def make_cache(credentials, response, data=None):
    """After we delete or add modules we need to reload all the modules to the file
    for quicker search. This module is then loaded to the memory.
            Arguments:
                :param response: (str) Contains string 'work' which will be sent back if
                    everything went through fine
                :param credentials: (list) Basic authorization credentials - username, password
                    respectively
                :return 'work' if everything went through fine otherwise send back the reason
                    why it failed.
    """
    try:
        if data is None:
            data = ''
            while data is None or len(data) == 0 or data == 'None':
                application.logger.debug("Loading data from confd")
                path = '{}://{}:{}//restconf/data/yang-catalog:catalog'.format(yc_gc.protocol, yc_gc.confd_ip,
                                                                               yc_gc.confdPort)
                try:
                    data = requests.get(path, auth=(credentials[0], credentials[1]),
                                        headers={'Accept': 'application/yang-data+json'}).json()
                    data = json.dumps(data)
                    application.logger.debug("Data loaded and parsed to json from confd db successfully")
                except ValueError as e:
                    application.logger.warning('not valid json returned')
                    data = ''
                except Exception:
                    application.logger.warning('exception during loading data from confd')
                    data = None
                if data is None or len(data) == 0 or data == 'None' or data == '':
                    secs = 30
                    application.logger.info('Confd not started or does not contain any data. Waiting for {} secs before reloading'.format(secs))
                    time.sleep(secs)
        #application.logger.info('is uwsgy {} type {}'.format(is_uwsgi, type(is_uwsgi)))
        yc_gc.redis.set('all-catalog-data', data)
    except:
        e = sys.exc_info()[0]
        application.logger.error('Could not load json to cache. Error: {}'.format(e))
        return 'Server error - downloading cache', None
    return response, data


def create_response(body, status, headers=None):
    """Creates flask response that can be sent to sender.
            Arguments:
                :param body: (Str) Message body of the response
                :param status: (int) Status code of the response
                :param headers: (list) List of tuples containing headers information
                :return: Response that can be returned.
    """
    if headers is None:
        headers = []
    resp = Response(body, status=status)
    if headers:
        for item in headers:
            if item[0] == 'Content-Length' or 'Content-Encoding' in item[0]:
                continue
            resp.headers[item[0]] = item[1]

    return resp


@application.route('/', defaults={'path': ''})
@application.route('/<path:path>', methods=['PUT', 'POST', 'GET', 'DELETE', 'PATCH'])
def catch_all(path):
    """Catch all the rest api requests that are not supported"""
    return abort(404, description='Path "/{}" does not exist'.format(path))


@application.route('/api/yangsuite/<id>', methods=['GET'])
def yangsuite_redirect(id):
    local_ip = '127.0.0.1'
    if yc_gc.is_uwsgi:
        local_ip = 'ys.{}'.format(yc_gc.ip)
    return redirect('https://{}/yangsuite/ydk/aaa/{}'.format(local_ip, id))


@application.route('/api/load-cache', methods=['POST'])
@auth.login_required
def load_to_memory():
    """Load all the data populated to yang-catalog to memory.
            :return response to the request.
    """
    username = request.authorization['username']
    if username != 'admin':
        return abort(401, description='User must be admin')
    if get_password(username) != hash_pw(request.authorization['password']):
        return abort(401)
    load()
    return make_response(jsonify({'info': 'Success'}), 201)


def load():
    """Load to cache from confd all the data populated to yang-catalog."""
    if application.waiting_for_reload:
        special_id = application.special_id
        application.special_id_counter[special_id] += 1
        while True:
            time.sleep(5)
            application.logger.info('application wating for reload with id - {}'.format(special_id))
            if special_id in application.release_locked:
                code = application.response_waiting.status_code
                body = application.response_waiting.json
                body['extra-info'] = "this message was generated with previous reload-cache response"
                application.special_id_counter[special_id] -= 1
                if application.special_id_counter[special_id] == 0:
                    application.special_id_counter.pop(special_id)
                    application.release_locked.remove(special_id)
                return make_response(jsonify(body), code)
    else:
        if lock_for_load.locked():
            application.logger.info('application locked for reload')
            application.waiting_for_reload = True
            special_id = str(uuid.uuid4())
            request.special_id = special_id
            application.special_id = special_id
            application.special_id_counter[special_id] = 0
            application.logger.info('Special ids {}'.format(application.special_id_counter))
    with lock_for_load:
        application.logger.info('application not locked for reload')
        load_uwsgi_cache()
        application.logger.info("Cache loaded successfully")
        application.loading = False


def load_uwsgi_cache():
    response = 'work'
    response, data = make_cache(yc_gc.credentials, response)
    cat = json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(data)['yang-catalog:catalog']
    modules = cat['modules']
    vendors = cat.get('vendors', {})

    yc_gc.redis.set("modules-data", json.dumps(modules))
    yc_gc.redis.set("vendors-data", json.dumps(vendors))
    if len(modules) != 0:
        existing_keys = ["modules-data", "vendors-data", "all-catalog-data"]
        # recreate keys to redis if there are any
        for i, mod in enumerate(modules['module']):
            key = mod['name'] + '@' + mod['revision'] + '/' + mod['organization']
            existing_keys.append(key)
            value = json.dumps(mod)
            yc_gc.redis.set(key, value)
        list_to_delete_keys_from_redis = []
        for key in yc_gc.redis.scan_iter():
            if key.decode('utf-8') not in existing_keys:
                list_to_delete_keys_from_redis.append(key)
        if len(list_to_delete_keys_from_redis) != 0:
            yc_gc.redis.delete(*list_to_delete_keys_from_redis)

    if response != 'work':
        application.logger.error('Could not load or create cache')
        sys.exit(500)


def load_app_first_time():
    while yc_gc.redis.get('yang-catalog@2018-04-03/ietf') is None:
        sec = 5
        application.logger.info('yang-catalog@2018-04-03 not loaded yet waiting for {} seconds'.format(sec))
        time.sleep(sec)


load_app_first_time()
if not discovered:
    discovery_thread = threading.Thread(target=retry_OP_discovery, daemon=True)
    discovery_thread.start()
    discovered = True
