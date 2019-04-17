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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import base64
import collections
import errno
import grp
import hashlib
import json
import math
import os
import pwd
import re
import shutil
import subprocess
import sys
import uuid
from copy import deepcopy
from datetime import datetime
from threading import Lock

import MySQLdb
import jinja2
import requests
import uwsgi as uwsgi
from OpenSSL.crypto import FILETYPE_PEM, X509, load_publickey, verify
from flask import Flask, Response, abort, jsonify, make_response, redirect, request
from flask_cors import CORS
from flask_httpauth import HTTPBasicAuth
from flask_wtf.csrf import CSRFProtect
from pyang.plugins.tree import emit_tree

import api.yangSearch.elasticsearchIndex as inde
import utility.log as log
from api.sender import Sender
from utility import messageFactory, repoutil, yangParser
from utility.util import get_curr_dir
from utility.yangParser import create_context

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

url = 'https://github.com/'

github_api_url = 'https://api.github.com'
github_repos_url = github_api_url + '/repos'
yang_models_url = github_repos_url + '/YangModels/yang'

auth = HTTPBasicAuth()

class MyFlask(Flask):

    def __init__(self, import_name):
        self.loading = True
        super(MyFlask, self).__init__(import_name)
        self.response = None
        self.ys_set = 'set'

        config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(config_path)
        self.result_dir = config.get('Web-Section', 'result-html-dir')
        self.dbHost = config.get('DB-Section', 'host')
        self.dbName = config.get('DB-Section', 'name-users')
        self.dbNameSearch = config.get('DB-Section', 'name-search')
        self.dbUser = config.get('DB-Section', 'user')
        self.dbPass = config.get('DB-Section', 'password')
        self.credentials = config.get('General-Section', 'credentials').split(' ')
        self.confd_ip = config.get('General-Section', 'confd-ip')
        self.confdPort = int(config.get('General-Section', 'confd-port'))
        self.protocol = config.get('General-Section', 'protocol')
        self.save_requests = config.get('Directory-Section', 'save-requests')
        self.save_file_dir = config.get('Directory-Section', 'save-file-dir')
        self.token = config.get('API-Section', 'yang-catalog-token')
        self.admin_token = config.get('API-Section', 'admin-token')
        self.commit_msg_file = config.get('Directory-Section', 'commit-dir')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.integrity_file_location = config.get('API-Section',
                                             'integrity-file-location')
        self.diff_file_dir = config.get('Web-Section', 'save-diff-dir')
        self.ip = config.get('API-Section', 'ip')
        self.api_port = int(config.get('General-Section', 'api-port'))
        self.api_protocol = config.get('General-Section', 'protocol-api')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        self.config_name = config.get('General-Section', 'repo-config-name')
        self.config_email = config.get('General-Section', 'repo-config-email')
        self.ys_users_dir = config.get('Directory-Section', 'ys_users')
        self.my_uri = config.get('Web-Section', 'my_uri')
        self.yang_models = config.get('Directory-Section', 'yang_models_dir')
        self.es_host = config.get('DB-Section', 'es-host')
        self.es_port = config.get('DB-Section', 'es-port')
        self.es_protocol = config.get('DB-Section', 'es-protocol')
        self.rabbitmq_host = config.get('RabbitMQ-Section', 'host', fallback='127.0.0.1')
        self.rabbitmq_port = int(config.get('RabbitMQ-Section', 'port', fallback='5672'))
        self.rabbitmq_virtual_host = config.get('RabbitMQ-Section', 'virtual_host', fallback='/')
        self.rabbitmq_username = config.get('RabbitMQ-Section', 'username', fallback='guest')
        self.rabbitmq_password = config.get('RabbitMQ-Section', 'password', fallback='guest')
        log_directory = config.get('Directory-Section', 'logs')
        self.LOGGER = log.get_logger('api', log_directory + '/yang.log')
        self.LOGGER.debug('Starting API')
        self.sender = Sender(log_directory, self.temp_dir,
                             rabbitmq_host=self.rabbitmq_host,
                             rabbitmq_port=self.rabbitmq_port,
                             rabbitmq_virtual_host=self.rabbitmq_virtual_host,
                             rabbitmq_username=self.rabbitmq_username,
                             rabbitmq_password=self.rabbitmq_password,
        )
        separator = ':'
        suffix = self.api_port
        if self.is_uwsgi == 'True':
            separator = '/'
            suffix = 'api'
        self.yangcatalog_api_prefix = '{}://{}{}{}/'.format(self.api_protocol, self.ip, separator, suffix)
        self.LOGGER.debug('API initialized at ' + self.yangcatalog_api_prefix)

        self.LOGGER = log.get_logger('api', log_directory + '/yang.log')
        self.LOGGER.debug('Starting api')

    def process_response(self, response):
        response.headers['Access-Control-Allow-Headers'] = 'content-type'
        self.response = response
        self.create_response_only_latest_revision()
        self.create_response_with_yangsuite_link()

        self.LOGGER.debug(response.headers)
        return self.response

    def preprocess_request(self):
        if self.loading:
            message = json.dumps({'Error': 'Server is loading. This can take several minutes. Please try again later'})
            return create_response(message, 503)

    def create_response_only_latest_revision(self):
        if request.args.get('latest-revision'):
            if 'True' == request.args.get('latest-revision'):
                if self.response.data:
                        if sys.version_info >= (3, 4):
                            decoded_string = self.response.data.decode(encoding='utf-8', errors='strict')
                        else:
                            decoded_string = self.response.data
                        json_data = json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(decoded_string)
                else:
                    return self.response
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
                        self.response.data = json.dumps(newlist)

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
                        self.yangcatalog_api_prefix), search_filter,
                        headers={
                            'Content-type': 'application/json',
                            'Accept': 'application/json'}
                    )
                    mo = rp.json()['yang-catalog:modules']['module'][0]
                    self.get_dependencies(mo, mods, inset)
                else:
                    rp = requests.get('{}/search/name/{}'
                                      .format(self.yangcatalog_api_prefix,
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

    def create_response_with_yangsuite_link(self):
        if request.headers.environ.get('HTTP_YANGSUITE'):
            if 'true' != request.headers.environ['HTTP_YANGSUITE']:
                return self.response
            if request.headers.environ.get('HTTP_YANGSET_NAME'):
                self.ys_set = request.headers.environ.get(
                    'HTTP_YANGSET_NAME').replace('/', '_')
        else:
            return self.response

        if self.response.data:
            json_data = json.loads(self.response.data)
        else:
            return self.response
        modules = None
        if json_data.get('yang-catalog:modules') is not None:
            if json_data.get('yang-catalog:modules').get('module') is not None:
                modules = json_data.get('yang-catalog:modules').get('module')
        elif json_data.get('module') is not None:
            modules = json_data.get('module')
        if modules:
            if len(modules) > 0:
                ys_dir = self.ys_users_dir

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
                        '{}search/name/iana-if-type?latest-revision=True'.format(self.yangcatalog_api_prefix),
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
                    if not os.path.exists(self.save_file_dir + '/' + mod):
                        continue
                    shutil.copy(self.save_file_dir + '/' + mod, ys_dir)
                    modules.append([mod.split('@')[0], mod.split('@')[1]
                                   .replace('.yang', '')])
                ys_dir = self.ys_users_dir
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
                path = self.ys_users_dir + '/' + id
                for root, dirs, files in os.walk(path):
                    for momo in dirs:
                        os.chown(os.path.join(root, momo), uid, gid)
                    for momo in files:
                        os.chown(os.path.join(root, momo), uid, gid)
                os.chown(path, uid, gid)
                json_data['yangsuite-url'] = (
                    '{}/yangsuite/{}'.format(self.yangcatalog_api_prefix, id))
                self.response.data = json.dumps(json_data)
                return self.response
            else:
                return self.response
        else:
            return self.response


application = MyFlask(__name__)
CORS(application)
csrf = CSRFProtect(application)
# monitor(application)              # to monitor requests using prometheus
lock_uwsgi_cache1 = Lock()
lock_uwsgi_cache2 = Lock()
lock_for_load = Lock()

NS_MAP = {
    "http://cisco.com/": "cisco",
    "http://www.huawei.com/netconf": "huawei",
    "http://openconfig.net/yang": "openconfig",
    "http://tail-f.com/": "tail-f",
    "http://yang.juniper.net/": "juniper"
}

def make_cache(credentials, response, cache_chunks, main_cache, is_uwsgi=True, data=None):
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
            path = application.protocol + '://' + application.confd_ip + ':' + repr(application.confdPort) + '/api/config/catalog?deep'
            data = requests.get(path, auth=(credentials[0], credentials[1]),
                                headers={'Accept': 'application/vnd.yang.data+json'}).text

        if is_uwsgi == 'True':
            chunks = int(math.ceil(len(data)/float(64000)))
            for i in range(0, chunks, 1):
                uwsgi.cache_set('data{}'.format(i), data[i*64000: (i+1)*64000],
                                0, main_cache)
            application.LOGGER.info('all {} chunks are set in uwsgi cache'.format(chunks))
            uwsgi.cache_set('chunks-data', repr(chunks), 0, cache_chunks)
        else:
            return response, data
    except:
        e = sys.exc_info()[0]
        application.LOGGER.error('Could not load json to cache. Error: {}'.format(e))
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


@application.errorhandler(404)
def not_found():
    """Error handler for 404"""
    return make_response(jsonify({'error': 'Not found -- in api code'}), 404)


def authorize_for_sdos(request, organizations_sent, organization_parsed):
    """Authorize sender whether he has rights to send data via API to confd.
            Arguments:
                :param organization_parsed: (str) organization of a module sent by sender.
                :param organizations_sent: (str) organization of a module parsed from module.
                :param request: (request) Request sent to api.
                :return whether authorization passed.
    """
    username = request.authorization['username']
    application.LOGGER.info('Checking sdo authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=application.dbHost, db=application.dbName, user=application.dbUser, passwd=application.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        cursor.execute("SELECT * FROM `users`")
        data = cursor.fetchall()

        for row in data:
            if row[1] == username:
                accessRigths = row[7]
                break
        db.close()
    except MySQLdb.MySQLError as err:
        application.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))

    passed = False
    if accessRigths == '/':
        if organization_parsed != organizations_sent:
            return "module`s organization is not the same as organization provided"
        return True
    if organizations_sent in accessRigths:
        if organization_parsed != organizations_sent:
            return "module`s organization is not the same as organization provided"
        passed = True
    return passed


def authorize_for_vendors(request, body):
    """Authorize sender whether he has rights to send data via API to confd.
       Checks if sender has access on a given branch
                Arguments:
                    :param body: (str) json body of the request.
                    :param request: (request) Request sent to api.
                    :return whether authorization passed.
    """
    username = request.authorization['username']
    application.LOGGER.info('Checking vendor authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=application.dbHost, db=application.dbName, user=application.dbUser, passwd=application.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        cursor.execute("SELECT * FROM `users`")
        data = cursor.fetchall()

        for row in data:
            if row[1] == username:
                accessRigths = row[8]
                break
        db.close()
    except MySQLdb.MySQLError as err:
        application.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))

    rights = accessRigths.split('/')
    check_vendor = None
    check_platform = None
    check_software_version = None
    check_software_flavor = None
    if rights[1] is '':
        return 'passed'
    else:
        check_vendor = rights[1]
    if len(rights) > 2:
        check_platform = rights[2]
    if len(rights) > 3:
        check_software_version = rights[3]
    if len(rights) > 4:
        check_software_flavor = rights[4]

    for platform in body['platforms']['platform']:
        vendor = platform['vendor']
        platform_name = platform['name']
        software_version = platform['software-version']
        software_flavor = platform['software-flavor']

        if check_platform and platform_name != check_platform:
            return unauthorized()
        if check_software_version and software_version != check_software_version:
            return unauthorized()
        if check_software_flavor and software_flavor != check_software_flavor:
            return unauthorized()
        if vendor != check_vendor:
            return unauthorized()
    return 'passed'


