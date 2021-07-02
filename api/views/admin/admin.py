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
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
import requests
from api.globalConfig import yc_gc
from flask import Blueprint, abort, jsonify, redirect, request, current_app
from flask_cors import CORS
from utility.util import create_signature
from api.models import Base, User, TempUser


class YangCatalogAdminBlueprint(Blueprint):

    def __init__(self, name, import_name, static_folder=None, static_url_path=None, template_folder=None,
                 url_prefix=None, subdomain=None, url_defaults=None, root_path=None):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder, url_prefix, subdomain,
                         url_defaults, root_path)


app = YangCatalogAdminBlueprint('admin', __name__)
CORS(app, supports_credentials=True)
db = yc_gc.sqlalchemy

### ROUTE ENDPOINT DEFINITIONS ###


@app.route('/api/admin/login')
@app.route('/admin')
@app.route('/admin/login')
@yc_gc.oidc.require_login
def login():
    if yc_gc.oidc.user_loggedin:
        return redirect('{}/admin/healthcheck'.format(yc_gc.my_uri), code=302)
    else:
        abort(401, 'user not logged in')


@app.route('/api/admin/logout', methods=['POST'])
def logout():
    yc_gc.oidc.logout()
    return {'info': 'Success'}


@app.route('/api/admin/ping')
def ping():
    yc_gc.LOGGER.info('ping {}'.format(yc_gc.oidc.user_loggedin))
    return {'info': 'Success'}


@app.route('/api/admin/check', methods=['GET'])
def check():
    return {'info': 'Success'}


@app.route('/api/admin/directory-structure/read/<path:direc>', methods=['GET'])
def read_admin_file(direc):
    yc_gc.LOGGER.info('Reading admin file {}'.format(direc))
    try:
        file_exist = os.path.isfile('{}/{}'.format(yc_gc.var_yang, direc))
    except:
        file_exist = False
    if file_exist:
        with open('{}/{}'.format(yc_gc.var_yang, direc), 'r') as f:
            processed_file = f.read()
        response = {'info': 'Success',
                    'data': processed_file}
        return response
    else:
        abort(400, description='error - file does not exist')


@app.route('/api/admin/directory-structure', defaults={'direc': ''}, methods=['DELETE'])
@app.route('/api/admin/directory-structure/<path:direc>', methods=['DELETE'])
def delete_admin_file(direc):
    yc_gc.LOGGER.info('Deleting admin file {}'.format(direc))
    try:
        exist = os.path.exists('{}/{}'.format(yc_gc.var_yang, direc))
    except:
        exist = False
    if exist:
        if os.path.isfile('{}/{}'.format(yc_gc.var_yang, direc)):
            os.unlink('{}/{}'.format(yc_gc.var_yang, direc))
        else:
            shutil.rmtree('{}/{}'.format(yc_gc.var_yang, direc))
        response = {'info': 'Success',
                    'data': 'directory of file {} removed succesfully'.format('{}/{}'.format(yc_gc.var_yang, direc))}
        return response
    else:
        abort(400, description='error - file or folder does not exist')


@app.route('/api/admin/directory-structure/<path:direc>', methods=['PUT'])
def write_to_directory_structure(direc):
    yc_gc.LOGGER.info('Updating file on path {}'.format(direc))

    body = get_input(request.json)
    if 'data' not in body:
        abort(400, description='"data" must be specified')
    data = body['data']

    try:
        file_exist = os.path.isfile('{}/{}'.format(yc_gc.var_yang, direc))
    except:
        file_exist = False
    if file_exist:
        with open('{}/{}'.format(yc_gc.var_yang, direc), 'w') as f:
            f.write(data)
        response = {'info': 'Success',
                    'data': data}
        return response
    else:
        abort(400, description='error - file does not exist')


@app.route('/api/admin/directory-structure', defaults={'direc': ''}, methods=['GET'])
@app.route('/api/admin/directory-structure/<path:direc>', methods=['GET'])
def get_var_yang_directory_structure(direc):

    def walk_through_dir(path):
        structure = {'folders': [], 'files': []}
        for root, dirs, files in os.walk(path):
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
            break
        return structure

    yc_gc.LOGGER.info('Getting directory structure')

    ret = walk_through_dir('/var/yang/{}'.format(direc))
    response = {'info': 'Success',
                'data': ret}
    return response


