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
import json
import math
import os
import re
from datetime import datetime

import MySQLdb
import requests
from flask import Blueprint, request, make_response, jsonify, g, session

from api.globalConfig import yc_gc
from api.views.admin.adminUser import AdminUser
from api.yangCatalogApi import hash_pw
from utility.util import create_signature
from validate import validate


class YangCatalogAdminBlueprint(Blueprint):

    def __init__(self, name, import_name, static_folder=None, static_url_path=None, template_folder=None,
                 url_prefix=None, subdomain=None, url_defaults=None, root_path=None):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder, url_prefix, subdomain,
                         url_defaults, root_path)

    def before_request(self, f):
        if 'admin' in request.path:
            g.user = None
            if 'user_id' in session:
                try:
                    db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser,
                                         passwd=yc_gc.dbPass)
                    # prepare a cursor object using cursor() method
                    cursor = db.cursor()
                    # execute SQL query using execute() method.
                    results_num = cursor.execute("""SELECT * FROM `admin_users` where Id=%s""", (session['user_id'],))
                    if results_num == 1:
                        data = cursor.fetchone()
                        g.user = AdminUser(data[0], data[1])
                    db.close()
                except MySQLdb.MySQLError as err:
                    if err.args[0] != 1049:
                        db.close()
                    yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
        return super().before_request(f)


app = YangCatalogAdminBlueprint('admin', __name__)


### ROUTE ENDPOINT DEFINITIONS ###
@app.route('/healthcheck', methods=['GET'])
def health_check():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    return make_response(jsonify({'info': 'success'}), 201)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session.pop('user_id', None)
        body = request.json
        input = body.get('input')
        if input is None:
            return make_response(jsonify({'error': 'missing "input" root json object'}), 400)
        username = input.get('username')
        password = hash_pw(input.get('password'))
        if username is None:
            return make_response(jsonify({'error': 'missing "userame" in json object'}), 400)
        if password is None:
            return make_response(jsonify({'error': 'missing "password" in json object'}), 400)
        try:
            db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser,
                                 passwd=yc_gc.dbPass)
            # prepare a cursor object using cursor() method
            cursor = db.cursor()
            # execute SQL query using execute() method.
            results_num = cursor.execute("""SELECT * FROM `admin_users` where Username=%s""", (username,))
            if results_num == 1:
                data = cursor.fetchone()
                if data[2] == password:
                    session['user_id'] = data[0]
                    yc_gc.LOGGER.info('session id {}'.format(session))
                    return make_response(jsonify({'info': 'Success'}), 200)
            db.close()
        except MySQLdb.MySQLError as err:
            if err.args[0] != 1049:
                db.close()
            yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
        return make_response(jsonify({'info': 'Bad authorization - username or password not correct'}), 401)


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return make_response(jsonify({'info': 'Success'}), 200)


@app.route('/create_user', methods=['POST'])
def create_admin_user():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    body = request.json
    input = body.get('input')
    if input is None:
        return make_response(jsonify({'error': 'missing "input" root json object'}), 400)
    username = input.get('username')
    password = hash_pw(input.get('password'))
    if username is None:
        return make_response(jsonify({'error': 'missing "userame" in json object'}), 400)
    if password is None:
        return make_response(jsonify({'error': 'missing "password" in json object'}), 400)
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser,
                             passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.

        cursor.execute("""INSERT INTO admin_users(Username, Password) VALUES (%s, %s)""", (username, password,))
        db.commit()
        db.close()
    except MySQLdb.MySQLError as err:
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))


@app.route('/directory-structure', methods=['GET'])
def get_var_yang_directory_structure():
    def walk_through_dir(path):
        structure = {'children': []}
        for root, dirs, files in os.walk(path):
            structure['name'] = os.path.basename(root)
            for f in files:
                b = {}
                b['name'] = f
                structure['children'].append(b)
            for dir in dirs:
                structure['children'].append(walk_through_dir('{}/{}'.format(path, dir)))
            break
        return structure

    yc_gc.LOGGER.info('Getting directory structure')

    ret = {'name': 'root', 'children': []}
    ret['children'].append(walk_through_dir('/var/yang'))
    response = {'info': 'Success',
                'data': ret}
    return make_response(jsonify(response), 200)


