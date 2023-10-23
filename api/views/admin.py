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

import collections
import fnmatch
import grp
import gzip
import json
import math
import os
import pwd
import re
import shutil
import stat
import typing as t
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing_extensions import Tuple

import flask
from flask.blueprints import Blueprint
from flask.globals import request
from flask.json import jsonify
from flask.wrappers import Response
from flask_cors import CORS
from flask_pyoidc import OIDCAuthentication
from flask_pyoidc.provider_configuration import ClientMetadata, ProviderConfiguration
from flask_pyoidc.user_session import UserSession
from redis import RedisError
from werkzeug.exceptions import abort
from werkzeug.utils import redirect

from api.my_flask import app
from api.views.json_checker import Union, check_error
from jobs.celery import run_script
from utility.create_config import create_config
from utility.util import hash_pw

config = create_config()
client_id = config.get('Secrets-Section', 'client-id')
client_secret = config.get('Secrets-Section', 'client-secret')
redirect_uris = config.get('Web-Section', 'redirect-oidc').split()
issuer = config.get('Web-Section', 'issuer')
my_uri = config.get('Web-Section', 'my-uri')

client_metadata = ClientMetadata(client_id=client_id, client_secret=client_secret, redirect_uris=redirect_uris)
provider_config = ProviderConfiguration(issuer=issuer, client_metadata=client_metadata)
ietf_auth = OIDCAuthentication({'default': provider_config})


bp = Blueprint('admin', __name__)
CORS(bp, supports_credentials=True)


@bp.before_request
def set_config():
    global ac, users
    ac = app.config
    users = ac.redis_users


