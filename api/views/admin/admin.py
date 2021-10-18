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

import fnmatch
import grp
import gzip
import hashlib
import json
import math
import os
import pwd
import re
import shutil
import stat
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Blueprint, abort
from flask import current_app as app
from flask import jsonify, redirect, request
from flask_cors import CORS
from flask_oidc import OpenIDConnect
from redis import RedisError


class YangCatalogAdminBlueprint(Blueprint):

    def __init__(self, name, import_name, static_folder=None, static_url_path=None, template_folder=None,
                 url_prefix=None, subdomain=None, url_defaults=None, root_path=None):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder, url_prefix, subdomain,
                         url_defaults, root_path)


bp = YangCatalogAdminBlueprint('admin', __name__)
CORS(bp, supports_credentials=True)
oidc = OpenIDConnect()


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
            app.logger.error('Cannot connect to database. Redis error: {}'.format(err))
            return ({'error': 'Server problem connecting to database'}, 500)

    return df


### ROUTE ENDPOINT DEFINITIONS ###


@bp.route('/api/admin/login')
@bp.route('/admin')
@bp.route('/admin/login')
@oidc.require_login
def login():
    if oidc.user_loggedin:
        return redirect('{}/admin/healthcheck'.format(ac.w_my_uri), code=302)
    else:
        abort(401, 'user not logged in')


@bp.route('/api/admin/logout', methods=['POST'])
def logout():
    oidc.logout()
    return {'info': 'Success'}


@bp.route('/api/admin/ping')
def ping():
    app.logger.info('ping {}'.format(oidc.user_loggedin))
    return {'info': 'Success'}


@bp.route('/api/admin/check', methods=['GET'])
def check():
    return {'info': 'Success'}


@bp.route('/api/admin/directory-structure/read/<path:direc>', methods=['GET'])
def read_admin_file(direc):
    app.logger.info('Reading admin file {}'.format(direc))
    if os.path.isfile('{}/{}'.format(ac.d_var, direc)):
        with open('{}/{}'.format(ac.d_var, direc), 'r') as f:
            processed_file = f.read()
        response = {'info': 'Success',
                    'data': processed_file}
        return response
    else:
        abort(400, description='error - file does not exist')


@bp.route('/api/admin/directory-structure', defaults={'direc': ''}, methods=['DELETE'])
@bp.route('/api/admin/directory-structure/<path:direc>', methods=['DELETE'])
def delete_admin_file(direc):
    app.logger.info('Deleting admin file {}'.format(direc))
    if os.path.exists('{}/{}'.format(ac.d_var, direc)):
        if os.path.isfile('{}/{}'.format(ac.d_var, direc)):
            os.unlink('{}/{}'.format(ac.d_var, direc))
        else:
            shutil.rmtree('{}/{}'.format(ac.d_var, direc))
        response = {'info': 'Success',
                    'data': 'directory of file {} removed succesfully'.format('{}/{}'.format(ac.d_var, direc))}
        return response
    else:
        abort(400, description='error - file or folder does not exist')


@bp.route('/api/admin/directory-structure/<path:direc>', methods=['PUT'])
def write_to_directory_structure(direc):
    app.logger.info("Updating file on path {}".format(direc))

    body = get_input(request.json)
    if 'data' not in body:
        abort(400, description='"data" must be specified')
    data = body['data']

    if os.path.isfile('{}/{}'.format(ac.d_var, direc)):
        with open('{}/{}'.format(ac.d_var, direc), 'w') as f:
            f.write(data)
        response = {'info': 'Success',
                    'data': data}
        return response
    else:
        abort(400, description='error - file does not exist')