@app.route('/api/admin/yangcatalog-nginx', methods=['GET'])
def read_yangcatalog_nginx_files():
    yc_gc.LOGGER.info('Getting list of nginx files')
    files = os.listdir('{}/sites-enabled'.format(yc_gc.nginx_dir))
    files_final = ['sites-enabled/' + sub for sub in files]
    files_final.append('nginx.conf')
    files = os.listdir('{}/conf.d'.format(yc_gc.nginx_dir))
    files_final.extend(['conf.d/' + sub for sub in files])
    response = {'info': 'Success',
                'data': files_final}
    return response


@app.route('/api/admin/yangcatalog-nginx/<path:nginx_file>', methods=['GET'])
def read_yangcatalog_nginx(nginx_file):
    yc_gc.LOGGER.info('Reading nginx file {}'.format(nginx_file))
    with open('{}/{}'.format(yc_gc.nginx_dir, nginx_file), 'r') as f:
        nginx_config = f.read()
    response = {'info': 'Success',
                'data': nginx_config}
    return response


@app.route('/api/admin/yangcatalog-config', methods=['GET'])
def read_yangcatalog_config():
    yc_gc.LOGGER.info('Reading yangcatalog config file')

    with open(yc_gc.config_path, 'r') as f:
        yangcatalog_config = f.read()
    response = {'info': 'Success',
                'data': yangcatalog_config}
    return response


@app.route('/api/admin/yangcatalog-config', methods=['PUT'])
def update_yangcatalog_config():
    yc_gc.LOGGER.info('Updating yangcatalog config file')
    body = get_input(request.json)
    if 'data' not in body:
        abort(400, description='"data" must be specified')

    with open(yc_gc.config_path, 'w') as f:
        f.write(body['data'])
    resp = {}
    try:
        yc_gc.load_config()
    except:
        resp['api'] = 'error loading data'
    else:
        resp['api'] = 'data loaded successfully'
    try:
        yc_gc.sender.send('reload_config')
    except:
        resp['receiver'] ='error loading data'
    else:
        resp['receiver'] = 'data loaded succesfully'
    path = '{}://{}/yang-search/reload_config'.format(yc_gc.api_protocol, yc_gc.ip)
    signature = create_signature(yc_gc.search_key, json.dumps(body))

    response = requests.post(path, data=json.dumps(body),
                             headers={'Content-Type': 'app/json', 'Accept': 'app/json',
                                      'X-YC-Signature': 'sha1={}'.format(signature)}, verify=False)
    code = response.status_code

    if code != 200 and code != 201 and code != 204:
        yc_gc.LOGGER.error('could not send data to realod config. Reason: {}'
                           .format(response.text))
        resp['yang-search'] = 'error loading data'
    else:
        resp['yang-search'] = response.json()['info']
    response = {'info': resp,
                'new-data': body['data']}
    return response


@app.route('/api/admin/logs', methods=['GET'])
def get_log_files():

    def find_files(directory, pattern):
        for root, dirs, files in os.walk(directory):
            for basename in files:
                if fnmatch.fnmatch(basename, pattern):
                    filename = os.path.join(root, basename)
                    yield filename

    yc_gc.LOGGER.info('Getting yangcatalog log files')

    files = find_files(yc_gc.logs_dir, '*.log*')
    resp = set()
    for f in files:
        resp.add(f.split('/logs/')[-1].split('.')[0])
    response = {'info': 'Success',
                'data': list(resp)}
    return response