@app.route('/yangcatalog-nginx', methods=['GET'])
def read_yangcatalog_nginx_files():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    yc_gc.LOGGER.info('Getting list of nginx files')
    files = os.listdir('{}/sites-enabled'.format(yc_gc.nginx_dir))
    files_final = ['sites-enabled/' + sub for sub in files]
    files_final.append('nginx.conf')
    files = os.listdir('{}/conf.d'.format(yc_gc.nginx_dir))
    files_final.extend(['conf.d/' + sub for sub in files])
    response = {'info': 'Success',
                'data': files_final}
    return make_response(jsonify(response), 200)


@app.route('/yangcatalog-nginx/<path:nginx_file>', methods=['GET'])
def read_yangcatalog_nginx(nginx_file):
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    yc_gc.LOGGER.info('Reading nginx file {}'.format(nginx_file))
    with open('{}/{}'.format(yc_gc.nginx_dir, nginx_file), 'r') as f:
        nginx_config = f.read()
    response = {'info': 'Success',
                'data': nginx_config}
    return make_response(jsonify(response), 200)


@app.route('/yangcatalog-config', methods=['GET'])
def read_yangcatalog_config():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    yc_gc.LOGGER.info('Reading yangcatalog config file')

    with open(yc_gc.config_path, 'r') as f:
        yangcatalog_config = f.read()
    response = {'info': 'Success',
                'data': yangcatalog_config}
    return make_response(jsonify(response), 200)


@app.route('/yangcatalog-config', methods=['PUT'])
def update_yangcatalog_config():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    yc_gc.LOGGER.info('Updating yangcatalog config file')
    body = request.json
    input = body.get('input')
    if input is None or input.get('data') is None:
        return make_response(jsonify({'error': 'payload needs to have body with input and data container'}), 400)

    with open(yc_gc.config_path, 'w') as f:
        f.write(input['data'])
    resp = {'api': 'error loading data',
            'yang-search': 'error loading data',
            'receiver': 'error loading data'}
    yc_gc.load_config()
    resp['api'] = 'data loaded successfully'
    yc_gc.sender.send('reload_config')
    resp['receiver'] = 'data loaded succesfully'
    path = '{}://{}/yang-search/reload_config'.format(yc_gc.api_protocol, yc_gc.ip)
    signature = create_signature(yc_gc.search_key, json.dumps(input))

    response = requests.post(path, data=json.dumps(input),
                             headers={'Content-Type': 'app/json', 'Accept': 'app/json',
                                      'X-YC-Signature': 'sha1={}'.format(signature)}, verify=False)
    code = response.status_code

    if code != 200 and code != 201 and code != 204:
        yc_gc.LOGGER.error('could not send data to realod config. Reason: {}'
                           .format(response.text))
    else:
        resp['yang-search'] = response.json()['info']
    response = {'info': resp,
                'new-data': input['data']}
    return make_response(jsonify(response), 200)


@app.route('/logs', methods=['GET'])
def get_log_files():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)

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
    return make_response(jsonify({'info': 'success',
                                  'data': list(resp)}), 200)