@bp.route('/api/admin/directory-structure', defaults={'direc': ''}, methods=['GET'])
@bp.route('/api/admin/directory-structure/<path:direc>', methods=['GET'])
def get_var_yang_directory_structure(direc):

    def walk_through_dir(path):
        structure = {'folders': [], 'files': []}
        root, dirs, files = next(os.walk(path))
        structure['name'] = os.path.basename(root)
        for f in files:
            file_structure = {'name': f}
            file_stat = Path('{}/{}'.format(path, f)).stat()
            file_structure['size'] = file_stat.st_size
            try:
                file_structure['group'] = grp.getgrgid(file_stat.st_gid).gr_name
            except:
                file_structure['group'] = file_stat.st_gid

            try:
                file_structure['user'] = pwd.getpwuid(file_stat.st_uid).pw_name
            except:
                file_structure['user'] = file_stat.st_uid
            file_structure['permissions'] = oct(stat.S_IMODE(os.lstat('{}/{}'.format(path, f)).st_mode))
            file_structure['modification'] = int(file_stat.st_mtime)
            structure['files'].append(file_structure)
        for directory in dirs:
            dir_structure = {'name': directory}
            p = Path('{}/{}'.format(path, directory))
            dir_size = sum(f.stat().st_size for f in p.glob('**/*') if f.is_file())
            dir_stat = p.stat()
            try:
                dir_structure['group'] = grp.getgrgid(dir_stat.st_gid).gr_name
            except:
                dir_structure['group'] = dir_stat.st_gid

            try:
                dir_structure['user'] = pwd.getpwuid(dir_stat.st_uid).pw_name
            except:
                dir_structure['user'] = dir_stat.st_uid
            dir_structure['size'] = dir_size
            dir_structure['permissions'] = oct(stat.S_IMODE(os.lstat('{}/{}'.format(path, directory)).st_mode))
            dir_structure['modification'] = int(dir_stat.st_mtime)
            structure['folders'].append(dir_structure)
        return structure

    app.logger.info('Getting directory structure')

    ret = walk_through_dir('/var/yang/{}'.format(direc))
    response = {'info': 'Success',
                'data': ret}
    return response


@bp.route('/api/admin/yangcatalog-nginx', methods=['GET'])
def read_yangcatalog_nginx_files():
    app.logger.info('Getting list of nginx files')
    files = os.listdir('{}/sites-enabled'.format(ac.d_nginx_conf))
    files_final = ['sites-enabled/' + sub for sub in files]
    files_final.append('nginx.conf')
    files = os.listdir('{}/conf.d'.format(ac.d_nginx_conf))
    files_final.extend(['conf.d/' + sub for sub in files])
    response = {'info': 'Success',
                'data': files_final}
    return response


@bp.route('/api/admin/yangcatalog-nginx/<path:nginx_file>', methods=['GET'])
def read_yangcatalog_nginx(nginx_file):
    app.logger.info('Reading nginx file {}'.format(nginx_file))
    with open('{}/{}'.format(ac.d_nginx_conf, nginx_file), 'r') as f:
        nginx_config = f.read()
    response = {'info': 'Success',
                'data': nginx_config}
    return response


@bp.route('/api/admin/yangcatalog-config', methods=['GET'])
def read_yangcatalog_config():
    app.logger.info('Reading yangcatalog config file')

    with open(os.environ['YANGCATALOG_CONFIG_PATH'], 'r') as f:
        yangcatalog_config = f.read()
    response = {'info': 'Success',
                'data': yangcatalog_config}
    return response


@bp.route('/api/admin/yangcatalog-config', methods=['PUT'])
def update_yangcatalog_config():
    app.logger.info('Updating yangcatalog config file')
    body = get_input(request.json)
    if 'data' not in body:
        abort(400, description='"data" must be specified')

    with open(os.environ['YANGCATALOG_CONFIG_PATH'], 'w') as f:
        f.write(body['data'])
    resp = {}
    try:
        app.load_config()
        resp['api'] = 'data loaded successfully'
    except:
        resp['api'] = 'error loading data'
    try:
        ac.sender.send('reload_config')
        resp['receiver'] = 'data loaded successfully'
    except:
        resp['receiver'] = 'error loading data'
    response = {'info': resp,
                'new-data': body['data']}
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
    response = {'info': 'Success',
                'data': list(resp)}
    return response


def find_files(directory, pattern):
    root, dirs, files = next(os.walk(directory))
    for basename in files:
        if fnmatch.fnmatch(basename, pattern):
            filename = os.path.join(root, basename)
            yield filename


def filter_from_date(file_names, from_timestamp):
    if from_timestamp is None:
        return ['{}/{}.log'.format(ac.d_logs, file_name) for file_name in file_names]
    else:
        r = []
        for file_name in file_names:
            files = find_files('{}/{}'.format(ac.d_logs, os.path.dirname(file_name)),
                               '{}.log*'.format(os.path.basename(file_name)))
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
                return datetime.strptime('{} {}'.format(d, t), '%Y-%m-%d %H:%M:%S').timestamp()
            except:
                pass