@app.route('/api/admin/logs', methods=['POST'])
def get_logs():

    def find_files(directory, pattern):
        for root, dirs, files in os.walk(directory):
            for basename in files:
                if fnmatch.fnmatch(basename, pattern):
                    filename = os.path.join(root, basename)
                    yield filename
            break

    date_regex = r'([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))'
    time_regex = r'(?:[01]\d|2[0-3]):(?:[0-5]\d):(?:[0-5]\d)'
    yc_gc.LOGGER.info('Reading yangcatalog log file')
    body = get_input(request.json)

    number_of_lines_per_page = body.get('lines-per-page', 1000)
    page_num = body.get('page', 1)
    filter = body.get('filter')
    from_date_timestamp = body.get('from-date', None)
    to_date_timestamp = body.get('to-date', None)
    file_names = body.get('file-names', ['yang'])
    log_files = []

    # Check if file modification date is greater than from timestamp
    for file_name in file_names:
        if from_date_timestamp is None:
            log_files.append('{}/{}.log'.format(yc_gc.logs_dir, file_name))
        else:
            files = find_files('{}/{}'.format(yc_gc.logs_dir, '/'.join(file_name.split('/')[:-1])),
                               '{}.log*'.format(file_name.split('/')[-1]))
            for f in files:
                if os.path.getmtime(f) >= from_date_timestamp:
                    log_files.append(f)
    send_out = []

    # Try to find a timestamp in a log file using regex
    if from_date_timestamp is None:
        with open(log_files[0], 'r') as f:
            for line in f.readlines():
                if from_date_timestamp is None:
                    try:
                        d = re.findall(date_regex, line)[0][0]
                        t = re.findall(time_regex, line)[0]
                        from_date_timestamp = datetime.strptime('{} {}'.format(d, t), '%Y-%m-%d %H:%M:%S').timestamp()
                    except:
                        # ignore and accept
                        pass
                else:
                    break

    yc_gc.LOGGER.debug('Searching for logs from timestamp: {}'.format(str(from_date_timestamp)))
    whole_line = ''
    if to_date_timestamp is None:
        to_date_timestamp = datetime.now().timestamp()

    log_files.reverse()
    # Decide whether the output will be formatted or not (default False)
    format_text = False
    for log_file in log_files:
        if '.gz' in log_file:
            f = gzip.open(log_file, 'rt')
        else:
            f = open(log_file, 'r')
        file_stream = f.read()
        level_regex = r'[A-Z]{4,10}'
        two_words_regex = r'(\s*(\S*)\s*){2}'
        line_regex = '({} {}[ ]{}{}[=][>])'.format(date_regex, time_regex, level_regex, two_words_regex)
        hits = re.findall(line_regex, file_stream)
        if len(hits) > 1 or file_stream == '':
            format_text = True
        else:
            format_text = False
            break

    if not format_text:
        for log_file in log_files:
            # Different way to open a file, but both will return a file object
            if '.gz' in log_file:
                f = gzip.open(log_file, 'rt')
            else:
                f = open(log_file, 'r')
            for line in reversed(f.readlines()):
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
                                    continue
                                send_out.append('{}'.format(line).rstrip())
                            elif not match_case and searched_string.lower() in line.lower():
                                if filter_out is not None and filter_out.lower() in line.lower():
                                    continue
                                send_out.append('{}'.format(line).rstrip())
                else:
                    send_out.append('{}'.format(line).rstrip())

    if format_text:
        for log_file in log_files:
            # Different way to open a file, but both will return a file object
            if '.gz' in log_file:
                f = gzip.open(log_file, 'rt')
            else:
                f = open(log_file, 'r')
            for line in reversed(f.readlines()):
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
                if from_date_timestamp <= line_timestamp <= to_date_timestamp:
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

    pages = math.ceil(len(send_out) / number_of_lines_per_page)
    len_send_out = len(send_out)

    metadata = {'file-names': file_names,
                'from-date': from_date_timestamp,
                'to-data': to_date_timestamp,
                'lines-per-page': number_of_lines_per_page,
                'page': page_num,
                'pages': pages,
                'filter': filter,
                'format': format_text}
    from_line = (page_num - 1) * number_of_lines_per_page
    if page_num * number_of_lines_per_page > len_send_out:
        output = send_out[from_line:]
    else:
        output = send_out[from_line:page_num * number_of_lines_per_page]
    response = {'meta': metadata,
                'output': output}
    return response


@app.route('/api/admin/sql-tables', methods=['GET'])
def get_sql_tables():
    return jsonify([
        {
            'name': 'users',
            'label': 'approved users'
        },
        {
            'name': 'users_temp',
            'label': 'users waiting for approval'
        }
    ])