@app.route('/logs', methods=['POST'])
def get_logs():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)

    def find_files(directory, pattern):
        for root, dirs, files in os.walk(directory):
            for basename in files:
                if fnmatch.fnmatch(basename, pattern):
                    filename = os.path.join(root, basename)
                    yield filename

    yc_gc.LOGGER.info('Reading yangcatalog log file')
    if request.json is None:
        return make_response(jsonify({'error': 'bad-request - body has to start with input and can not be empty'}), 400)

    body = request.json.get('input')

    if body is None:
        return make_response(jsonify({'error': 'bad-request - body has to start with input and can not be empty'}), 400)
    number_of_lines_per_page = body.get('lines-per-page', 1000)
    page_num = body.get('page', 1)
    filter = body.get('filter')
    from_date_timestamp = body.get('from-date', None)
    file_name = body.get('file-name', 'yang')
    log_files = []
    if from_date_timestamp is None:
        log_files.append('{}/{}.log'.format(yc_gc.logs_dir, body.get('file-name', 'yang')))
    else:
        files = find_files('{}/{}'.format(yc_gc.logs_dir, '/'.join(file_name.split('/')[:-1])),
                           "{}.log*".format(file_name.split('/')[:-1]))
        for f in files:
            if os.path.getmtime(f) >= from_date_timestamp:
                log_files.append(f)
    send_out = []
    yc_gc.LOGGER.debug(from_date_timestamp)
    if from_date_timestamp is None:
        with open(log_files[0], 'r') as f:
            for line in f.readlines():
                if from_date_timestamp is None:
                    try:
                        d = re.findall('([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))', line)[0][0]
                        t = re.findall('(?:[01]\d|2[0123]):(?:[012345]\d):(?:[012345]\d)', line)[0]
                        from_date_timestamp = datetime.strptime("{} {}".format(d, t), '%Y-%m-%d %H:%M:%S').timestamp()
                    except:
                        # ignore and accept
                        pass

    whole_line = ''
    yc_gc.LOGGER.debug(from_date_timestamp)
    with open(log_files[0], 'r') as f:
        file_stream = f.read()
        hits = re.findall(
            '(([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])) (?:(?:([01]?\d|2[0-3]):)?([0-5]?\d):)?([0-5]?\d)[ ][A-Z]{4,10}\s*(\S*.)\s*[=][>])',
            file_stream)
        if len(hits) > 1:
            format_text = True
        else:
            send_out.append(file_stream)
            format_text = False

    if format_text:
        for log_file in log_files:
            with open(log_file, 'r') as f:
                for line in reversed(f.readlines()):
                    line_timestamp = None
                    try:
                        d = re.findall('([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))', line)[0][0]
                        t = re.findall('(?:[01]\d|2[0123]):(?:[012345]\d):(?:[012345]\d)', line)[0]
                        line_beginning = "{} {}".format(d, t)
                        line_timestamp = datetime.strptime(line_beginning, '%Y-%m-%d %H:%M:%S').timestamp()
                    except:
                        # ignore and accept
                        pass
                    if line_timestamp is None or not line.startswith(line_beginning):
                        whole_line = '{}{}'.format(line, whole_line)
                        continue
                    if line_timestamp >= from_date_timestamp:
                        if filter is not None:
                            match_case = filter.get('match-case', False)
                            match_whole_words = filter.get("match-words", False)
                            filter_out = filter.get("filter-out", None)
                            searched_string = filter.get('search-for', '')
                            level = filter.get('level', '').upper()
                            if level != '':
                                level = ' {} '.format(level)
                            if match_whole_words:
                                if searched_string != '':
                                    searched_string = ' {} '.format(searched_string)
                            if level in line:
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

    if format_text:
        pages = math.ceil(len(send_out) / number_of_lines_per_page)
        len_send_out = len(send_out)
    else:
        pages = math.ceil(len(send_out[0].split('\n')) / number_of_lines_per_page)
        len_send_out = len(send_out[0])
    metadata = {'file-name': file_name,
                'from-date': from_date_timestamp,
                'lines-per-page': number_of_lines_per_page,
                'page': page_num,
                'pages': pages,
                'filter': filter,
                'format': format_text}
    from_line = (page_num - 1) * number_of_lines_per_page
    if page_num * number_of_lines_per_page > len_send_out:
        if format_text:
            output = send_out[from_line:]
        else:
            output = ['\n'.join(send_out[0].split('\n')[from_line:])]
    else:
        if format_text:
            output = send_out[from_line: page_num * number_of_lines_per_page]
        else:
            output = ['\n'.join(send_out[0].split('\n')[from_line: page_num * number_of_lines_per_page])]
    return make_response(jsonify({'meta': metadata,
                                  'output': output}), 200)