def determine_formatting(log_files, date_regex, time_regex):
    for log_file in log_files:
        with gzip.open(log_file, 'rt') if '.gz' in log_file else open(log_file, 'r') as f:
            file_stream = f.read()
            level_regex = r'[A-Z]{4,10}'
            two_words_regex = r'(\s*(\S*)\s*){2}'
            line_regex = '({} {}[ ]{}{}[=][>])'.format(date_regex, time_regex, level_regex, two_words_regex)
            hits = re.findall(line_regex, file_stream)
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
                if format_text:
                    line_timestamp = None
                    try:
                        d = re.findall(date_regex, line)[0][0]
                        t = re.findall(time_regex, line)[0]
                        line_beginning = '{} {}'.format(d, t)
                        line_timestamp = datetime.strptime(line_beginning, '%Y-%m-%d %H:%M:%S').timestamp()
                    except:
                        # ignore and accept
                        pass
                    if line_timestamp is None or not line.startswith(line_beginning):
                        whole_line = '{}{}'.format(line, whole_line)
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
                        level_formats = [
                            ' {} '.format(level), '<{}>'.format(level),
                            '[{}]'.format(level).lower(), '{}:'.format(level)]
                    if match_whole_words:
                        if searched_string != '':
                            searched_string = ' {} '.format(searched_string)
                    for level_format in level_formats:
                        if level_format in line:
                            if match_case and searched_string in line:
                                if filter_out is not None and filter_out in line:
                                    whole_line = ''
                                    continue
                                send_out.append('{}{}'.format(line, whole_line).rstrip())
                            elif not match_case and searched_string.lower() in line.lower():
                                if filter_out is not None and filter_out.lower() in line.lower():
                                    whole_line = ''
                                    continue
                                send_out.append('{}{}'.format(line, whole_line).rstrip())
                else:
                    send_out.append('{}{}'.format(line, whole_line).rstrip())
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

    # Try to find a timestamp in a log file using regex
    if from_date_timestamp is None:
        from_date_timestamp = find_timestamp(log_files[0], date_regex, time_regex)

    app.logger.debug('Searching for logs from timestamp: {}'.format(str(from_date_timestamp)))
    if to_date_timestamp is None:
        to_date_timestamp = datetime.now().timestamp()

    log_files.reverse()
    format_text = determine_formatting(log_files, date_regex, time_regex)

    send_out = generate_output(format_text, log_files, filter,
                               from_date_timestamp, to_date_timestamp, date_regex, time_regex)

    pages = math.ceil(len(send_out) / number_of_lines_per_page)

    metadata = {'file-names': file_names,
                'from-date': from_date_timestamp,
                'to-date': to_date_timestamp,
                'lines-per-page': number_of_lines_per_page,
                'page': page_num,
                'pages': pages,
                'filter': filter,
                'format': format_text}
    from_line = (page_num - 1) * number_of_lines_per_page
    output = send_out[from_line:page_num * number_of_lines_per_page]
    response = {'meta': metadata,
                'output': output}
    return response

@bp.route('/api/admin/move-user', methods=['POST'])
@catch_db_error
def move_user():
    body = get_input(request.json)
    id = body.get('id')
    sdo_access = body.get('access-rights-sdo', '')
    vendor_access = body.get('access-rights-vendor', '')
    if id is None:
        abort(400, description='id of a user is missing')
    if sdo_access == '' and vendor_access == '':
        abort(400, description='access-rights-sdo OR access-rights-vendor must be specified')

    users.approve(id, sdo_access, vendor_access)
    response = {'info': 'user successfully approved',
                'data': body}
    return (response, 201)


@bp.route('/api/admin/users/<status>', methods=['POST'])
@catch_db_error
def create_user(status):
    if status not in ['temp', 'approved']:
        return ({'error': 'invalid status "{}", use only "temp" or "approved" allowed'.format(status)}, 400)
    body = get_input(request.json)
    username = body.get('username')
    password = body.get('password')
    first_name = body.get('first-name')
    last_name = body.get('last-name')
    email = body.get('email')
    motivation = body.get('motivation', '')
    if not all((body, username, first_name, last_name, email, password)):
        abort(400, description='username - {}, firstname - {}, last-name - {},'
                               ' email - {} and password - {} must be specified'
                               .format(username, first_name, last_name, email, password))
    models_provider = body.get('models-provider', '')
    sdo_access = body.get('access-rights-sdo', '')
    vendor_access = body.get('access-rights-vendor', '')
    hashed_password = hash_pw(password)
    if status == 'approved' and not (sdo_access or vendor_access):
        abort(400, description='access-rights-sdo OR access-rights-vendor must be specified')
    fields = {
        'username': username,
        'password': hashed_password,
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'models_provider': models_provider
    }
    if status == 'temp':
        fields['motivation'] = motivation
    elif status == 'approved':
        fields['access_rights_sdo'] = sdo_access
        fields['access_rights_vendor'] = vendor_access
    id = users.create(temp=True if status == 'temp' else False, **fields)
    response = {'info': 'data successfully added to database',
                'data': body,
                'id': id}
    return (response, 201)