@application.route('/', defaults={'path': ''})
@application.route('/<path:path>', methods=['PUT', 'POST', 'GET', 'DELETE', 'PATCH'])
def catch_all(path):
    """Catch all the rest api requests that are not supported"""
    return make_response(jsonify(
        {
            'error': 'Path "/{}" does not exist'.format(path)
        }), 400)


def check_authorized(signature, payload):
    """Convert the PEM encoded public key to a format palatable for pyOpenSSL,
    then verify the signature
            Arguments:
                :param signature: (str) Signature returned by sign function
                :param payload: (str) String that is encoded
    """
    response = requests.get('https://api.travis-ci.org/config', timeout=10.0)
    response.raise_for_status()
    public_key = response.json()['config']['notifications']['webhook']['public_key']
    pkey_public_key = load_publickey(FILETYPE_PEM, public_key)
    certificate = X509()
    certificate.set_pubkey(pkey_public_key)
    verify(certificate, base64.b64decode(signature), payload, str('SHA1'))


@application.route('/yangsuite/<id>', methods=['GET'])
def yangsuite_redirect(id):
    local_ip = '127.0.0.1'
    if application.is_uwsgi:
        local_ip = 'ys.{}'.format(application.ip)
    return redirect('https://{}/yangsuite/ydk/aaa/{}'.format(local_ip, id))


@auth.login_required
@application.route('/ietf', methods=['GET'])
def trigger_ietf_pull():
    username = request.authorization['username']
    if username != 'admin':
        return unauthorized
    job_id = application.sender.send('run_ietf')
    application.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'job-id': job_id}), 202)


@application.route('/checkComplete', methods=['POST'])
def check_local():
    """Authorize sender if it is Travis, if travis job was sent from yang-catalog
    repository and job passed fine and Travis run a job on pushed patch, create
    a pull request to YangModules repository. If the job passed on this pull request,
    merge the pull request and remove the repository at yang-catalog repository
            :return response to the request
    """
    application.LOGGER.info('Starting pull request job')
    body = json.loads(request.form['payload'])
    application.LOGGER.info('Body of travis {}'.format(json.dumps(body)))
    application.LOGGER.info('type of job {}'.format(body['type']))
    try:
        check_authorized(request.headers.environ['HTTP_SIGNATURE'], request.form['payload'])
        application.LOGGER.info('Authorization successful')
    except:
        application.LOGGER.critical('Authorization failed.'
                        ' Request did not come from Travis')
        mf = messageFactory.MessageFactory()
        mf.send_travis_auth_failed()
        return unauthorized()

    global yang_models_url

    verify_commit = False
    application.LOGGER.info('Checking commit SHA if it is the commit sent by yang-catalog'
                'user.')
    if body['repository']['owner_name'] == 'yang-catalog':
        commit_sha = body['commit']
    else:
        commit_sha = body['head_commit']
    try:
        with open(application.commit_msg_file, 'r') as commit_file:
            for line in commit_file:
                if commit_sha in line:
                    verify_commit = True
                    break
    except:
        return not_found()

    if verify_commit:
        application.LOGGER.info('commit verified')
        if body['repository']['owner_name'] == 'yang-catalog':
            if body['result_message'] == 'Passed':
                if body['type'] == 'push':
                    # After build was successful only locally
                    json_body = json.loads(json.dumps({
                        "title": "Cronjob - every day pull and update of ietf draft yang files.",
                        "body": "ietf extracted yang modules",
                        "head": "yang-catalog:master",
                        "base": "master"
                    }))

                    r = requests.post(yang_models_url + '/pulls',
                                      json=json_body, headers={'Authorization': 'token ' + application.token})
                    if r.status_code == requests.codes.created:
                        application.LOGGER.info('Pull request created successfully')
                        return make_response(jsonify({'info': 'Success'}), 201)
                    else:
                        application.LOGGER.error('Could not create a pull request {}'.format(r.status_code))
                        return make_response(jsonify({'Error': 'PR creation failed'}), 400)
            else:
                application.LOGGER.warning('Travis job did not pass. Removing forked repository.')
                requests.delete('https://api.github.com/repos/yang-catalog/yang',
                                headers={'Authorization': 'token ' + application.token})
                return make_response(jsonify({'info': 'Failed'}), 406)
        elif body['repository']['owner_name'] == 'YangModels':
            if body['result_message'] == 'Passed':
                if body['type'] == 'pull_request':
                    # If build was successful on pull request
                    pull_number = body['pull_request_number']
                    application.LOGGER.info('Pull request was successful {}. sending review.'.format(repr(pull_number)))
                    url = 'https://api.github.com/repos/YangModels/yang/pulls/'+ repr(pull_number) +'/reviews'
                    data = json.dumps({
                        'body': 'AUTOMATED YANG CATALOG APPROVAL',
                        'event': 'APPROVE'
                    })
                    response = requests.post(url, data, headers={'Authorization': 'token ' + application.admin_token})
                    application.LOGGER.info('review response code {}. Merge response {}.'.format(
                            response.status_code, response.text))
                    data = json.dumps({'commit-title': 'Travis job passed',
                                       'sha': body['head_commit']})
                    response = requests.put('https://api.github.com/repos/YangModels/yang/pulls/' + repr(pull_number) +
                                 '/merge', data, headers={'Authorization': 'token ' + application.admin_token})
                    application.LOGGER.info('Merge response code {}. Merge response {}.'.format(response.status_code, response.text))
                    requests.delete('https://api.github.com/repos/yang-catalog/yang',
                                    headers={'Authorization': 'token ' + application.token})
                    return make_response(jsonify({'info': 'Success'}), 201)
            else:
                application.LOGGER.warning('Travis job did not pass. Removing pull request')
                pull_number = body['pull_request_number']
                json_body = json.loads(json.dumps({
                    "title": "Cron job - every day pull and update of ietf draft yang files.",
                    "body": "ietf extracted yang modules",
                    "state": "closed",
                    "base": "master"
                }))
                requests.patch('https://api.github.com/repos/YangModels/yang/pulls/' + pull_number, json=json_body,
                               headers={'Authorization': 'token ' + application.token})
                application.LOGGER.warning(
                    'Travis job did not pass. Removing forked repository.')
                requests.delete(
                    'https://api.github.com/repos/yang-catalog/yang',
                    headers={'Authorization': 'token ' + application.token})
                return make_response(jsonify({'info': 'Failed'}), 406)
        else:
            application.LOGGER.warning('Owner name verification failed. Owner -> {}'
                           .format(body['repository']['owner_name']))
            return make_response(jsonify({'Error': 'Owner verfication failed'}),
                                 401)
    else:
        application.LOGGER.info('Commit verification failed. Commit sent by someone else.'
                    'Not doing anything.')
    return make_response(jsonify({'Error': 'Fails'}), 500)


@application.route('/modules/module/<name>,<revision>,<organization>', methods=['DELETE'])
@auth.login_required
def delete_module(name, revision, organization):
    """Delete a specific module defined with name, revision and organization. This is
    not done right away but it will send a request to receiver which will work on deleting
    while this request will send a job_id of the request which user can use to see the job
    process.
            Arguments:
                :param name: (str) name of the module
                :param revision: (str) revision of the module
                :param organization: (str) organization of the module
                :return response to the request with job_id that user can use to
                    see if the job is still on or Failed or Finished successfully
    """
    application.LOGGER.info('deleting module with name, revision and organization {} {} {}'.format(name, revision, organization))
    username = request.authorization['username']
    application.LOGGER.debug('Checking authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=application.dbHost, db=application.dbName, user=application.dbUser, passwd=application.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        cursor.execute("SELECT * FROM `users`")
        data = cursor.fetchall()

        for row in data:
            if row[1] == username:
                accessRigths = row[7]
                break
        db.close()
    except MySQLdb.MySQLError as err:
        application.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
    response = requests.get(application.protocol + '://' + application.confd_ip + ':' + repr(
        application.confdPort) + '/api/config/catalog/modules/module/' + name +
                            ',' + revision + ',' + organization,
                            auth=(application.credentials[0], application.credentials[1]),
                            headers={'Content-type': 'application/vnd.yang.data+json', 'Accept': 'application/vnd.yang.data+json'})
    if response.status_code != 200 or response.status_code != 201 or response.status_code != 204:
        return not_found()
    read = response.json()
    if read['yang-catalog:module']['organization'] != accessRigths and accessRigths != '/':
        return unauthorized()

    if read['yang-catalog:module'].get('implementations') is not None:
        return make_response(jsonify({'error': 'This module has reference in vendors branch'}), 400)

    path_to_delete = application.protocol + '://' + application.confd_ip + ':' + repr(application.confdPort) + '/api/config/catalog/modules/module/' \
                     + name + ',' + revision + ',' + organization

    arguments = [application.protocol, application.confd_ip, repr(application.confdPort), application.credentials[0],
                 application.credentials[1], path_to_delete, 'DELETE', application.api_protocol, repr(application.api_port)]
    job_id = application.sender.send('#'.join(arguments))

    application.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


@application.route('/modules', methods=['DELETE'])
@auth.login_required
def delete_modules():
    """Delete a specific modules defined with name, revision and organization. This is
    not done right away but it will send a request to receiver which will work on deleting
    while this request will send a job_id of the request which user can use to see the job
    process.
            Arguments:
                :return response to the request with job_id that user can use to
                    see if the job is still on or Failed or Finished successfully
    """
    if not request.json:
        abort(400)
    username = request.authorization['username']
    application.LOGGER.debug('Checking authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=application.dbHost, db=application.dbName, user=application.dbUser, passwd=application.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        cursor.execute("SELECT * FROM `users`")
        data = cursor.fetchall()

        for row in data:
            if row[1] == username:
                accessRigths = row[7]
                break
        db.close()
    except MySQLdb.MySQLError as err:
        application.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))

    rpc = request.json
    if rpc.get('input'):
        modules = rpc['input'].get('modules')
    else:
        return not_found()
    for mod in modules:
        response = requests.get(application.protocol + '://' + application.confd_ip + ':' + repr(application.confdPort) + '/api/config/catalog/modules/module/' + mod['name'] +
            ',' + mod['revision'] + ',' + mod['organization'],auth=(application.credentials[0], application.credentials[1]),
                        headers={'Content-type': 'application/vnd.yang.data+json', 'Accept': 'application/vnd.yang.data+json'})
        if response.status_code != 200 or response.status_code != 201 or response.status_code != 204:
            return not_found()
        read = response.json()

        if read['yang-catalog:module'][
            'organization'] != accessRigths and accessRigths != '/':
            return unauthorized()

        if read['yang-catalog:module'].get('implementations') is not None:
            return make_response(jsonify(
                {'error': 'This module has reference in vendors branch'}),
                                 400)

    path_to_delete = json.dumps(rpc['input'])

    arguments = [application.protocol, application.confd_ip, repr(application.confdPort), application.credentials[0],
                 application.credentials[1], path_to_delete, 'DELETE_MULTIPLE',
                 application.api_protocol, repr(application.api_port)]
    job_id = application.sender.send('#'.join(arguments))

    application.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