@app.route('/validate', methods=['POST'])
def validate_post():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    body = request.json
    if body.get('vendor-access') is None and body.get('sdo-access'):
        return make_response(jsonify({'info': 'Failed to validate - at least one of vendor-access or sdo-access'
                                              'must be filled in'}), 400)
    if body.get('vendor-access') is not None and body.get('vendor-path') is None:
        return make_response(jsonify({'info': 'Failed to validate - vendor-access True but no vendor-path given'}), 400)
    if body.get('sdo-access') is not None and body.get('sdo-path') is None:
        return make_response(jsonify({'info': 'Failed to validate - sdo-access True but no sdo-path given'}), 400)
    if body.get('row-id') is None or body.get('user-email') is None:
        return make_response(jsonify({'info': 'Failed to validate - user-email and row-id must exist'}), 400)
    validate.main(body.get('vendor-access'), body.get('vendor-path'), body.get('sdo-access'), body.get('sdo-path'),
                  body['row-id'], body['user-email'])
    return make_response(jsonify({'info': 'Successfully validated and written to MySQL database'}), 200)


@app.route('/sql-tables', methods=['GET'])
def get_sql_tables():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    return make_response(jsonify(['users', 'users_temp']), 200)


@app.route('/sql-tables/<table>', methods=['POST'])
def create_sql_row(table):
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    if table not in ['users', 'users_temp']:
        return make_response(jsonify({'error': 'table {} not implemented use only users or users_temp'.format(table)}),
                             501)
    body = request.json.get('input')
    if body is None:
        return make_response(jsonify({'error': 'bad request - did you not start with input json container?'}), 400)
    username = body.get('username')
    name = body.get('first-name')
    last_name = body.get('last-name')
    email = body.get('email')
    password = body.get('password')
    if body is None or username is None or name is None or last_name is None or email is None or password is None:
        return make_response(jsonify({'error': 'username - {}, firstname - {}, last-name - {},'
                                               ' email - {} and password - {} must be specified'.format(username,
                                                                                                        name,
                                                                                                        last_name,
                                                                                                        email,
                                                                                                        password)}),
                             400)
    models_provider = body.get('models-provider', '')
    sdo_access = body.get('access-rights-sdo', '')
    vendor_access = body.get('access-rights-vendor', '')
    if sdo_access == '' and vendor_access == '':
        return make_response(jsonify({'error': 'access-rights-sdo OR access-rights-vendor must be specified.'}), 400)
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser, passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        sql = """INSERT INTO `{}` (Username, Password, Email, ModelsProvider,
         FirstName, LastName, AccessRightsSdo, AccessRightsVendor) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""" \
            .format(table)
        cursor.execute(sql, (username, password, email, models_provider,
                             name, last_name, sdo_access, vendor_access,))
        db.commit()
        db.close()
        response = {'info': 'data successfully added to database',
                    'data': body}
        return make_response(jsonify(response), 201)
    except MySQLdb.MySQLError as err:
        if err.args[0] not in [1049, 2013]:
            db.close()
        yc_gc.LOGGER.error("Cannot connect to database. MySQL error: {}".format(err))
        return make_response(jsonify({'error': 'Server problem connecting to database'}), 500)


@app.route('/sql-tables/<table>/id/<unique_id>', methods=['DELETE'])
def delete_sql_row(table, unique_id):
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser, passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        sql = """SELECT * FROM `{}` WHERE Id = %s""".format(table)
        cursor.execute(sql, (unique_id,))

        data = cursor.fetchall()

        found = False
        for x in data:
            if x[0] == int(unique_id):
                found = True
        if found:
            # execute SQL query using execute() method.
            cursor = db.cursor()
            sql = """DELETE FROM `{}` WHERE Id = %s""".format(table)
            cursor.execute(sql, (unique_id,))
            db.commit()

        db.close()
    except MySQLdb.MySQLError as err:
        if err.args[0] not in [1049, 2013]:
            db.close()
        yc_gc.LOGGER.error("Cannot connect to database. MySQL error: {}".format(err))
        return make_response(jsonify({'error': 'Server problem connecting to database'}), 500)
    if found:
        return make_response(jsonify({'info': 'id {} deleted successfully'.format(unique_id)}), 200)
    else:
        return make_response(jsonify({'error': 'id {} not found in table {}'.format(unique_id, table)}), 404)


