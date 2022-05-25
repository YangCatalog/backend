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

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import collections
import json
import os
import sys
import time
import uuid
from threading import Lock

from flask.globals import g, request
from flask.helpers import make_response
from flask.json import jsonify
from flask.wrappers import Response
from flask_cors import CORS
from werkzeug.exceptions import abort
from werkzeug.utils import redirect

import api.authentication.auth as auth
from api.my_flask import MyFlask
from api.views.admin.admin import bp as admin_bp
from api.views.admin.admin import ietf_auth
from api.views.errorHandlers.errorHandler import bp as error_handling_bp
from api.views.healthCheck.healthCheck import bp as healthcheck_bp
from api.views.userSpecificModuleMaintenance.moduleMaintenance import \
    bp as user_maintenance_bp
from api.views.yangSearch.yangSearch import bp as yang_search_bp
from api.views.ycJobs.ycJobs import bp as jobs_bp
from api.views.ycSearch.ycSearch import bp as search_bp

app = MyFlask(__name__)
ac = app.config

ac['OIDC_REDIRECT_URI'] = os.path.join(ac.w_yangcatalog_api_prefix, 'admin/ping')
if ac.g_is_prod:
    ietf_auth.init_app(app)

# Register blueprint(s)
app.register_blueprint(admin_bp)
app.register_blueprint(error_handling_bp, url_prefix='/api')
app.register_blueprint(user_maintenance_bp, url_prefix='/api')
app.register_blueprint(jobs_bp, url_prefix='/api')
app.register_blueprint(search_bp, url_prefix='/api')
app.register_blueprint(healthcheck_bp, url_prefix='/api/admin/healthcheck')
app.register_blueprint(yang_search_bp, url_prefix='/api/yang-search/v2')

CORS(app, supports_credentials=True)
# csrf = CSRFProtect(application)
# monitor(application)              # to monitor requests using prometheus
lock_for_load = Lock()


def make_cache(response, data=None):
    """ THIS METHOD IS DEPRECATED SINCE MOVING DATA FROM CONFD TO REDIS!
    After we delete or add modules we need to reload all the modules to the file
    for quicker search. This module is then loaded to the memory.
    Arguments:
        :param response: (str) Contains string 'work' which will be sent back if
            everything went through fine
        :return 'work' if everything went through fine otherwise send back the reason
            why it failed.
    """
    try:
        if data is None:
            data = ''
            while data is None or len(data) == 0 or data == 'None':
                app.logger.debug('Loading data from ConfD')
                try:
                    data = app.confdService.get_catalog_data().json()
                    data = json.dumps(data)
                    app.logger.debug('Data loaded and parsed to json from ConfD successfully')
                except ValueError as e:
                    app.logger.warning('not valid json returned')
                    data = ''
                except Exception:
                    app.logger.warning('exception during loading data from ConfD')
                    data = None
                if data is None or len(data) == 0 or data == 'None' or data == '':
                    secs = 30
                    app.logger.info('ConfD not started or does not contain any data. Waiting for {} secs before reloading'.format(secs))
                    time.sleep(secs)
    except Exception:
        e = sys.exc_info()[0]
        app.logger.exception('Could not load json to cache. Error: {}'.format(e))
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


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['PUT', 'POST', 'GET', 'DELETE', 'PATCH'])
def catch_all(path):
    """Catch all the rest api requests that are not supported"""
    return abort(404, description='Path "/{}" does not exist'.format(path))


@app.route('/api/yangsuite/<id>', methods=['GET'])
def yangsuite_redirect(id):
    local_ip = '127.0.0.1'
    if ac.g_uwsgi:
        local_ip = 'ys.{}'.format(ac.w_ip)
    return redirect('https://{}/yangsuite/ydk/aaa/{}'.format(local_ip, id))


@app.route('/api/load-cache', methods=['POST'])
@auth.auth.login_required
def load_to_memory():
    """Load all the data populated to yang-catalog to memory.
            :return response to the request.
    """
    assert request.authorization
    username = request.authorization['username']
    if username != 'admin':
        return abort(401, description='User must be admin')
    load()
    return ({'info': 'Success'}, 201)


def load():
    """Load modules data from Redis individual keys to modules-data"""
    if app.waiting_for_reload:
        special_id = app.special_id
        app.special_id_counter[special_id] += 1
        while True:
            time.sleep(5)
            app.logger.info('application wating for reload with id - {}'.format(special_id))
            if special_id in app.release_locked:
                code = app.response_waiting.status_code
                assert app.response_waiting.json
                body = app.response_waiting.json
                body['extra-info'] = 'this message was generated with previous reload-cache response'
                app.special_id_counter[special_id] -= 1
                if app.special_id_counter[special_id] == 0:
                    app.special_id_counter.pop(special_id)
                    app.release_locked.remove(special_id)
                return make_response(jsonify(body), code)
    else:
        if lock_for_load.locked():
            app.logger.info('Application locked for reload')
            app.waiting_for_reload = True
            special_id = str(uuid.uuid4())
            g.special_id = special_id
            app.special_id = special_id
            app.special_id_counter[special_id] = 0
            app.logger.info('Special ids {}'.format(app.special_id_counter))
    with lock_for_load:
        app.logger.info('Application not locked for reload')
        app.redisConnection.reload_modules_cache()
        app.redisConnection.reload_vendors_cache()
        # load_uwsgi_cache()
        app.logger.info('Cache loaded successfully')
        app.loading = False


def load_uwsgi_cache():
    """ THIS METHOD IS DEPRECATED SINCE MOVING DATA FROM CONFD TO REDIS!
    This method loads modules-data and vendors-data from ConfD and then set individual modules as keys
    into Redis database db=0.
    This method is no longer used since modules are now kept in Redis db=1.
    """
    response = 'work'
    response, data = make_cache(response)
    assert data, response
    cat = json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(data)['yang-catalog:catalog']
    modules = cat['modules']
    vendors = cat.get('vendors', {})

    ac.redis.set('modules-data', json.dumps(modules))
    ac.redis.set('vendors-data', json.dumps(vendors))
    if len(modules) != 0:
        existing_keys = ['modules-data', 'vendors-data', 'all-catalog-data']
        # recreate keys to redis if there are any
        for _, mod in enumerate(modules['module']):
            key = '{}@{}/{}'.format(mod['name'], mod['revision'], mod['organization'])
            existing_keys.append(key)
            value = json.dumps(mod)
            ac.redis.set(key, value)
        list_to_delete_keys_from_redis = []
        for key in ac.redis.scan_iter():
            if key.decode('utf-8') not in existing_keys:
                list_to_delete_keys_from_redis.append(key)
        if len(list_to_delete_keys_from_redis) != 0:
            ac.redis.delete(*list_to_delete_keys_from_redis)

    if response != 'work':
        app.logger.error('Could not load or create cache')
        sys.exit(500)


def load_app_first_time():
    while app.redisConnection.get_module('yang-catalog@2018-04-03/ietf') == '{}':
        sec = 30
        app.logger.info('yang-catalog@2018-04-03 not loaded yet - waiting for {} seconds'.format(sec))
        time.sleep(sec)


load_app_first_time()