@application.route('/vendors/<path:value>', methods=['DELETE'])
@auth.login_required
def delete_vendor(value):
    """Delete a specific vendor defined with path. This is not done right away but it
    will send a request to receiver which will work on deleting while this request
    will send a job_id of the request which user can use to see the job
        process.
            Arguments:
                :param value: (str) path to the branch that needs to be deleted
                :return response to the request with job_id that user can use to
                    see if the job is still on or Failed or Finished successfully
    """
    application.LOGGER.info('Deleting vendor on path {}'.format(value))
    username = request.authorization['username']
    application.LOGGER.debug('Checking authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=application.dbHost, db=application.dbName, user=application.dbUser, passwd=application.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        cursor.execute("SELECT * FROM `users`")
        data = cursor.fetchall()

        for row in data:
            if row[1] == username:
                accessRigths = row[8]
                break
        db.close()
    except MySQLdb.MySQLError as err:
        application.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))

    rights = accessRigths.split('/')
    check_vendor = None
    check_platform = None
    check_software_version = None
    check_software_flavor = None
    if not rights[1] is '':
        check_vendor = rights[1]
        if len(rights) > 2:
            check_platform = rights[2]
        if len(rights) > 3:
            check_software_version = rights[3]
        if len(rights) > 4:
            check_software_flavor = rights[4]

    path_to_delete = application.protocol + '://' + application.confd_ip + ':' + repr(application.confdPort) + '/api/config/catalog/vendors/' \
                     + value + '?deep'

    vendor = 'None'
    platform = 'None'
    software_version = 'None'
    software_flavor = 'None'
    if '/vendor/' in path_to_delete:
        vendor = path_to_delete.split('?deep')[0].split('/vendor/')[1].split('/')[0]
    if '/platform/' in path_to_delete:
        platform = path_to_delete.split('?deep')[0].split('/platform/')[1].split('/')[0]
    if '/software-version/' in path_to_delete:
        software_version = path_to_delete.split('?deep')[0].split('/software-version/')[1].split('/')[0]
    if 'software-version/' in path_to_delete:
        software_flavor = path_to_delete.split('?deep')[0].split('/software-version/')[1].split('/')[0]

    if check_platform and platform != check_platform:
        return unauthorized()
    if check_software_version and software_version != check_software_version:
        return unauthorized()
    if check_software_flavor and software_flavor != check_software_flavor:
        return unauthorized()
    if check_vendor and vendor != check_vendor:
        return unauthorized()

    arguments = [vendor, platform, software_version, software_flavor, application.protocol, application.confd_ip, repr(application.confdPort), application.credentials[0],
                 application.credentials[1], path_to_delete, 'DELETE', application.api_protocol, repr(application.api_port)]
    job_id = application.sender.send('#'.join(arguments))

    application.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


@application.route('/modules', methods=['PUT', 'POST'])
@auth.login_required
def add_modules():
    """Add a new module. Use PUT request when we want to update every module there is
    in the request, use POST request if you want to create just modules that are not
    in confd yet. This is not done right away. First it checks if the request sent is
    ok and if it is, it will send a request to receiver which will work on deleting
    while this request will send a job_id of the request which user can use to see
    the job process.
            Arguments:
                :return response to the request with job_id that user can use to
                    see if the job is still on or Failed or Finished successfully
    """
    if not request.json:
        abort(400)
    body = request.json
    application.LOGGER.info('Adding modules with body {}'.format(body))
    tree_created = False

    with open('./prepare-sdo.json', "w") as plat:
        json.dump(body, plat)
    shutil.copy('./prepare-sdo.json', application.save_requests + '/sdo-'
                + str(datetime.utcnow()).split('.')[0].replace(' ', '_') + '-UTC.json')

    path = application.protocol + '://' + application.confd_ip + ':' + repr(application.confdPort) + '/api/config/modules'

    str_to_encode = '%s:%s' % (application.credentials[0], application.credentials[1])
    if sys.version_info >= (3, 4):
        str_to_encode = str_to_encode.encode(encoding='utf-8', errors='strict')
    base64string = base64.b64encode(str_to_encode)
    if sys.version_info >= (3, 4):
        base64string = base64string.decode(encoding='utf-8', errors='strict')
    response = requests.put(path, json.dumps(body), headers={'Authorization': 'Basic ' + base64string,
                                                             'Content-type': 'application/vnd.yang.data+json',
                                                             'Accept': 'application/vnd.yang.data+json'})

    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        return create_response(response.text, response.status_code, response.headers.items())
    repo = {}
    warning = []

    direc = 0
    while True:
        if os.path.isdir('{}/{}'.format(application.temp_dir, repr(direc))):
            direc += 1
        else:
            break
    direc = '{}/{}'.format(application.temp_dir, repr(direc))
    try:
        os.makedirs(direc)
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            raise
    application.LOGGER.info('{}'.format(body['modules']['module']))
    for mod in body['modules']['module']:
        application.LOGGER.info('{}'.format(mod))
        sdo = mod['source-file']
        orgz = mod['organization']
        if request.method == 'POST':
            path = application.protocol + '://' + application.confd_ip + ':' + repr(
                application.confdPort) + '/api/config/catalog/modules/module/' + \
                   mod['name'] + ',' + mod['revision'] + ',' + mod['organization']
            response = requests.get(path, auth=(application.credentials[0], application.credentials[1]),
                                    headers={'Accept':'application/vnd.yang.data+json'})
            if response.status_code != 404:
                continue

        directory = '/'.join(sdo['path'].split('/')[:-1])

        repo_url = url + sdo['owner'] + '/' + sdo['repository']
        application.LOGGER.debug('Cloning repository')
        if repo_url not in repo:
            application.LOGGER.info('Downloading repo {}'.format(repo_url))
            repo[repo_url] = repoutil.RepoUtil(repo_url)
            repo[repo_url].clone()
            repo[repo_url].updateSubmodule()

        if sdo.get('branch'):
            branch = sdo.get('branch')
        else:
            branch = 'master'
        save_to = direc + '/temp/' + sdo['owner'] + '/' + sdo['repository'].split('.')[0] \
                  + '/' + branch + '/' + directory
        try:
            os.makedirs(save_to)
        except OSError as e:
            # be happy if someone already created the path
            if e.errno != errno.EEXIST:
                raise
        shutil.copy(repo[repo_url].localdir + '/' + sdo['path'], save_to)

        tree_created = True
        organization = ''
        try:
            namespace = yangParser.parse(os.path.abspath(save_to + '/' + sdo['path'].split('/')[-1])) \
                .search('namespace')[0].arg

            for ns, org in NS_MAP.items():
                if ns in namespace:
                    organization = org
            if organization == '':
                if 'urn:' in namespace:
                    organization = namespace.split('urn:')[1].split(':')[0]
        except:
            while True:
                try:
                    belongs_to = yangParser.parse(os.path.abspath(repo[repo_url].localdir + '/' + sdo['path'])) \
                        .search('belongs-to')[0].arg
                except:
                    break
                try:
                    namespace = yangParser.parse(os.path.abspath(repo[repo_url].localdir + '/' + '/'.join(
                        sdo['path'].split('/')[:-1]) + '/' + belongs_to + '.yang')).search('namespace')[0].arg
                    for ns, org in NS_MAP.items():
                        if ns in namespace:
                            organization = org
                    if organization == '':
                        if 'urn:' in namespace:
                            organization = namespace.split('urn:')[1].split(':')[0]
                    break
                except:
                    pass
        resolved_authorization = authorize_for_sdos(request, orgz, organization)
        if not resolved_authorization:
            shutil.rmtree(direc)
            for key in repo:
                repo[key].remove()
            return unauthorized()
        if 'organization' in repr(resolved_authorization):
            warning.append(sdo['path'].split('/')[-1] + ' ' + resolved_authorization)

    if os.path.isfile('./prepare-sdo.json'):
        shutil.move('./prepare-sdo.json', direc)
    for key in repo:
        repo[key].remove()

    application.LOGGER.debug('Sending a new job')
    arguments = ["python", os.path.abspath("../parseAndPopulate/populate.py"), "--sdo", "--port",
                 repr(application.confdPort), "--dir", direc, "--api", "--ip",
                 application.confd_ip, "--credentials", application.credentials[0], application.credentials[1],
                 repr(tree_created), application.protocol, application.api_protocol, repr(application.api_port)]
    job_id = application.sender.send('#'.join(arguments))
    application.LOGGER.info('job_id {}'.format(job_id))
    if len(warning) > 0:
        return jsonify({'info': 'Verification successful', 'job-id': job_id, 'warnings': [{'warning': val}
                                                                                          for val in warning]})
    else:
        return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