@bp.route('/api/admin/users/<status>/id/<id>', methods=['DELETE'])
@catch_db_error
def delete_user(status, id):
    if status not in ['temp', 'approved']:
        return ({'error': 'invalid status "{}", use only "temp" or "approved" allowed'.format(status)}, 400)
    if not users.exists(id):
        abort(404, description='id {} not found with status {}'.format(id, status))
    users.delete(id, temp=True if status == 'temp' else False)
    return {'info': 'id {} deleted successfully'.format(id)}


@bp.route('/api/admin/users/<status>/id/<id>', methods=['PUT'])
@catch_db_error
def update_user(status, id):
    if status not in ['temp', 'approved']:
        return ({'error': 'invalid status "{}", use only "temp" or "approved" allowed'.format(status)}, 400)
    if not (users.is_temp(id) if status == 'temp' else users.is_approved(id)):
        abort(404, description='id {} not found with status {}'.format(id, status))
    body = get_input(request.json)
    if not 'username' in body or not 'email' in body:
        abort(400, description='username and email must be specified')

    def get_set(field):
        users.set_field(id, field, body.get(field, ''))

    for field in ['username', 'email', 'models-provider', 'first-name', 'last-name']:
        get_set(field)
    if status == 'temp':
        get_set('motivation')
    if status == 'approved':
        get_set('access-rights-sdo')
        get_set('access-rights-vendor')
    app.logger.info('Record with ID {} with status {} updated successfully'.format(id, status))
    return {'info': 'ID {} updated successfully'.format(id)}

@bp.route('/api/admin/users/<status>', methods=['GET'])
@catch_db_error
def get_users(status):
    ids = users.get_all(status)
    ret = [users.get_all_fields(id) for id in ids]
    return jsonify(ret)


@bp.route('/api/admin/scripts/<script>', methods=['GET'])
def get_script_details(script):
    module_name = get_module_name(script)
    if module_name is None:
        abort(400, description='"{}" is not valid script name'.format(script))

    module = __import__(module_name, fromlist=[script])
    submodule = getattr(module, script)
    script_conf = submodule.ScriptConfig()
    script_args_list = script_conf.get_args_list()
    script_args_list.pop('credentials', None)

    response = {'data': script_args_list}
    response.update(script_conf.get_help())
    return response


@bp.route('/api/admin/scripts/<script>', methods=['POST'])
def run_script_with_args(script):
    module_name = get_module_name(script)
    if module_name is None:
        abort(400, description='"{}" is not valid script name'.format(script))

    body = get_input(request.json)

    arguments = ['run_script', module_name, script, json.dumps(body)]
    job_id = ac.sender.send('#'.join(arguments))

    return ({'info': 'Verification successful', 'job-id': job_id, 'arguments': arguments[1:]}, 202)


@bp.route('/api/admin/scripts', methods=['GET'])
def get_script_names():
    scripts_names = ['populate', 'runCapabilities', 'draftPull', 'ianaPull', 'draftPullLocal', 'openconfigPullLocal', 'statistics',
                     'recovery', 'elkRecovery', 'elkFill', 'resolveExpiration', 'reviseSemver']
    return {'data': scripts_names, 'info': 'Success'}


@bp.route('/api/admin/disk-usage', methods=['GET'])
def get_disk_usage():
    total, used, free = shutil.disk_usage('/')
    usage = {}
    usage['total'] = total
    usage['used'] = used
    usage['free'] = free
    return {'data': usage, 'info': 'Success'}


### HELPER DEFINITIONS ###
def get_module_name(script_name):
    if script_name in ['populate', 'runCapabilities', 'reviseSemver']:
        return 'parseAndPopulate'
    elif script_name in ['draftPull', 'ianaPull', 'draftPullLocal', 'openconfigPullLocal']:
        return 'ietfYangDraftPull'
    elif script_name in ['recovery', 'elkRecovery', 'elkFill']:
        return 'recovery'
    elif script_name == 'statistics':
        return 'statistic'
    elif script_name == 'resolveExpiration':
        return 'utility'
    else:
        return None


def hash_pw(password):
    if sys.version_info >= (3, 4):
        password = password.encode(encoding='utf-8', errors='strict')
    return hashlib.sha256(password).hexdigest()

def get_input(body):
    if body is None:
        abort(400, description='bad-request - body can not be empty')
    if 'input' not in body:
        abort(400, description='bad-request - body has to start with "input" and can not be empty')
    else:
        return body['input']