def catch_db_error(f):
    @wraps(f)
    def df(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except RedisError as err:
            app.logger.error(f'Cannot connect to database. Redis error: {err}')
            return ({'error': 'Server problem connecting to database'}, 500)

    return df


@bp.route('/api/admin/login')
@bp.route('/admin')
@bp.route('/admin/login')
@ietf_auth.oidc_auth('default')
def login():
    return redirect(f'{ac.w_domain_prefix}/admin/healthcheck', code=302)


@bp.route('/api/admin/logout', methods=['POST'])
def logout():
    flask.session['id_token'] = None
    flask.session['last_authenticated'] = None
    return {'info': 'Success'}


@bp.route('/api/admin/ping')
def ping():
    app.logger.info(f'ping {UserSession(flask.session, "default").is_authenticated()}')
    return {'info': 'Success'}


@bp.route('/api/admin/check', methods=['GET'])
def check():
    return {'info': 'Success'}


@bp.route('/api/admin/directory-structure/read/<path:direc>', methods=['GET'])
def read_admin_file(direc):
    app.logger.info(f'Reading admin file {direc}')
    admin_file_path = os.path.join(ac.d_var, direc)
    if not os.path.isfile(admin_file_path):
        abort(400, description='error - file does not exist')
    with open(admin_file_path, 'r') as f:
        processed_file = f.read()
    response = {'info': 'Success', 'data': processed_file}
    return response


@bp.route('/api/admin/directory-structure', defaults={'direc': ''}, methods=['DELETE'])
@bp.route('/api/admin/directory-structure/<path:direc>', methods=['DELETE'])
def delete_admin_file(direc):
    app.logger.info(f'Deleting admin file {direc}')
    admin_file_path = os.path.join(ac.d_var, direc)
    if not os.path.exists(admin_file_path):
        abort(400, description='error - file or folder does not exist')
    if os.path.isfile(admin_file_path):
        os.unlink(admin_file_path)
    else:
        shutil.rmtree(admin_file_path)
    response = {'info': 'Success', 'data': f'directory of file {admin_file_path} removed succesfully'}
    return response


@bp.route('/api/admin/directory-structure/<path:direc>', methods=['PUT'])
def write_to_directory_structure(direc):
    app.logger.info(f'Updating file on path {direc}')
    body: t.Any = request.json
    check_error({'input': {'data': str}}, body)
    data = body['input']['data']
    admin_file_path = os.path.join(ac.d_var, direc)
    if not os.path.isfile(admin_file_path):
        abort(400, description='error - file does not exist')
    with open(admin_file_path, 'w') as f:
        f.write(data)
    response = {'info': 'Success', 'data': data}
    return response


@bp.route('/api/admin/directory-structure', defaults={'direc': ''}, methods=['GET'])
@bp.route('/api/admin/directory-structure/<path:direc>', methods=['GET'])
def get_var_yang_directory_structure(direc):
    def walk_through_dir(path):
        structure = {'folders': [], 'files': []}
        root, dirs, files = next(os.walk(path))
        structure['name'] = os.path.basename(root)
        for f in files:
            file_structure = {'name': f}
            file_stat = Path(f'{path}/{f}').stat()
            file_structure['size'] = file_stat.st_size
            try:
                file_structure['group'] = grp.getgrgid(file_stat.st_gid).gr_name
            except (KeyError, TypeError, AttributeError):
                file_structure['group'] = file_stat.st_gid

            try:
                file_structure['user'] = pwd.getpwuid(file_stat.st_uid).pw_name
            except Exception:
                file_structure['user'] = file_stat.st_uid
            file_structure['permissions'] = oct(stat.S_IMODE(os.lstat(f'{path}/{f}').st_mode))
            file_structure['modification'] = int(file_stat.st_mtime)
            structure['files'].append(file_structure)
        for directory in dirs:
            dir_structure = {'name': directory}
            p = Path(f'{path}/{directory}')
            dir_size = sum(f.stat().st_size for f in p.glob('**/*') if f.is_file())
            dir_stat = p.stat()
            try:
                dir_structure['group'] = grp.getgrgid(dir_stat.st_gid).gr_name
            except (KeyError, TypeError, AttributeError):
                dir_structure['group'] = dir_stat.st_gid

            try:
                dir_structure['user'] = pwd.getpwuid(dir_stat.st_uid).pw_name
            except Exception:
                dir_structure['user'] = dir_stat.st_uid
            dir_structure['size'] = dir_size
            dir_structure['permissions'] = oct(stat.S_IMODE(os.lstat(f'{path}/{directory}').st_mode))
            dir_structure['modification'] = int(dir_stat.st_mtime)
            structure['folders'].append(dir_structure)
        return structure

    app.logger.info('Getting directory structure')

    ret = walk_through_dir(os.path.join('/var/yang', direc))
    response = {'info': 'Success', 'data': ret}
    return response


@bp.route('/api/admin/yangcatalog-nginx', methods=['GET'])
def read_yangcatalog_nginx_files():
    app.logger.info('Getting list of nginx files')
    files = os.listdir(os.path.join(ac.d_nginx_conf, 'sites-enabled'))
    files_final = ['sites-enabled/' + sub for sub in files]
    files_final.append('nginx.conf')
    files = os.listdir(os.path.join(ac.d_nginx_conf, 'conf.d'))
    files_final.extend(['conf.d/' + sub for sub in files])
    response = {'info': 'Success', 'data': files_final}
    return response


@bp.route('/api/admin/yangcatalog-nginx/<path:nginx_file>', methods=['GET'])
def read_yangcatalog_nginx(nginx_file):
    app.logger.info(f'Reading nginx file {nginx_file}')
    with open(os.path.join(ac.d_nginx_conf, nginx_file), 'r') as f:
        nginx_config = f.read()
    response = {'info': 'Success', 'data': nginx_config}
    return response


@bp.route('/api/admin/yangcatalog-config', methods=['GET'])
def read_yangcatalog_config():
    app.logger.info('Reading yangcatalog config file')

    with open(os.environ['YANGCATALOG_CONFIG_PATH'], 'r') as f:
        yangcatalog_config = f.read()
    response = {'info': 'Success', 'data': yangcatalog_config}
    return response


@bp.route('/api/admin/yangcatalog-config', methods=['PUT'])
def update_yangcatalog_config():
    app.logger.info('Updating yangcatalog config file')
    body: t.Any = request.json
    check_error({'input': {'data': str}}, body)
    data = body['input']['data']
    with open(os.environ['YANGCATALOG_CONFIG_PATH'], 'w') as f:
        f.write(data)
    resp = {}
    try:
        app.load_config()
        resp['api'] = 'data loaded successfully'
    except Exception:
        resp['api'] = 'error loading data'
    response = {'info': resp, 'new-data': data}
    return response


@bp.route('/api/admin/logs', methods=['GET'])
def get_log_files():
    def find_files(directory, pattern):
        for root, _, files in os.walk(directory):
            for basename in files:
                if fnmatch.fnmatch(basename, pattern):
                    filename = os.path.join(root, basename)
                    yield filename

    app.logger.info('Getting yangcatalog log files')

    files = find_files(ac.d_logs, '*.log*')
    resp = set()
    for f in files:
        resp.add(f.split('/logs/')[-1].split('.')[0])
    response = {'info': 'Success', 'data': list(resp)}
    return response


def find_files(directory, pattern):
    root, _, files = next(os.walk(directory))
    for basename in files:
        if fnmatch.fnmatch(basename, pattern):
            filename = os.path.join(root, basename)
            yield filename


def filter_from_date(file_names, from_timestamp):
    if from_timestamp is None:
        return [f'{ac.d_logs}/{file_name}.log' for file_name in file_names]
    r = []
    for file_name in file_names:
        files = find_files(os.path.join(ac.d_logs, os.path.dirname(file_name)), f'{os.path.basename(file_name)}.log*')
        for f in files:
            if os.path.getmtime(f) >= from_timestamp:
                r.append(f)
    return r


def find_timestamp(file, date_regex, time_regex):
    with open(file, 'r') as f:
        for line in f.readlines():
            try:
                d = re.findall(date_regex, line)[0][0]
                t = re.findall(time_regex, line)[0]
                return datetime.strptime(f'{d} {t}', '%Y-%m-%d %H:%M:%S').timestamp()
            except (IndexError, ValueError):
                pass


def determine_formatting(log_files, date_regex, time_regex):
    for log_file in log_files:
        with gzip.open(log_file, 'rt') if '.gz' in log_file else open(log_file, 'r') as f:
            file_stream = f.read()
            level_regex = r'[A-Z]{4,10}'
            two_words_regex = r'(\s*(\S*)\s*){2}'
            line_regex = f'({date_regex} {time_regex}[ ]{level_regex}{two_words_regex}[=][>])'
            hits = re.findall(line_regex, file_stream)  # pyright: ignore # broken type hints I think
            if len(hits) <= 1 and file_stream:
                return False
    return True


def generate_output(format_text, log_files, filter, from_timestamp, to_timestamp, date_regex, time_regex):
    send_out = []
    for log_file in log_files:
        # Different way to open a file, but both will return a file object
        with gzip.open(log_file, 'rt') if '.gz' in log_file else open(log_file, 'r') as f:
            whole_line = ''
            for line in reversed(f.readlines()):
                line = line if isinstance(line, str) else line.decode()
                if format_text:
                    line_timestamp = None
                    line_beginning = ''
                    try:
                        d = re.findall(date_regex, line)[0][0]
                        t = re.findall(time_regex, line)[0]
                        line_beginning = f'{d} {t}'
                        line_timestamp = datetime.strptime(line_beginning, '%Y-%m-%d %H:%M:%S').timestamp()
                    except (IndexError, ValueError):
                        # ignore and accept
                        pass
                    if line_timestamp is None or not line.startswith(line_beginning):
                        whole_line = f'{line}{whole_line}'
                        continue
                    if not from_timestamp <= line_timestamp <= to_timestamp:
                        whole_line = ''
                        continue
                if filter is not None:
                    match_case = filter.get('match-case', False)
                    match_whole_words = filter.get('match-words', False)
                    filter_out = filter.get('filter-out', None)
                    searched_string = filter.get('search-for', '')
                    level = filter.get('level', '').upper()
                    level_formats = ['']
                    if level != '':
                        level_formats = [f' {level} ', '<{level}>', f'[{level}]'.lower(), f'{level}:']
                    if match_whole_words:
                        if searched_string != '':
                            searched_string = f' {searched_string} '
                    for level_format in level_formats:
                        if level_format in line:
                            if match_case and searched_string in line:
                                if filter_out is not None and filter_out in line:
                                    whole_line = ''
                                    continue
                                send_out.append(f'{line}{whole_line}'.rstrip())
                            elif not match_case and searched_string.lower() in line.lower():
                                if filter_out is not None and filter_out.lower() in line.lower():
                                    whole_line = ''
                                    continue
                                send_out.append(f'{line}{whole_line}'.rstrip())
                else:
                    send_out.append(f'{line}{whole_line}'.rstrip())
                whole_line = ''
    return send_out


@bp.route('/api/admin/logs', methods=['POST'])
def get_logs():
    date_regex = r'([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))'
    time_regex = r'(?:[01]\d|2[0-3]):(?:[0-5]\d):(?:[0-5]\d)'
    app.logger.info('Reading yangcatalog log file')
    body = get_input(request.json)

    number_of_lines_per_page = body.get('lines-per-page', 1000)
    page_num = body.get('page', 1)
    filter = body.get('filter')
    from_date_timestamp = body.get('from-date', None)
    to_date_timestamp = body.get('to-date', None)
    file_names = body.get('file-names', ['yang'])
    log_files = filter_from_date(file_names, from_date_timestamp)

    # Try to find a timestamp in a log file using regex
    if from_date_timestamp is None:
        from_date_timestamp = find_timestamp(log_files[0], date_regex, time_regex)

    app.logger.debug(f'Searching for logs from timestamp: {str(from_date_timestamp)}')
    if to_date_timestamp is None:
        to_date_timestamp = datetime.now().timestamp()

    log_files.reverse()
    format_text = determine_formatting(log_files, date_regex, time_regex)

    send_out = generate_output(
        format_text,
        log_files,
        filter,
        from_date_timestamp,
        to_date_timestamp,
        date_regex,
        time_regex,
    )

    pages = math.ceil(len(send_out) / number_of_lines_per_page)

    metadata = {
        'file-names': file_names,
        'from-date': from_date_timestamp,
        'to-date': to_date_timestamp,
        'lines-per-page': number_of_lines_per_page,
        'page': page_num,
        'pages': pages,
        'filter': filter,
        'format': format_text,
    }
    from_line = (page_num - 1) * number_of_lines_per_page
    output = send_out[from_line : page_num * number_of_lines_per_page]
    response = {'meta': metadata, 'output': output}
    return response


@bp.route('/api/admin/move-user', methods=['POST'])
@catch_db_error
def move_user():
    body: t.Any = request.json
    check_error(
        {'input': Union({'id': int, 'access-rights-sdo': str}, {'id': int, 'access-rights-vendor': str})},
        body,
    )
    body = body['input']
    id = body['id']
    sdo_access = body.get('access-rights-sdo', '')
    vendor_access = body.get('access-rights-vendor', '')
    users.approve(id, sdo_access, vendor_access)
    response = {'info': 'user successfully approved', 'data': body}
    return (response, 201)


@bp.route('/api/admin/users/<status>', methods=['POST'])
@catch_db_error
def create_user(status):
    if status not in ['temp', 'approved']:
        return ({'error': f'invalid status "{status}", use only "temp" or "approved" allowed'}, 400)
    body: t.Any = request.json
    registration_data = {'username': str, 'password': str, 'first-name': str, 'last-name': str, 'email': str}
    if status == 'approved':
        registration_data = Union(
            registration_data | {'access-rights-sdo': str},
            registration_data | {'access-rights-vendor': str},
        )
    check_error({'input': registration_data}, body)
    body = body['input']
    username = body['username']
    password = body['password']
    first_name = body['first-name']
    last_name = body['last-name']
    email = body['email']
    motivation = body.get('motivation', '')
    models_provider = body.get('models-provider', '')
    sdo_access = body.get('access-rights-sdo', '')
    vendor_access = body.get('access-rights-vendor', '')
    hashed_password = hash_pw(password)
    fields = {
        'username': username,
        'password': hashed_password,
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'models_provider': models_provider,
    }
    if status == 'temp':
        fields['motivation'] = motivation
    elif status == 'approved':
        fields['access_rights_sdo'] = sdo_access
        fields['access_rights_vendor'] = vendor_access
    id = users.create(temp=status == 'temp', **fields)
    response = {'info': 'data successfully added to database', 'data': body, 'id': id}
    return (response, 201)


@bp.route('/api/admin/users/<status>/id/<id>', methods=['DELETE'])
@catch_db_error
def delete_user(status, id):
    if status not in ['temp', 'approved']:
        return ({'error': f'invalid status "{status}", use only "temp" or "approved" allowed'}, 400)
    if not (users.is_temp(id) if status == 'temp' else users.is_approved(id)):
        abort(404, description=f'id {id} not found with status {status}')
    users.delete(id, temp=True if status == 'temp' else False)
    return {'info': f'id {id} deleted successfully'}


@bp.route('/api/admin/users/<status>/id/<id>', methods=['PUT'])
@catch_db_error
def update_user(status, id):
    if status not in ['temp', 'approved']:
        return ({'error': f'invalid status "{status}", use only "temp" or "approved" allowed'}, 400)
    if not (users.is_temp(id) if status == 'temp' else users.is_approved(id)):
        abort(404, description=f'id {id} not found with status {status}')
    body: t.Any = request.json
    check_error({'input': {'username': str, 'email': str}}, body)

    def get_set(field):
        users.set_field(id, field, body['input'].get(field, ''))

    for field in ['username', 'email', 'models-provider', 'first-name', 'last-name']:
        get_set(field)
    if status == 'temp':
        get_set('motivation')
    if status == 'approved':
        get_set('access-rights-sdo')
        get_set('access-rights-vendor')
    app.logger.info(f'Record with ID {id} with status {status} updated successfully')
    return {'info': f'ID {id} updated successfully'}


@bp.route('/api/admin/users/<status>', methods=['GET'])
@catch_db_error
def get_users(status):
    ids = users.get_all(status)
    app.logger.info(f'Fetching {len(ids)} users from redis')
    ret = [users.get_all_fields(id) for id in ids]
    for user, id in zip(ret, ids):
        user.update(id=id)
    return jsonify(ret)


@bp.route('/api/admin/scripts/<script>', methods=['GET'])
def get_script_details(script):
    module_name = get_module_name(script)
    if module_name is None:
        abort(400, description=f'"{script}" is not valid script name')

    module = __import__(module_name, fromlist=[script])
    submodule = getattr(module, script)
    script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()
    script_args_list = script_conf.get_args_list()
    script_args_list.pop('credentials', None)

    response = {'data': script_args_list}
    response.update(script_conf.get_help())
    return response


@bp.route('/api/admin/scripts/<script>', methods=['POST'])
def run_script_with_args(script):
    module_name = get_module_name(script)
    if module_name is None:
        abort(400, description=f'"{script}" is not valid script name')

    body = get_input(request.json)
    arguments = (module_name, script, body)

    result = run_script.s(*arguments).apply_async()

    return {'info': 'Verification successful', 'job-id': result.id, 'arguments': arguments}, 202


@bp.route('/api/admin/scripts', methods=['GET'])
def get_script_names():
    scripts_names = (
        'populate',
        'parse_directory',
        'ietf_push',
        'iana_push',
        'pull_local',
        'statistics',
        'recovery',
        'opensearch_recovery',
        'opensearch_fill',
        'redis_users_recovery',
        'resolve_expiration',
        'reviseSemver',
    )
    return {'data': scripts_names, 'info': 'Success'}


@bp.route('/api/admin/disk-usage', methods=['GET'])
def get_disk_usage():
    total, used, free = shutil.disk_usage('/')
    usage = {'total': total, 'used': used, 'free': free}
    return {'data': usage, 'info': 'Success'}


def get_module_name(script_name):
    if script_name in ('populate', 'parse_directory', 'reviseSemver', 'resolve_expiration'):
        return 'parseAndPopulate'
    elif script_name in ('pull_local',):
        return 'ietfYangDraftPull'
    elif script_name in ('ietf_push', 'iana_push'):
        return 'automatic_push'
    elif script_name in ('recovery', 'opensearch_recovery', 'opensearch_fill', 'redis_users_recovery'):
        return 'recovery'
    elif script_name == 'statistics':
        return 'statistic'
    return None


def get_input(body):
    if body is None:
        abort(400, description='bad-request - body can not be empty')
    if 'input' not in body:
        abort(400, description='bad-request - body has to start with "input" and can not be empty')
    else:
        return body['input']
    

@bp.route('/api/admin/module/<module>@<revision>/<organization>', methods=['GET'])
@catch_db_error
def get_redis_module(module:str, revision:str, organization: str) -> dict | Tuple[Response, int]:
    module_key = f'{module}@{revision}/{organization}'
    module_from_db = app.redisConnection.get_module(module_key)
    if module_from_db != '{}':
        return json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(module_from_db)
    else:
        return jsonify({module_key: {'info': 'Module does not exist.'}}), 404
    

@bp.route('/api/admin/module/<module>@<revision>/<organization>', methods=['PUT'])
@catch_db_error
def update_redis_module(module:str, revision:str, organization: str) -> dict | Tuple[Response, int]:
    module_key = f'{module}@{revision}/{organization}'
    module_from_db = app.redisConnection.get_module(module_key)
    module_to_json = json.JSONDecoder(object_pairs_hook=collections.OrderedDict).decode(module_from_db)
    if body := request.get_json():
        if body == module_to_json:
            return jsonify({'message': f'Module {module_key} is already in database.'}), 200
        app.redisConnection.set_module(body, module_key)
        return jsonify({'message': f'Module {module_key} updated successfully.'}), 200
    else:
        return jsonify({'error': 'Invalid data provided.'}), 400