@application.route('/platforms', methods=['PUT', 'POST'])
@auth.login_required
def add_vendors():
    """Add a new vendors. Use PUT request when we want to update every module there is
    in the request, use POST request if you want to create just modules that are not
    in confd yet. This is not done right away. First it checks if the request sent is
    ok and if it is, it will send a request to receiver which will work on deleting
    while this request will send a job_id of the request which user can use to see
    the job process.
            Arguments:
                :return response to the request with job_id that user can use to
                    see if the job is still on or Failed or Finished successfully
    """
    if not request.json:
        abort(400)
    body = request.json
    application.LOGGER.info('Adding vendor with body {}'.format(body))
    tree_created = False
    resolved_authorization = authorize_for_vendors(request, body)
    if 'passed' != resolved_authorization:
        return resolved_authorization
    with open(application.save_requests + '/vendor-' + str(datetime.utcnow()).split('.')[0].replace(' ', '_') +
              '-UTC.json', "w") as plat:
        json.dump(body, plat)

    path = application.protocol + '://' + application.confd_ip + ':' + repr(application.confdPort) + '/api/config/platforms'

    str_to_encode = '%s:%s' % (application.credentials[0], application.credentials[1])
    if sys.version_info >= (3, 4):
        str_to_encode = str_to_encode.encode(encoding='utf-8', errors='strict')
    base64string = base64.b64encode(str_to_encode)
    if sys.version_info >= (3, 4):
        base64string = base64string.decode(encoding='utf-8', errors='strict')
    response = requests.put(path, json.dumps(body), headers={'Authorization': 'Basic ' + base64string,
                                                             'Content-type': 'application/vnd.yang.data+json',
                                                             'Accept': 'application/vnd.yang.data+json'})

    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        return create_response(response.text, response.status_code, response.headers.items())

    repo = {}

    direc = 0
    while True:
        if os.path.isdir('{}/{}'.format(application.temp_dir, repr(direc))):
            direc += 1
        else:
            break
    direc = '{}/{}'.format(application.temp_dir, repr(direc))
    try:
        os.makedirs(direc)
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            raise
    for platform in body['platforms']['platform']:
        capability = platform['module-list-file']
        file_name = capability['path'].split('/')[-1]
        if request.method == 'POST':
            repo_split = capability['repository'].split('.')[0]
            repoutil.pull(application.yang_models)
            if os.path.isfile(application.yang_models + '/vendor/' + capability['owner'] + '/' + repo_split + '/' + capability['path']):
                continue

        repo_url = url + capability['owner'] + '/' + capability['repository']

        if repo_url not in repo:
            application.LOGGER.info('Downloading repo {}'.format(repo_url))
            repo[repo_url] = repoutil.RepoUtil(repo_url)
            repo[repo_url].clone()
            repo[repo_url].updateSubmodule()

        if capability.get('branch'):
            branch = capability.get('branch')
        else:
            branch = 'master'
        directory = '/'.join(capability['path'].split('/')[:-1])
        save_to = direc + '/temp/' + capability['owner'] + '/' \
                  + capability['repository'].split('.')[0] + '/' + branch + '/' + directory

        try:
            shutil.copytree(repo[repo_url].localdir + '/' + directory, save_to,
                            ignore=shutil.ignore_patterns('*.json', '*.xml', '*.sh', '*.md', '*.txt', '*.bin'))
        except OSError:
            pass
        with open(save_to + '/' + file_name.split('.')[0] + '.json', "w") as f:
            json.dump(platform, f)
        shutil.copy(repo[repo_url].localdir + '/' + capability['path'], save_to)
        tree_created = True

    for key in repo:
        repo[key].remove()
    arguments = ["python", os.path.abspath("../parseAndPopulate/populate.py"), "--port",
                 repr(application.confdPort), "--dir", direc, "--api", "--ip",
                 application.confd_ip, "--credentials", application.credentials[0], application.credentials[1],
                 repr(tree_created), application.integrity_file_location, application.protocol,
                 application.api_protocol, repr(application.api_port)]
    job_id = application.sender.send('#'.join(arguments))
    application.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


@application.route('/fast', methods=['POST'])
def fast_search():
    """Search through the YANG keyword index for a given search pattern.
       The arguments are a payload specifying search options and filters.
    """
    if not request.json:
        abort(400)

    limit = 1000000
    payload = request.json
    application.LOGGER.info(payload)
    if 'search' not in payload:
        return make_response(jsonify({'error': 'You must specify a "search" argument'}), 400)
    try:
        count = 0
        search_res, limit_reached = inde.do_search(payload, application.es_host,
                                    application.es_protocol, application.es_port,
                                    application.LOGGER)
        res = []
        found_modules = {}
        rejects = []
        not_founds = []

        for row in search_res:
            res_row = {}
            res_row['node'] = row['node']
            m_name = row['module']['name']
            m_revision = row['module']['revision']
            m_organization = row['module']['organization']
            mod_sig = '{}@{}/{}'.format(m_name, m_revision, m_organization)
            if mod_sig in rejects:
                continue

            mod_meta = None
            try:
                if mod_sig not in not_founds:
                    if mod_sig in found_modules:
                        mod_meta = found_modules[mod_sig]
                    else:
                        mod_meta = search_module(m_name, m_revision, m_organization)
                        if mod_meta.status_code == 404 and m_revision.endswith('02-28'):
                            mod_meta = search_module(m_name, m_revision.replace('02-28', '02-29'), m_organization)
                        if mod_meta.status_code == 404:
                            not_founds.append(mod_sig)
                            application.LOGGER.error('index search module {}@{} not found but exist in elasticsearch'.format(m_name, m_revision))
                            res_row = {'module': {'error': 'no {}@{} in API'.format(m_name, m_revision)}}
                            res.append(res_row)
                            continue
                        else:
                            mod_meta = mod_meta.json['module'][0]
                            found_modules[mod_sig] = mod_meta

                if 'include-mibs' not in payload or payload['include-mibs'] is False:
                    if re.search('yang:smiv2:', mod_meta.get('namespace')):
                        rejects.append(mod_sig)
                        continue

                if mod_meta is not None and 'yang-versions' in payload and len(payload['yang-versions']) > 0:
                    if mod_meta.get('yang-version') not in payload['yang-versions']:
                        rejects.append(mod_sig)
                        continue

                if mod_meta is not None:
                    if 'filter' not in payload or 'module-metadata' not in payload['filter']:
                        # If the filter is not specified, return all
                        # fields.
                        res_row['module'] = mod_meta
                    elif 'module-metadata' in payload['filter']:
                        res_row['module'] = {}
                        for field in payload['filter']['module-metadata']:
                            if field in mod_meta:
                                res_row['module'][field] = mod_meta[field]
            except Exception as e:
                count -= 1
                res_row['module'] = {
                    'error': 'Search failed at {}: {}'.format(mod_sig, e)}

            if not filter_using_api(res_row, payload):
                count += 1
                res.append(res_row)
            else:
                rejects.append(mod_sig)
            if count >= limit:
                break
        return jsonify({'results': res, 'limit_reched': limit_reached})
    except Exception as e:
        return make_response(jsonify({'error': str(e)}), 500)


def filter_using_api(res_row, payload):
    try:
        if 'filter' not in payload or 'module-metadata-filter' not in payload['filter']:
            reject = False
        else:
            reject = False
            keywords = payload['filter']['module-metadata-filter']
            for key, value in keywords.items():
                # Module doesn not contain such key as searched for, then reject
                if res_row['module'].get(key) is None:
                    reject = True
                    break
                if isinstance(res_row['module'][key], dict):
                    # This means the key is either implementations or ietf (for WG)
                    if key == 'implementations':
                        exists = True
                        if res_row['module'][key].get('implementations') is not None:
                            for val in value['implementation']:
                                val_found = False
                                for impl in res_row['module'][key]['implementations']['implementation']:
                                    vendor = impl.get('vendor')
                                    software_version = impl.get('software_version')
                                    software_flavor = impl.get('software_flavor')
                                    platform = impl.get('platform')
                                    os_version = impl.get('os_version')
                                    feature_set = impl.get('feature_set')
                                    os_type = impl.get('os_type')
                                    conformance_type = impl.get('conformance_type')
                                    local_exist = True
                                    if val.get('vendor') is not None:
                                        if vendor != val['vendor']:
                                            local_exist = False
                                    if val.get('software-version') is not None:
                                        if software_version != val['software-version']:
                                            local_exist = False
                                    if val.get('software-flavor') is not None:
                                        if software_flavor != val['software-flavor']:
                                            local_exist = False
                                    if val.get('platform') is not None:
                                        if platform != val['platform']:
                                            local_exist = False
                                    if val.get('os-version') is not None:
                                        if os_version != val['os-version']:
                                            local_exist = False
                                    if val.get('feature-set') is not None:
                                        if feature_set != val['feature-set']:
                                            local_exist = False
                                    if val.get('os-type') is not None:
                                        if os_type != val['os-type']:
                                            local_exist = False
                                    if val.get('conformance-type') is not None:
                                        if conformance_type != val['conformance-type']:
                                            local_exist = False
                                    if local_exist:
                                        val_found = True
                                        break
                                if not val_found:
                                    exists = False
                                    break
                            if not exists:
                                reject = True
                                break
                        else:
                            # No implementations that is searched for, reject
                            reject = True
                            break
                    elif key == 'ietf':
                        values = value.split(',')
                        reject = True
                        for val in values:
                            if res_row['module'][key].get('ietf-wg') is not None:
                                if res_row['module'][key]['ietf-wg'] == val['ietf-wg']:
                                    reject = False
                                    break
                        if reject:
                            break
                elif isinstance(res_row['module'][key], list):
                    # this means the key is either dependencies or dependents
                    exists = True
                    for val in value:
                        val_found = False
                        for dep in res_row['module'][key]:
                            name = dep.get('name')
                            rev = dep.get('revision')
                            schema = dep.get('schema')
                            local_exist = True
                            if val.get('name') is not None:
                                if name != val['name']:
                                    local_exist = False
                            if val.get('revision') is not None:
                                if rev != val['revision']:
                                    local_exist = False
                            if val.get('schema') is not None:
                                if schema != val['schema']:
                                    local_exist = False
                            if local_exist:
                                val_found = True
                                break
                        if not val_found:
                            exists = False
                            break
                    if not exists:
                        reject = True
                        break
                else:
                    # Module key has different value then serached for then reject
                    values = value.split(',')
                    reject = True
                    for val in values:
                        if res_row['module'].get(key) is not None:
                            if res_row['module'][key] == val:
                                reject = False
                                break
                    if reject:
                        break

        return reject
    except Exception as e:
        res_row['module'] = {'error': 'Metadata search failed with: {}'.format(e)}
        return False