@app.route('/sql-tables/<table>', methods=['GET'])
def get_sql_rows(table):
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser, passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        sql = """SELECT * FROM {}""".format(table)
        cursor.execute(sql)
        data = cursor.fetchall()
        db.close()

    except MySQLdb.MySQLError as err:
        yc_gc.LOGGER.error("Cannot connect to database. MySQL error: {}".format(err))
        if err.args[0] not in [1049, 2013]:
            db.close()
        return make_response(jsonify({'error': 'Server problem connecting to database'}), 500)
    ret = []
    for row in data:
        data_set = {'id': row[0],
                    'username': row[1],
                    'email': row[3],
                    'models-provider': row[4],
                    'first-name': row[5],
                    'last-name': row[6],
                    'access-rights-sdo': row[7],
                    'access-rights-vendor': row[8]}
        ret.append(data_set)
    return make_response(jsonify(ret), 200)


@app.route('/scripts/<script>', methods=['GET'])
def get_script_details(script):
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)

    module_name = get_module_name(script)
    if module_name is None:
        return make_response(jsonify({'error': '"{}" is not valid script name'.format(script)}), 400)

    module = __import__(module_name, fromlist=[script])
    submodule = getattr(module, script)
    script_conf = submodule.ScriptConfig()
    script_args_list = script_conf.get_args_list()
    script_args_list.pop('credentials', None)
    return make_response(jsonify({'data': script_args_list}), 200)


@app.route('/scripts/<script>', methods=['POST'])
def run_script_with_args(script):
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)

    module_name = get_module_name(script)
    if module_name is None:
        return make_response(jsonify({'error': '"{}" is not valid script name'.format(script)}), 400)

    body = request.json

    if body is None:
        return make_response(jsonify({'error': 'body of request is empty'}), 400)
    if body.get('input') is None:
        return make_response(jsonify({'error': 'body of request need to start with input'}), 400)
    if script == 'validate':
        try:
            if not body['input']['row_id'] or not body['input']['user_email']:
                return make_response(jsonify({'info': 'Failed to validate - user-email and row-id cannot be empty strings'}), 400)
        except:
            return make_response(jsonify({'info': 'Failed to validate - user-email and row-id must exist'}), 400)

    arguments = ['run_script', module_name, script, json.dumps(body['input'])]
    job_id = yc_gc.sender.send('#'.join(arguments))

    yc_gc.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id, 'arguments': arguments[1:]}), 202)


@app.route('/scripts', methods=['GET'])
def get_script_names():
    if 'user_id' not in session:
        return make_response(jsonify({'info': 'not yet Authorized'}), 401)

    scripts_names = ['populate', 'runCapabilities', 'draftPull', 'draftPullLocal', 'openconfigPullLocal', 'statistics',
                     'recovery', 'elkRecovery', 'elkFill', 'resolveExpiration', 'validate']
    return make_response(jsonify({'data': scripts_names, 'info': 'Success'}), 200)


### HELPER DEFINITIONS ###
def get_module_name(script_name):
    if script_name == 'populate' or script_name == 'runCapabilities':
        return 'parseAndPopulate'
    elif script_name == 'draftPull' or script_name == 'draftPullLocal' or script_name == 'openconfigPullLocal':
        return 'ietfYangDraftPull'
    elif script_name == 'recovery' or script_name == 'elkRecovery' or script_name == 'elkFill':
        return 'recovery'
    elif script_name == 'statistics':
        return 'statistic'
    elif script_name == 'resolveExpiration':
        return 'utility'
    elif script_name == 'validate':
        return 'validate'
    else:
        return None