@app.route('/api/admin/move-user', methods=['POST'])
def move_user():
    body = get_input(request.json)
    unique_id = body.get('id')
    if unique_id is None:
        return abort(400, description='Id of a user is missing')
    models_provider = body.get('models-provider', '')
    sdo_access = body.get('access-rights-sdo', '')
    vendor_access = body.get('access-rights-vendor', '')
    username = body.get('username')
    name = body.get('first-name')
    last_name = body.get('last-name')
    email = body.get('email')
    if sdo_access == '' and vendor_access == '':
        abort(400, description='access-rights-sdo OR access-rights-vendor must be specified')
    try:
        password = db.session.query(TempUser.Password).filter_by(Id=unique_id).first() or ''
        user = User(Username=username, Password=password, Email=email, ModelsProvider=models_provider,
                    FirstName=name, LastName=last_name, AccessRightsSdo=sdo_access, AccessRightsVendor=vendor_access)
        db.session.add(user)
        db.session.commit()
    except SQLAlchemyError as err:
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
        return ({'error': 'Server problem connecting to database'}, 500)
    try:
        user = db.session.query(TempUser).filter_by(Id=unique_id).first()
        if user:
            db.session.delete(user)
            db.session.commit()
    except SQLAlchemyError as err:
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
        return ({'error': 'Server problem connecting to database'}, 500)
    response = {'info': 'data successfully added to database users and removed from users_temp',
                'data': body}
    return (response, 201)


@app.route('/api/admin/sql-tables/<table>', methods=['POST'])
def create_sql_row(table):
    if table not in ['users', 'users_temp']:
        return ({'error': 'table {} not implemented use only users or users_temp'.format(table)}, 501)
    model = get_class_by_tablename(table)
    body = get_input(request.json)
    username = body.get('username')
    name = body.get('first-name')
    last_name = body.get('last-name')
    email = body.get('email')
    password = body.get('password')
    if not all((body, username, name, last_name, email, password)):
        abort(400, description='username - {}, firstname - {}, last-name - {},'
                               ' email - {} and password - {} must be specified'
                               .format(username, name, last_name, email, password))
    models_provider = body.get('models-provider', '')
    sdo_access = body.get('access-rights-sdo', '')
    vendor_access = body.get('access-rights-vendor', '')
    hashed_password = hash_pw(password)
    if model is User and sdo_access == '' and vendor_access == '':
        abort(400, description='access-rights-sdo OR access-rights-vendor must be specified')
    try:
        user = model(Username=username, FirstName=name, LastName=last_name, Email=email, Password=hashed_password,
                    ModelsProvider=models_provider, AccessRightsSdo=sdo_access, AccessRightsVendor=vendor_access)
        db.session.add(user)
        db.session.commit()
        response = {'info': 'data successfully added to database',
                    'data': body}
        return (response, 201)
    except SQLAlchemyError as err:
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
        return ({'error': 'Server problem connecting to database'}, 500)


@app.route('/api/admin/sql-tables/<table>/id/<unique_id>', methods=['DELETE'])
def delete_sql_row(table, unique_id):
    if table not in ['users', 'users_temp']:
        return ({'error': 'no such table {}, use only users or users_temp'.format(table)}, 400)
    try:
        model = get_class_by_tablename(table)
        user = db.session.query(model).filter_by(Id=unique_id).first()
        db.session.delete(user)
        db.session.commit()
    except SQLAlchemyError as err:
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
        return ({'error': 'Server problem connecting to database'}, 500)
    if user:
        return {'info': 'id {} deleted successfully'.format(unique_id)}
    else:
        abort(404, description='id {} not found in table {}'.format(unique_id, table))