@application.route('/search/<path:value>', methods=['GET'])
def search(value):
    """Search for a specific leaf from yang-catalog.yang module in modules
    branch. The key searched is defined in @module_keys variable.
            Arguments:
                :param value: (str) path that contains one of the @module_keys and
                    ends with /value searched for
                :return response to the request.
    """
    path = value
    application.LOGGER.info('Searching for {}'.format(value))
    split = value.split('/')[:-1]
    key = '/'.join(value.split('/')[:-1])
    value = value.split('/')[-1]
    module_keys = ['ietf/ietf-wg', 'maturity-level', 'document-name', 'author-email', 'compilation-status', 'namespace',
                   'conformance-type', 'module-type', 'organization', 'yang-version', 'name', 'revision', 'tree-type',
                   'belongs-to', 'generated-from', 'expires', 'expired', 'prefix', 'reference']
    for module_key in module_keys:
        if key == module_key:
            active_cache = get_active_cache()
            with active_cache[0]:
                data = modules_data(active_cache[1]).get('module')
            if data is None:
                return not_found()
            passed_data = []
            for module in data:
                count = -1
                process(module, passed_data, value, module, split, count)

            if len(passed_data) > 0:
                modules = json.JSONDecoder(object_pairs_hook=collections.OrderedDict) \
                    .decode(json.dumps(passed_data))
                return Response(json.dumps({
                    'yang-catalog:modules': {
                        'module': modules
                    }
                }), mimetype='application/json')
            else:
                return not_found()
    return Response(json.dumps({'error': 'Search on path {} is not supported'.format(path)})
                    , mimetype='application/json', status=400)


@application.route('/search-filter/<leaf>', methods=['POST'])
def rpc_search_get_one(leaf):
    rpc = request.json
    if rpc.get('input'):
        recursive = rpc['input'].get('recursive')
    else:
        return not_found()
    if recursive:
        rpc['input'].pop('recursive')
    response = rpc_search(rpc)
    modules = json.loads(response.get_data()).get('yang-catalog:modules')
    if modules is None:
        return not_found()
    modules = modules.get('module')
    if modules is None:
        return not_found()
    output = set()
    resolved = set()
    for module in modules:
        if recursive:
            search_recursive(output, module, leaf, resolved)
        meta_data = module.get(leaf)
        output.add(meta_data)
    if None in output:
        output.remove(None)
    if len(output) == 0:
        return not_found()
    else:
        return Response(json.dumps({'output': {leaf: list(output)}}),
                        mimetype='application/json', status=201)


def search_recursive(output, module, leaf, resolved):
    r_name = module['name']
    if r_name not in resolved:
        resolved.add(r_name)
        response = rpc_search({'input': {'dependencies': [{'name': r_name}]}})
        modules = json.loads(response.get_data()).get('yang-catalog:modules')
        if modules is None:
            return
        modules = modules.get('module')
        if modules is None:
            return
        for mod in modules:
            search_recursive(output, mod, leaf, resolved)
            meta_data = mod.get(leaf)
            output.add(meta_data)


@application.route('/services/tree/<f1>@<r1>.yang', methods=['GET'])
def create_tree(f1, r1):
    path_to_yang = '{}/{}@{}.yang'.format(application.save_file_dir, f1, r1)
    ctx = create_context('{}:{}'.format(application.yang_models, application.save_file_dir))
    with open(path_to_yang, 'r') as f:
        a = ctx.add_module(path_to_yang, f.read())
    if ctx.opts.tree_path is not None:
        path = ctx.opts.tree_path.split('/')
        if path[0] == '':
            path = path[1:]
    else:
        path = None
    with open('{}/pyang_temp.txt'.format(application.temp_dir), 'w')as f:
        emit_tree(ctx, [a], f, ctx.opts.tree_depth,
                  ctx.opts.tree_line_length, path)
    with open('{}/pyang_temp.txt'.format(application.temp_dir), 'r')as f:
        stdout = f.read()
    os.unlink('{}/pyang_temp.txt'.format(application.temp_dir))
    if stdout == '' and len(ctx.errors) != 0:
        return create_bootstrap_danger()
    elif stdout != '' and len(ctx.errors) != 0:
        return create_bootstrap_warning(stdout)
    elif stdout == '' and len(ctx.errors) == 0:
        return create_bootstrap_info()
    else:
        return '<html><body><pre>{}</pre></body></html>'.format(stdout)


@application.route('/services/reference/<f1>@<r1>.yang', methods=['GET'])
def create_reference(f1, r1):
    schema1 = '{}/{}@{}.yang'.format(application.save_file_dir, f1, r1)
    arguments = ['cat', schema1]
    cat = subprocess.Popen(arguments,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    stdout, stderr = cat.communicate()
    if sys.version_info >= (3, 4):
        stdout = stdout.decode(encoding='utf-8', errors='strict')
        stderr = stderr.decode(encoding='utf-8', errors='strict')
    if stdout == '' and stderr != '':
        return create_bootstrap_danger()
    elif stdout != '' and stderr != '':
        return create_bootstrap_warning(stdout)
    else:
        return '<html><body><pre>{}</pre></body></html>'.format(stdout)


def create_bootstrap_info():
    with open(get_curr_dir(__file__) + '/template/info.html', 'r') as f:
        template = f.read()
    return template


def create_bootstrap_warning(tree):
    application.LOGGER.info('Rendering bootstrap data')
    context = {'tree': tree}
    path, filename = os.path.split(
        get_curr_dir(__file__) + '/template/warning.html')
    return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')
                              ).get_template(filename).render(context)


def create_bootstrap_danger():
    with open(get_curr_dir(__file__) + '/template/danger.html', 'r') as f:
        template = f.read()
    return template


@application.route('/services/file1=<f1>@<r1>/check-update-from/file2=<f2>@<r2>',
           methods=['GET'])
