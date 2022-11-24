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

import os
import time
import uuid
from threading import Lock

from flask.globals import g, request
from flask.helpers import make_response
from flask.json import jsonify
from flask.wrappers import Response
from flask_cors import CORS
from werkzeug.exceptions import abort

import api.authentication.auth as auth
from api.cache.api_cache import cache
from api.my_flask import MyFlask
from api.views.admin.admin import bp as admin_bp
from api.views.admin.admin import ietf_auth
from api.views.errorHandlers.errorHandler import bp as error_handling_bp
from api.views.healthCheck.healthCheck import bp as healthcheck_bp
from api.views.notifications.notifications import bp as notifications_bp
from api.views.userSpecificModuleMaintenance.moduleMaintenance import bp as user_maintenance_bp
from api.views.yangSearch.yangSearch import bp as yang_search_bp
from api.views.ycJobs.ycJobs import bp as jobs_bp
from api.views.ycSearch.ycSearch import bp as search_bp

app = MyFlask(__name__)
app_config = app.config

app_config['OIDC_REDIRECT_URI'] = os.path.join(app_config.w_yangcatalog_api_prefix, 'admin/ping')
if app_config.g_is_prod:
    ietf_auth.init_app(app)

cache.init_app(app)

# Register blueprint(s)
app.register_blueprint(admin_bp)
app.register_blueprint(error_handling_bp, url_prefix='/api')
app.register_blueprint(user_maintenance_bp, url_prefix='/api')
app.register_blueprint(jobs_bp, url_prefix='/api')
app.register_blueprint(search_bp, url_prefix='/api')
app.register_blueprint(healthcheck_bp, url_prefix='/api/admin/healthcheck')
app.register_blueprint(yang_search_bp, url_prefix='/api/yang-search/v2')
app.register_blueprint(notifications_bp, url_prefix='/api/notifications')

CORS(app, supports_credentials=True)
# csrf = CSRFProtect(application)
# monitor(application)              # to monitor requests using prometheus
lock_for_load = Lock()


def create_response(body, status, headers=None):
    """Creates flask response that can be sent to sender.

    Arguments:
        :param body:    (str) Message body of the response
        :param status:  (int) Status code of the response
        :param headers: (list) List of tuples containing headers information
        :return:        (str) Response that can be returned.
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
            if special_id not in app.release_locked:
                continue
            code = app.response_waiting.status_code
            assert app.response_waiting.json
            body = app.response_waiting.json
            body['extra-info'] = 'this message was generated with previous reload-cache response'
            app.special_id_counter[special_id] -= 1
            if app.special_id_counter[special_id] == 0:
                app.special_id_counter.pop(special_id)
                app.release_locked.remove(special_id)
            return make_response(jsonify(body), code)
    elif lock_for_load.locked():
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
        app.logger.info('Cache loaded successfully')
        app.loading = False


def load_app_first_time():
    while app.redisConnection.get_module('yang-catalog@2018-04-03/ietf') == '{}':
        sec = 30
        app.logger.info('yang-catalog@2018-04-03 not loaded yet - waiting for {} seconds'.format(sec))
        time.sleep(sec)


load_app_first_time()