@app.route('/api/admin/sql-tables/<table>/id/<unique_id>', methods=['PUT'])
def update_sql_row(table, unique_id):
    if table not in ['users', 'users_temp']:
        return ({'error': 'no such table {}, use only users or users_temp'.format(table)}, 400)
    try:
        model = get_class_by_tablename(table)
        user = db.session.query(model).filter_by(Id=unique_id).first()
        if user:
            body = get_input(request.json)
            user.Username = body.get('username')
            user.Email = body.get('email')
            user.ModelsProvider = body.get('models-provider')
            user.FirstName = body.get('first-name')
            user.LastName = body.get('last-name')
            user.AccessRightsSdo = body.get('access-rights-sdo', '')
            user.AccessRightsVendor = body.get('access-rights-vendor', '')
            if not user.Username or not user.Email:
                abort(400, description='username and email must be specified')
            db.session.commit()
    except SQLAlchemyError as err:
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
        return ({'error': 'Server problem connecting to database'}, 500)
    if user:
        yc_gc.LOGGER.info('Record with ID {} in table {} updated successfully'.format(unique_id, table))
        return {'info': 'ID {} updated successfully'.format(unique_id)}
    else:
        abort(404, description='ID {} not found in table {}'.format(unique_id, table))


@app.route('/api/admin/sql-tables/<table>', methods=['GET'])
def get_sql_rows(table):
    try:
        model = get_class_by_tablename(table)
        users = db.session.query(model).all()
    except SQLAlchemyError as err:
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
        return ({'error': 'Server problem connecting to database'}, 500)
    ret = []
    for user in users:
        data_set = {'id': user.Id,
                    'username': user.Username,
                    'email': user.Email,
                    'models-provider': user.ModelsProvider,
                    'first-name': user.FirstName,
                    'last-name': user.LastName,
                    'access-rights-sdo': user.AccessRightsSdo,
                    'access-rights-vendor': user.AccessRightsVendor}
        ret.append(data_set)
    return ret


@app.route('/api/admin/scripts/<script>', methods=['GET'])
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


@app.route('/api/admin/scripts/<script>', methods=['POST'])
def run_script_with_args(script):
    module_name = get_module_name(script)
    if module_name is None:
        abort(400, description='"{}" is not valid script name'.format(script))

    body = get_input(request.json)
    if script == 'validate':
        try:
            if not body['row_id'] or not body['user_email']:
                abort(400, description='Failed to validate - user-email and row-id cannot be empty strings')
        except KeyError:
            abort(400, description='Failed to validate - user-email and row-id must exist')

    arguments = ['run_script', module_name, script, json.dumps(body)]
    job_id = yc_gc.sender.send('#'.join(arguments))

    yc_gc.LOGGER.info('job_id {}'.format(job_id))
    return ({'info': 'Verification successful', 'job-id': job_id, 'arguments': arguments[1:]}, 202)


@app.route('/api/admin/scripts', methods=['GET'])
def get_script_names():
    scripts_names = ['populate', 'runCapabilities', 'draftPull', 'draftPullLocal', 'openconfigPullLocal', 'statistics',
                     'recovery', 'elkRecovery', 'elkFill', 'resolveExpiration', 'mariadbRecovery']
    return {'data': scripts_names, 'info': 'Success'}


@app.route('/api/admin/disk-usage', methods=['GET'])
def get_disk_usage():
    total, used, free = shutil.disk_usage('/')
    usage = {}
    usage['total'] = total
    usage['used'] = used
    usage['free'] = free
    return {'data': usage, 'info': 'Success'}


### HELPER DEFINITIONS ###
def get_module_name(script_name):
    if script_name in ['populate', 'runCapabilities']:
        return 'parseAndPopulate'
    elif script_name in ['draftPull', 'draftPullLocal', 'openconfigPullLocal']:
        return 'ietfYangDraftPull'
    elif script_name in ['recovery', 'elkRecovery', 'elkFill', 'mariadbRecovery']:
        return 'recovery'
    elif script_name == 'statistics':
        return 'statistic'
    elif script_name == 'resolveExpiration':
        return 'utility'
    elif script_name == 'validate':
        return 'validate'
    else:
        return None


def hash_pw(password):
    if sys.version_info >= (3, 4):
        password = password.encode(encoding='utf-8', errors='strict')
    return hashlib.sha256(password).hexdigest()


def get_class_by_tablename(name):
    with current_app.app_context():
        for mapper in Base.registry.mappers:
            if mapper.class_.__tablename__ == name and hasattr(mapper.class_, '__tablename__'):
                return mapper.class_

def get_input(body):
    if body is None:
        abort(400, description='bad-request - body can not be empty')
    if 'input' not in body:
        abort(400, description='bad-request - body has to start with "input" and can not be empty')
    else:
        return body['input']