def create_update_from(f1, r1, f2, r2):
    try:
        os.makedirs(get_curr_dir(__file__) + '/temp')
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            return 'Server error - could not create directory'
    schema1 = '{}/{}@{}.yang'.format(application.save_file_dir, f1, r1)
    schema2 = '{}/{}@{}.yang'.format(application.save_file_dir, f2, r2)
    arguments = ['pyang', '-p',
                 application.yang_models,
                 schema1, '--check-update-from',
                 schema2]
    pyang = subprocess.Popen(arguments,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    stdout, stderr = pyang.communicate()
    if sys.version_info >= (3, 4):
        stderr = stderr.decode(encoding='utf-8', errors='strict')
    return '<html><body><pre>{}</pre></body></html>'.format(stderr)


@application.route('/services/diff-file/file1=<f1>@<r1>/file2=<f2>@<r2>',
           methods=['GET'])
def create_diff_file(f1, r1, f2, r2):
    try:
        os.makedirs(get_curr_dir(__file__) + '/temp')
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            return 'Server error - could not create directory'
    schema1 = '{}/{}@{}.yang'.format(application.save_file_dir, f1, r1)
    schema2 = '{}/{}@{}.yang'.format(application.save_file_dir, f2, r2)

    arguments = ['cat', schema1]
    cat = subprocess.Popen(arguments, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    stdout, stderr = cat.communicate()
    if sys.version_info >= (3, 4):
        stdout = stdout.decode(encoding='utf-8', errors='strict')
    file_name1 = 'schema1-file-diff.txt'
    with open('{}/{}'.format(application.diff_file_dir, file_name1), 'w+') as f:
        f.write('<pre>{}</pre>'.format(stdout))
    arguments = ['cat', schema2]
    cat = subprocess.Popen(arguments, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    stdout, stderr = cat.communicate()
    if sys.version_info >= (3, 4):
        stdout = stdout.decode(encoding='utf-8', errors='strict')
    file_name2 = 'schema2-file-diff.txt'
    with open('{}/{}'.format(application.diff_file_dir, file_name2), 'w+') as f:
        f.write('<pre>{}</pre>'.format(stdout))
    tree1 = '{}/compatibility/{}'.format(application.my_uri, file_name1)
    tree2 = '{}/compatibility/{}'.format(application.my_uri, file_name2)
    diff_url = ('https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1={}&url2={}'
                .format(tree1, tree2))
    response = requests.get(diff_url)
    os.remove(application.diff_file_dir + '/' + file_name1)
    os.remove(application.diff_file_dir + '/' + file_name2)
    return '<html><body>{}</body></html>'.format(response.text)


@application.route('/services/diff-tree/file1=<f1>@<r1>/file2=<f2>@<r2>', methods=['GET'])
def create_diff_tree(f1, r1, f2, r2):
    try:
        os.makedirs(get_curr_dir(__file__) + '/temp')
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            return 'Server error - could not create directory'
    schema1 = '{}/{}@{}.yang'.format(application.save_file_dir, f1, r1)
    schema2 = '{}/{}@{}.yang'.format(application.save_file_dir, f2, r2)
    ctx = create_context('{}:{}'.format(application.yang_models, application.save_file_dir))
    ctx.lax_quote_checks = True
    ctx.lax_xpath_checks = True
    with open(schema1, 'r') as f:
        a = ctx.add_module(schema1, f.read())
    ctx.errors = []
    if ctx.opts.tree_path is not None:
        path = ctx.opts.tree_path.split('/')
        if path[0] == '':
            path = path[1:]
    else:
        path = None
    with open('{}/pyang_temp.txt'.format(application.temp_dir), 'w')as f:
        emit_tree(ctx, [a], f, ctx.opts.tree_depth,
                  ctx.opts.tree_line_length, path)
    with open('{}/pyang_temp.txt'.format(application.temp_dir), 'r')as f:
        stdout = f.read()
    file_name1 = 'schema1-tree-diff.txt'
    with open('{}/{}'.format(application.diff_file_dir, file_name1), 'w+') as f:
        f.write('<pre>{}</pre>'.format(stdout))
    with open(schema2, 'r') as f:
        a = ctx.add_module(schema2, f.read())
    with open('{}/pyang_temp.txt'.format(application.temp_dir), 'w')as f:
        emit_tree(ctx, [a], f, ctx.opts.tree_depth,
                  ctx.opts.tree_line_length, path)
    with open('{}/pyang_temp.txt'.format(application.temp_dir), 'r')as f:
        stdout = f.read()
    file_name2 = 'schema2-tree-diff.txt'
    with open('{}/{}'.format(application.diff_file_dir, file_name2), 'w+') as f:
        f.write('<pre>{}</pre>'.format(stdout))
    tree1 = '{}/compatibility/{}'.format(application.my_uri, file_name1)
    tree2 = '{}/compatibility/{}'.format(application.my_uri, file_name2)
    diff_url = ('https://www.ietf.org/rfcdiff/rfcdiff.pyht?url1={}&url2={}'
                .format(tree1, tree2))
    response = requests.get(diff_url)
    os.remove(application.diff_file_dir + '/' + file_name1)
    os.remove(application.diff_file_dir + '/' + file_name2)
    os.unlink('{}/pyang_temp.txt'.format(application.temp_dir))
    return '<html><body>{}</body></html>'.format(response.text)


@application.route('/get-common', methods=['POST'])
def get_common():
    body = request.json
    if body is None:
        return make_response(jsonify({'error': 'body of request is empty'}), 400)
    if body.get('input') is None:
        return make_response(jsonify
                             ({'error':
                                   'body of request need to start with input'}),
                             400)
    if body['input'].get('first') is None or body['input'].get('second') is None:
        return make_response(jsonify
                             ({'error':
                                   'body of request need to contain first and '
                                   'second container'}),
                             400)
    response_first = rpc_search({'input': body['input']['first']})
    response_second = rpc_search({'input': body['input']['second']})

    if response_first.status_code == 404 or response_second.status_code == 404:
        return not_found()

    data = json.JSONDecoder(object_pairs_hook=collections.OrderedDict)\
        .decode(response_first.get_data(as_text=True))
    modules_first = data['yang-catalog:modules']['module']
    data = json.JSONDecoder(object_pairs_hook=collections.OrderedDict)\
        .decode(response_second.get_data(as_text=True))
    modules_second = data['yang-catalog:modules']['module']

    output_modules_list = []
    names = []
    for mod_first in modules_first:
        for mod_second in modules_second:
            if mod_first['name'] == mod_second['name']:
                if mod_first['name'] not in names:
                    names.append(mod_first['name'])
                    output_modules_list.append(mod_first)
    if len(output_modules_list) == 0:
        return not_found()
    return Response(json.dumps({'output': output_modules_list}),
                    mimetype='application/json')


@application.route('/compare', methods=['POST'])
def compare():
    body = request.json
    if body is None:
        return make_response(jsonify({'error': 'body of request is empty'}), 400)
    if body.get('input') is None:
        return make_response(jsonify
                             ({'error':
                                   'body of request need to start with input'}),
                             400)
    if body['input'].get('old') is None or body['input'].get('new') is None:
        return make_response(jsonify
                             ({'error':
                                   'body of request need to contain new'
                                   ' and old container'}),
                             400)
    response_new = rpc_search({'input': body['input']['new']})
    response_old = rpc_search({'input': body['input']['old']})

    if response_new.status_code == 404 or response_old.status_code == 404:
        return not_found()

    data = json.loads(response_new.data)
    modules_new = data['yang-catalog:modules']['module']
    data = json.loads(response_old.data)
    modules_old = data['yang-catalog:modules']['module']

    new_mods = []
    for mod_new in modules_new:
        new_rev = mod_new['revision']
        new_name = mod_new['name']
        found = False
        new_rev_found = False
        for mod_old in modules_old:
            old_rev = mod_old['revision']
            old_name = mod_old['name']
            if new_name == old_name and new_rev == old_rev:
                found = True
                break
            if new_name == old_name and new_rev != old_rev:
                new_rev_found = True
        if not found:
            mod_new['reason-to-show'] = 'New module'
            new_mods.append(mod_new)
        if new_rev_found:
            mod_new['reason-to-show'] = 'Different revision'
            new_mods.append(mod_new)
    if len(new_mods) == 0:
        return not_found()
    output = {'output': new_mods}
    return make_response(jsonify(output), 200)


@application.route('/check-semantic-version', methods=['POST'])
#@cross_origin(headers='Content-Type')
def check_semver():
    body = request.json
    if body is None:
        return make_response(jsonify({'error': 'body of request is empty'}), 400)
    if body.get('input') is None:
        return make_response(jsonify
                             ({'error':
                                   'body of request need to start with input'}),
                             400)
    if body['input'].get('old') is None or body['input'].get('new') is None:
        return make_response(jsonify
                             ({'error':
                                   'body of request need to contain new'
                                   ' and old container'}),
                             400)
    response_new = rpc_search({'input': body['input']['new']})
    response_old = rpc_search({'input': body['input']['old']})

    if response_new.status_code == 404 or response_old.status_code == 404:
        return not_found()

    data = json.loads(response_new.data)
    modules_new = data['yang-catalog:modules']['module']
    data = json.loads(response_old.data)
    modules_old = data['yang-catalog:modules']['module']

    output_modules_list = []
    for mod_old in modules_old:
        name_new = None
        semver_new = None
        revision_new = None
        status_new = None
        name_old = mod_old['name']
        revision_old = mod_old['revision']
        organization_old = mod_old['organization']
        status_old = mod_old['compilation-status']
        for mod_new in modules_new:
            name_new = mod_new['name']
            revision_new = mod_new['revision']
            organization_new = mod_new['organization']
            status_new = mod_new['compilation-status']
            if name_new == name_old and organization_new == organization_old:
                if revision_old == revision_new:
                    break
                semver_new = mod_new.get('derived-semantic-version')
                break
        if semver_new:
            semver_old = mod_old.get('derived-semantic-version')
            if semver_old:
                if semver_new != semver_old:
                    output_mod = {}
                    if status_old != 'passed' and status_new != 'passed':
                        reason = 'Both modules failed compilation'
                    elif status_old != 'passed' and status_new == 'passed':
                        reason = 'Older module failed compilation'
                    elif status_new != 'passed' and status_old == 'passed':
                        reason = 'Newer module failed compilation'
                    else:
                        file_name = ('{}/services/file1={}@{}/check-update-from/file2={}@{}'
                                     .format(application.yangcatalog_api_prefix, name_new,
                                             revision_new, name_old,
                                             revision_old))
                        reason = ('pyang --check-update-from output: {}'.
                                  format(file_name))

                    diff = (
                        '{}/services/diff-tree/file1={}@{}/file2={}@{}'.
                            format(application.yangcatalog_api_prefix, name_old,
                                   revision_old, name_new, revision_new))

                    output_mod['yang-module-pyang-tree-diff'] = diff

                    output_mod['name'] = name_old
                    output_mod['revision-old'] = revision_old
                    output_mod['revision-new'] = revision_new
                    output_mod['organization'] = organization_old
                    output_mod['old-derived-semantic-version'] = semver_old
                    output_mod['new-derived-semantic-version'] = semver_new
                    output_mod['derived-semantic-version-results'] = reason
                    diff = ('{}/services/diff-file/file1={}@{}/file2={}@{}'
                            .format(application.yangcatalog_api_prefix, name_old,
                                    revision_old, name_new, revision_new))
                    output_mod['yang-module-diff'] = diff
                    output_modules_list.append(output_mod)
    if len(output_modules_list) == 0:
        return not_found()
    output = {'output': output_modules_list}
    return make_response(jsonify(output), 200)


@application.route('/search-filter', methods=['POST'])
def rpc_search(body=None):
    if body is None:
        body = request.json
    application.LOGGER.info('Searching and filtering modules based on RPC {}'
                .format(json.dumps(body)))
    active_cache = get_active_cache()
    with active_cache[0]:
        data = modules_data(active_cache[1])['module']
    body = body.get('input')
    if body:
        partial = body.get('partial')
        if partial is None:
            partial = False
        passed_modules = []
        if partial:
            for module in data:
                passed = True
                if 'dependencies' in body:
                    submodules = deepcopy(module.get('dependencies'))
                    if submodules is None:
                        continue
                    for sub in body['dependencies']:
                        found = True
                        name = sub.get('name')
                        revision = sub.get('revision')
                        schema = sub.get('schema')
                        for submodule in submodules:
                            found = True
                            if name:
                                if name not in submodule['name']:
                                    found = False
                            if not found:
                                continue
                            if revision:
                                if revision not in submodule['revision']:
                                    found = False
                            if not found:
                                continue
                            if schema:
                                if schema not in submodule['schema']:
                                    found = False
                            if found:
                                break

                        if not found:
                            passed = False
                            break
                if not passed:
                    continue
                if 'dependents' in body:
                    submodules = deepcopy(module.get('dependents'))
                    if submodules is None:
                        continue
                    for sub in body['dependents']:
                        found = True
                        name = sub.get('name')
                        revision = sub.get('revision')
                        schema = sub.get('schema')
                        for submodule in submodules:
                            found = True
                            if name:
                                if name not in submodule['name']:
                                    found = False
                            if not found:
                                continue
                            if revision:
                                if revision not in submodule['revision']:
                                    found = False
                            if not found:
                                continue
                            if schema:
                                if schema not in submodule['schema']:
                                    found = False
                            if found:
                                break

                        if not found:
                            passed = False
                            break
                if not passed:
                    continue
                if 'submodule' in body:
                    submodules = deepcopy(module.get('submodule'))
                    if submodules is None:
                        continue
                    for sub in body['submodule']:
                        found = True
                        name = sub.get('name')
                        revision = sub.get('revision')
                        schema = sub.get('schema')
                        for submodule in submodules:
                            found = True
                            if name:
                                if name not in submodule['name']:
                                    found = False
                            if not found:
                                continue
                            if revision:
                                if revision not in submodule['revision']:
                                    found = False
                            if not found:
                                continue
                            if schema:
                                if schema not in submodule['schema']:
                                    found = False
                            if found:
                                break

                        if not found:
                            passed = False
                            break
                if not passed:
                    continue
                if 'implementations' in body:
                    implementations = deepcopy(module.get('implementations'))
                    if implementations is None:
                        continue
                    passed = True
                    for imp in body['implementations']['implementation']:
                        if not passed:
                            break
                        for leaf in imp:
                            found = False
                            impls = []
                            if leaf == 'deviation':
                                for implementation in implementations[
                                    'implementation']:
                                    deviations = implementation.get('deviation')
                                    if deviations is None:
                                        continue
                                    for dev in imp[leaf]:
                                        found = True
                                        name = dev.get('name')
                                        revision = dev.get('revision')
                                        for deviation in deviations:
                                            found = True
                                            if name:
                                                if name not in deviation['name']:
                                                    found = False
                                            if not found:
                                                continue
                                            if revision:
                                                if revision not in deviation['revision']:
                                                    found = False
                                            if found:
                                                break
                                        if not found:
                                            break
                                    if not found:
                                        continue
                                    else:
                                        impls.append(implementation)
                                if not found:
                                    passed = False
                                    break
                            elif leaf == 'feature':
                                for implementation in implementations['implementation']:
                                    if implementation.get(leaf) is None:
                                        continue
                                    if imp[leaf] in implementation[leaf]:
                                        found = True
                                        impls.append(implementation)
                                        continue
                                if not found:
                                    passed = False
                            else:
                                for implementation in implementations['implementation']:
                                    if implementation.get(leaf) is None:
                                        continue
                                    if imp[leaf] in implementation[leaf]:
                                        found = True
                                        impls.append(implementation)
                                        continue
                                if not found:
                                    passed = False
                            if not passed:
                                break
                            implementations['implementation'] = impls
                if not passed:
                    continue
                for leaf in body:
                    if leaf != 'implementations' and leaf != 'submodule':
                        module_leaf = module.get(leaf)
                        if module_leaf:
                            if body[leaf] not in module_leaf:
                                passed = False
                                break
                if passed:
                    passed_modules.append(module)
        else:
            for module in data:
                passed = True
                if 'dependencies' in body:
                    submodules = deepcopy(module.get('dependencies'))
                    if submodules is None:
                        continue
                    for sub in body['dependencies']:
                        found = True
                        name = sub.get('name')
                        revision = sub.get('revision')
                        schema = sub.get('schema')
                        for submodule in submodules:
                            found = True
                            if name:
                                if name != submodule['name']:
                                    found = False
                            if not found:
                                continue
                            if revision:
                                if revision != submodule['revision']:
                                    found = False
                            if not found:
                                continue
                            if schema:
                                if schema != submodule['schema']:
                                    found = False
                            if found:
                                break

                        if not found:
                            passed = False
                            break
                if not passed:
                    continue
                if 'dependents' in body:
                    submodules = deepcopy(module.get('dependents'))
                    if submodules is None:
                        continue
                    for sub in body['dependents']:
                        found = True
                        name = sub.get('name')
                        revision = sub.get('revision')
                        schema = sub.get('schema')
                        for submodule in submodules:
                            found = True
                            if name:
                                if name != submodule['name']:
                                    found = False
                            if not found:
                                continue
                            if revision:
                                if revision!= submodule['revision']:
                                    found = False
                            if not found:
                                continue
                            if schema:
                                if schema != submodule['schema']:
                                    found = False
                            if found:
                                break

                        if not found:
                            passed = False
                            break
                if not passed:
                    continue
                if 'submodule' in body:
                    submodules = deepcopy(module.get('submodule'))
                    if submodules is None:
                        continue
                    for sub in body['submodule']:
                        found = True
                        name = sub.get('name')
                        revision = sub.get('revision')
                        schema = sub.get('schema')
                        for submodule in submodules:
                            found = True
                            if name:
                                if name != submodule['name']:
                                    found = False
                            if not found:
                                continue
                            if revision:
                                if revision != submodule['revision']:
                                    found = False
                            if not found:
                                continue
                            if schema:
                                if schema != submodule['schema']:
                                    found = False
                            if found:
                                break

                        if not found:
                            passed = False
                            break
                if not passed:
                    continue
                if 'implementations' in body:
                    implementations = deepcopy(module.get('implementations'))
                    if implementations is None:
                        continue
                    passed = True
                    for imp in body['implementations']['implementation']:
                        if not passed:
                            break
                        for leaf in imp:
                            found = False
                            impls = []
                            if leaf == 'deviation':
                                for implementation in implementations[
                                    'implementation']:
                                    deviations = implementation.get('deviation')
                                    if deviations is None:
                                        continue
                                    for dev in imp[leaf]:
                                        found = True
                                        name = dev.get('name')
                                        revision = dev.get('revision')
                                        for deviation in deviations:
                                            found = True
                                            if name:
                                                if name != deviation['name']:
                                                    found = False
                                            if not found:
                                                continue
                                            if revision:
                                                if revision != deviation['revision']:
                                                    found = False
                                            if found:
                                                break
                                        if not found:
                                            break
                                    if not found:
                                        continue
                                    else:
                                        impls.append(implementation)
                                if not found:
                                    passed = False
                                    break
                            elif leaf == 'feature':
                                for implementation in implementations['implementation']:
                                    if implementation.get(leaf) is None:
                                        continue
                                    if imp[leaf] == implementation[leaf]:
                                        found = True
                                        impls.append(implementation)
                                        continue
                                if not found:
                                    passed = False
                            else:
                                for implementation in implementations['implementation']:
                                    if implementation.get(leaf) is None:
                                        continue
                                    if imp[leaf] == implementation[leaf]:
                                        found = True
                                        impls.append(implementation)
                                        continue
                                if not found:
                                    passed = False
                            if not passed:
                                break
                            implementations['implementation'] = impls
                if not passed:
                    continue
                for leaf in body:
                    if (leaf != 'implementations' and leaf != 'submodule'
                        and leaf != 'dependencies' and leaf != 'dependents'):
                        if body[leaf] != module.get(leaf):
                            passed = False
                            break
                if passed:
                    passed_modules.append(module)
        if len(passed_modules) > 0:
            modules = json.JSONDecoder(object_pairs_hook=collections.OrderedDict) \
                .decode(json.dumps(passed_modules))
            return Response(json.dumps({
                'yang-catalog:modules': {
                    'module': modules
                }
            }), mimetype='application/json')
        else:
            return not_found()
    else:
        return make_response(
            jsonify({'error': 'body request has to start with "input" container'}),
            400)


@application.route('/search/vendor/<org>', methods=['GET'])
def search_vendor_statistics(org):
    vendor = org

    active_cache = get_active_cache()
    with active_cache[0]:
        application.LOGGER.info('Searching for vendors')
        data = vendors_data(active_cache[1], False)
    ven_data = None
    for d in data['vendor']:
        if d['name'] == vendor:
            ven_data = d
            break

    os_type = {}
    for plat in ven_data['platforms']['platform']:
        version_list = set()
        os = {}
        for ver in plat['software-versions']['software-version']:
            for flav in ver['software-flavors']['software-flavor']:
                os[ver['name']] = flav['modules']['module'][0]['os-type']
                if os[ver['name']] not in os_type:
                    os_type[os[ver['name']]] = {}
                break
            if ver['name'] not in os_type[os[ver['name']]]:
                os_type[os[ver['name']]][ver['name']] = set()

            version_list.add(ver['name'])
        for ver in version_list:
            os_type[os[ver]][ver].add(plat['name'])

    os_types = {}
    for key, vals in os_type.items():
        os_types[key] = {}
        for key2, val in os_type[key].items():
            os_types[key][key2] = list(os_type[key][key2])
    return Response(json.dumps(os_types), mimetype='application/json')


@application.route('/search/vendors/<path:value>', methods=['GET'])
def search_vendors(value):
    """Search for a specific vendor, platform, os-type, os-version depending on
    the value sent via API.
            Arguments:
                :param value: (str) path that contains one of the @module_keys and
                    ends with /value searched for
                :return response to the request.
    """
    application.LOGGER.info('Searching for specific vendors {}'.format(value))
    path = application.protocol + '://' + application.confd_ip + ':' + repr(application.confdPort) + '/api/config/catalog/vendors/' + value + '?deep'
    data = requests.get(path, auth=(application.credentials[0], application.credentials[1]),
                        headers={'Accept': 'application/vnd.yang.data+json'})
    if data.status_code == 200 or data.status_code == 204:
        data = json.JSONDecoder(object_pairs_hook=collections.OrderedDict) \
            .decode(data.text)
        return Response(json.dumps(data), mimetype='application/json')
    else:
        return not_found()


@application.route('/search/modules/<name>,<revision>,<organization>', methods=['GET'])
def search_module(name, revision, organization):
    """Search for a specific module defined with name, revision and organization
            Arguments:
                :param name: (str) name of the module
                :param revision: (str) revision of the module
                :param organization: (str) organization of the module
                :return response to the request with job_id that user can use to
                    see if the job is still on or Failed or Finished successfully
    """
    active_cache = get_active_cache()
    with active_cache[0]:
        application.LOGGER.info('Searching for module {}, {}, {}'.format(name, revision,
                                                             organization))
        if uwsgi.cache_exists(name + '@' + revision + '/' + organization,
                              'cache_chunks{}'.format(active_cache[1])):
            chunks = uwsgi.cache_get(name + '@' + revision + '/' + organization,
                                     'cache_chunks{}'.format(active_cache[1]))
            data = ''
            for i in range(0, int(chunks), 1):
                if sys.version_info >= (3, 4):
                    data += uwsgi.cache_get(name + '@' + revision + '/' +
                                            organization + '-' + repr(i),
                                            'cache_modules{}'.format(active_cache[1]))\
                        .decode(encoding='utf-8', errors='strict')
                else:
                    data += uwsgi.cache_get(name + '@' + revision + '/' +
                                            organization + '-' + repr(i),
                                            'cache_modules{}'.format(active_cache[1]))

            return Response(json.dumps({
                'module': [json.JSONDecoder(object_pairs_hook=collections.OrderedDict)\
                    .decode(data)]
            }), mimetype='application/json')
        return not_found()


@application.route('/search/modules', methods=['GET'])
def get_modules():
    """Search for a all the modules populated in confd
            :return response to the request with all the modules
    """
    active_cache = get_active_cache()
    with active_cache[0]:
        application.LOGGER.info('Searching for modules')
        data = json.dumps(modules_data(active_cache[1]))
        if data is None or data == '{}':
            return not_found()
        return Response(data, mimetype='application/json')


@application.route('/search/vendors', methods=['GET'])
def get_vendors():
    """Search for a all the vendors populated in confd
            :return response to the request with all the vendors
    """
    active_cache = get_active_cache()
    with active_cache[0]:
        application.LOGGER.info('Searching for vendors')
        data = json.dumps(vendors_data(active_cache[1]))
        if data is None or data == '{}':
            return not_found()
        return Response(data, mimetype='application/json')


@application.route('/search/catalog', methods=['GET'])
def get_catalog():
    """Search for a all the data populated in confd
                :return response to the request with all the data
    """
    application.LOGGER.info('Searching for catalog data')
    active_cache = get_active_cache()
    with active_cache[0]:
        data = catalog_data(active_cache[1])
    if data is None or data == '{}':
        return not_found()
    else:
        return Response(json.dumps(data), mimetype='application/json')


@application.route('/job/<job_id>', methods=['GET'])
def get_job(job_id):
    """Search for a job_id to see the process of the job
                :return response to the request with the job
    """
    application.LOGGER.info('Searching for job_id {}'.format(job_id))
    # EVY result = application.sender.get_response(job_id)
    result = application.sender.get_response(job_id)
    split = result.split('#split#')

    reason = None
    if split[0] == 'Failed':
        result = split[0]
        reason = split[1]

    return jsonify({'info': {'job-id': job_id,
                             'result': result,
                             'reason': reason}
                    })


@application.route('/check-platform-metadata', methods=['POST'])
def trigger_populate():
    application.LOGGER.info('Trigger populate if necessary')
    repoutil.pull(application.yang_models)
    try:
        commits = request.json['commits']
        paths = set()
        new = []
        mod = []
        if commits:
            for commit in commits:
                added = commit.get('added')
                if added:
                    for add in added:
                        if 'platform-metadata.json' in add:
                            paths.add('/'.join(add.split('/')[:-1]))
                            new.append('/'.join(add.split('/')[:-1]))
                modified = commit.get('modified')
                if modified:
                    for m in modified:
                        if 'platform-metadata.json' in m:
                            paths.add('/'.join(m.split('/')[:-1]))
                            mod.append('/'.join(m.split('/')[:-1]))
        if len(paths) > 0:
            mf = messageFactory.MessageFactory()
            mf.send_new_modified_platform_metadata(new, mod)
            application.LOGGER.info('Forking the repo')
            try:
                arguments = ["python", os.path.abspath("../parseAndPopulate/populate.py"),
                             "--port", repr(application.confdPort), "--ip",
                             application.confd_ip, "--api-protocol", application.api_protocol, "--api-port",
                             repr(application.api_port), "--api-ip", application.ip,
                             "--result-html-dir", application.result_dir,
                             "--credentials", application.credentials[0], application.credentials[1],
                             "--save-file-dir", application.save_file_dir, "repoLocalDir"]
                arguments = arguments + list(paths) + [application.yang_models, "github"]
                application.sender.send("#".join(arguments))
            except:
                application.LOGGER.error('Could not populate after git push')
            return make_response(jsonify({'info': 'Success'}), 200)
        return make_response(jsonify({'info': 'Success'}), 200)
    except Exception as e:
        application.LOGGER.error('Automated github webhook failure - {}'.format(e))
        return make_response(jsonify({'info': 'Success'}), 200)


@application.route('/load-cache', methods=['POST'])
@auth.login_required
def load_to_memory():
    """Load all the data populated to yang-catalog to memory.
            :return response to the request.
    """
    username = request.authorization['username']
    if username != 'admin':
        return unauthorized
    if get_password(username) != hash_pw(request.authorization['password']):
        return unauthorized()
    load(True)
    return make_response(jsonify({'info': 'Success'}), 201)


@application.route('/contributors', methods=['GET'])
def get_organizations():
    orgs = set()
    active_cache = get_active_cache()
    with active_cache[0]:
        data = modules_data(active_cache[1]).get('module')
    for mod in data:
        if mod['organization'] != 'example' and mod['organization'] != 'missing element':
            orgs.add(mod['organization'])
    orgs = list(orgs)
    resp = make_response(jsonify({'contributors': orgs}), 200)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


def modules_data(which_cache):
    chunks = int(uwsgi.cache_get('chunks-modules', 'cache_chunks{}'.format(which_cache)))
    data = ''
    for i in range(0, chunks, 1):
        if sys.version_info >= (3, 4):
            data += uwsgi.cache_get('modules-data{}'.format(i), 'main_cache{}'.format(which_cache))\
                .decode(encoding='utf-8', errors='strict')
        else:
            data += uwsgi.cache_get('modules-data{}'.format(i), 'main_cache{}'.format(which_cache))
    json_data = \
        json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(data)
    return json_data


def vendors_data(which_cache, clean_data=True):
    chunks = int(uwsgi.cache_get('chunks-vendor', 'cache_chunks{}'.format(which_cache)))
    data = ''
    for i in range(0, chunks, 1):
        if sys.version_info >= (3, 4):
            data += uwsgi.cache_get('vendors-data{}'.format(i), 'main_cache{}'.format(which_cache))\
                .decode(encoding='utf-8', errors='strict')
        else:
            data += uwsgi.cache_get('vendors-data{}'.format(i), 'main_cache{}'.format(which_cache))
    if clean_data:
        json_data = \
            json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(data)
    else:
        json_data = json.loads(data)
    return json_data


def catalog_data(which_cache):
    chunks = int(uwsgi.cache_get('chunks-data', 'cache_chunks{}'.format(which_cache)))
    if chunks == 0:
        return None
    data = ''
    for i in range(0, chunks, 1):
        if sys.version_info >= (3, 4):
            data += uwsgi.cache_get('data{}'.format(i), 'main_cache{}'.format(which_cache))\
                .decode(encoding='utf-8', errors='strict')
        else:
            data += uwsgi.cache_get('data{}'.format(i), 'main_cache{}'.format(which_cache))
    json_data = \
        json.JSONDecoder(object_pairs_hook=collections.OrderedDict) \
            .decode(data)
    return json_data


def get_active_cache():
    active_cache = uwsgi.cache_get('active_cache', 'cache_chunks1')
    if active_cache is None:
        return None
    else:
        active_cache = int(active_cache)
        if active_cache == 1:
            return lock_uwsgi_cache1, '1'
        else:
            return lock_uwsgi_cache2, '2'


def load(on_change):
    """Load to cache from confd all the data populated to yang-catalog."""
    with lock_for_load:
        with lock_uwsgi_cache1:
            application.LOGGER.info('Loading cache 1')
            modules_text, modules, vendors_text, data =\
                load_uwsgi_cache('cache_chunks1', 'main_cache1', 'cache_modules1', on_change)
            # reset active cache back to 1 since we are done with populating cache 1
            uwsgi.cache_update('active_cache', '1', 0, 'cache_chunks1')
        application.LOGGER.info('Loading cache 2')
        with lock_uwsgi_cache2:
            load_uwsgi_cache('cache_chunks2', 'main_cache2', 'cache_modules2', on_change,
                             modules_text, modules, vendors_text, data)
        application.LOGGER.info('Both caches are loaded')
        application.loading = False


def load_uwsgi_cache(cache_chunks, main_cache, cache_modules, on_change,
                     modules_text=None, modules=None, vendors_text=None, data=None):
    response = 'work'
    initialized = uwsgi.cache_get('initialized', cache_chunks)
    if sys.version_info >= (3, 4) and initialized is not None:
        initialized = initialized.decode(encoding='utf-8', errors='strict')
    application.LOGGER.debug('initialized {} on change {}'.format(initialized, on_change))
    if initialized is None or initialized == 'False' or on_change:
        uwsgi.cache_clear(cache_chunks)
        uwsgi.cache_clear(main_cache)
        uwsgi.cache_clear(cache_modules)
        if cache_chunks == 'cache_chunks1':
            # set active cache to 2 until we work on cache 1
            uwsgi.cache_set('active_cache', '2', 0, 'cache_chunks1')
        uwsgi.cache_set('initialized', 'False', 0, cache_chunks)
        response, data = make_cache(application.credentials, response, cache_chunks, main_cache,
                                    is_uwsgi=application.is_uwsgi, data=data)
        vendors = {}
        if modules is None or vendors_text is None:
            cat = json.JSONDecoder(object_pairs_hook=collections.OrderedDict) \
                    .decode(data)['yang-catalog:catalog']
            modules = cat['modules']
            if cat.get('vendors'):
                vendors = cat['vendors']
            else:
                vendors = {}
        if len(modules) != 0:
            for i, mod in enumerate(modules['module']):
                key = mod['name'] + '@' + mod['revision'] + '/' + mod[
                    'organization']
                value = json.dumps(mod)
                chunks = int(math.ceil(len(value) / float(20000)))
                uwsgi.cache_set(key, repr(chunks), 0, cache_chunks)
                for j in range(0, chunks, 1):
                    uwsgi.cache_set(key + '-{}'.format(j),
                                    value[j * 20000: (j + 1) * 20000], 0,
                                    cache_modules)

        if modules_text is None:
            modules_text = json.dumps(modules)
        chunks = int(math.ceil(len(modules_text) / float(64000)))
        for i in range(0, chunks, 1):
            uwsgi.cache_set('modules-data{}'.format(i),
                            modules_text[i * 64000: (i + 1) * 64000],
                            0, main_cache)
        application.LOGGER.info(
            'all {} modules chunks are set in uwsgi cache'.format(chunks))
        uwsgi.cache_set('chunks-modules', repr(chunks), 0, cache_chunks)

        if vendors_text is None:
            vendors_text = json.dumps(vendors)
        chunks = int(math.ceil(len(vendors_text) / float(64000)))
        for i in range(0, chunks, 1):
            uwsgi.cache_set('vendors-data{}'.format(i),
                            vendors_text[i * 64000: (i + 1) * 64000],
                            0, main_cache)
        application.LOGGER.info(
            'all {} vendors chunks are set in uwsgi cache'.format(chunks))
        uwsgi.cache_set('chunks-vendor', repr(chunks), 0, cache_chunks)
    if response != 'work':
        application.LOGGER.error('Could not load or create cache')
        sys.exit(500)
    uwsgi.cache_update('initialized', 'True', 0, cache_chunks)
    return modules_text, modules, vendors_text, data


def process(data, passed_data, value, module, split, count):
    """Iterates recursively through the data to find only modules
    that are searched for
            Arguments:
                :param data: (dict) module that is searched
                :param passed_data: (list) data that contain value searched
                    for are saved in this variable
                :param value: (str) value searched for
                :param module: (dict) module that is searched
                :param split: (str) key value that conatins value searched for
                :param count: (int) if split contains '/' then we need to know
                    which part of the path are we searching.
    """
    if isinstance(data, str):
        if data == value:
            passed_data.append(module)
            return True
    elif isinstance(data, list):
        for part in data:
            if process(part, passed_data, value, module, split, count):
                break
    elif isinstance(data, dict):
        if data:
            count += 1
            return process(data.get(split[count]), passed_data, value, module, split, count)
    return False


@auth.hash_password
def hash_pw(password):
    """Hash the password
            Arguments:
                :param password: (str) password provided via API
                :return hashed password
    """
    if sys.version_info >= (3, 4):
        password = password.encode(encoding='utf-8', errors='strict')
    return hashlib.sha256(password).hexdigest()


@auth.get_password
def get_password(username):
    """Get password out of database
            Arguments:
                :param username: (str) username privided via API
                :return hashed password
    """
    try:
        db = MySQLdb.connect(host=application.dbHost, db=application.dbName, user=application.dbUser, passwd=application.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()

        # execute SQL query using execute() method.
        cursor.execute("SELECT * FROM `users`")

        data = cursor.fetchall()

        for row in data:
            if username in row[1]:
                return row[2]
        db.close()
        return None

    except MySQLdb.MySQLError as err:
        application.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))


@auth.error_handler
def unauthorized():
    """Return unauthorized error message"""
    return make_response(jsonify({'error': 'Unauthorized access'}), 401)

load(False)
