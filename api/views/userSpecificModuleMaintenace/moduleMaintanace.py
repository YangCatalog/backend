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

import base64
import errno
import json
import os
import shutil
import sys
from datetime import datetime

import MySQLdb
import requests
from flask import Blueprint, request, abort, make_response, jsonify
from git import GitCommandError

from api.authentication.auth import auth, hash_pw
from api.globalConfig import yc_gc
from utility import repoutil, yangParser
from utility.messageFactory import MessageFactory

NS_MAP = {
    "http://cisco.com/": "cisco",
    "http://www.huawei.com/netconf": "huawei",
    "http://openconfig.net/yang": "openconfig",
    "http://tail-f.com/": "tail-f",
    "http://yang.juniper.net/": "juniper"
}
url = 'https://github.com/'


class UserSpecificModuleMaintenance(Blueprint):

    def __init__(self, name, import_name, static_folder=None, static_url_path=None, template_folder=None,
                 url_prefix=None, subdomain=None, url_defaults=None, root_path=None):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder, url_prefix, subdomain,
                         url_defaults, root_path)


app = UserSpecificModuleMaintenance('userSpecificModuleMaintenance', __name__)


### ROUTE ENDPOINT DEFINITIONS ###
@app.route('/register-user', methods=['POST'])
def register_user():
    if not request.json:
        return abort(400, description='bad request - no data received')
    body = request.json
    for data in ['username', 'password', 'password-confirm', 'email', 'company', 'first-name', 'last-name']:
        if data not in body:
            return abort(400, description='bad request - missing {} data in input'.format(data))
    username = body['username']

    password = hash_pw(body['password'])
    email = body['email']
    confirm_password = hash_pw(body['password-confirm'])
    models_provider = body['company']
    name = body['first-name']
    last_name = body['last-name']
    if password != confirm_password:
        return abort(400, 'Passwords do not match')
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser, passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        results_num = cursor.execute("""SELECT Username FROM `users` where Username=%s""", (username,))
        if results_num >= 1:
            return abort(409, 'User with username {} already exists'.format(username))
        results_num = cursor.execute("""SELECT Username FROM `users_temp` where Username=%s""", (username,))
        if results_num >= 1:
            return abort(409, 'User with username {} is pending for permissions'.format(username))

        sql = """INSERT INTO `{}` (Username, Password, Email, ModelsProvider,
         FirstName, LastName) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""" \
            .format('users_temp')
        cursor.execute(sql, (username, password, email, models_provider,
                             name, last_name,))
        db.commit()
        db.close()
    except MySQLdb.MySQLError as err:
        if err.args[0] != 1049:
            db.close()
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
    mf = MessageFactory()
    mf.send_new_user(username, email)
    return make_response(jsonify({'info': 'User created successfully'}), 201)


@app.route('/modules/module/<name>,<revision>,<organization>', methods=['DELETE'])
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
    yc_gc.LOGGER.info(
        'deleting module with name, revision and organization {} {} {}'.format(name, revision, organization))
    username = request.authorization['username']
    yc_gc.LOGGER.debug('Checking authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser, passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        results_num = cursor.execute("""SELECT * FROM `users` where Username=%s""", (username,))
        if results_num == 1:
            data = cursor.fetchone()
            accessRigths = data[7]
        db.close()
    except MySQLdb.MySQLError as err:
        if err.args[0] != 1049:
            db.close()
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))
    response = requests.get(yc_gc.protocol + '://' + yc_gc.confd_ip + ':' + repr(
        yc_gc.confdPort) + '/restconf/data/yang-catalog:catalog/modules/module/' + name +
                            ',' + revision + ',' + organization,
                            auth=(yc_gc.credentials[0], yc_gc.credentials[1]),
                            headers={'Content-type': 'application/yang-data+json',
                                     'Accept': 'application/yang-data+json'})
    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        return abort(404, description='Module not found in confd database')
    read = response.json()
    if read['yang-catalog:module']['organization'] != accessRigths and accessRigths != '/':
        return abort(401, description="You do not have rights to delete module with organization {}"
                     .format(read['yang-catalog:module']['organization']))

    if read['yang-catalog:module'].get('implementations') is not None:
        return abort(400, description='This module has reference in vendors branch')

    all_mods = requests.get('{}search/modules'.format(yc_gc.yangcatalog_api_prefix)).json()

    for existing_module in all_mods['module']:
        if existing_module.get('dependencies') is not None:
            dependency = existing_module['dependencies']
            for dep in dependency:
                if dep['name'] == name and dep.get('revision') == revision:
                    return abort(400, description='{}@{} module has reference in another module dependency: {}@{}'
                                 .format(name, revision, existing_module['name'], existing_module['revision']))
        if existing_module.get('submodule') is not None:
            submodule = existing_module['submodule']
            for sub in submodule:
                if sub['name'] == name and sub.get('revision') == revision:
                    return abort(400, description='{}@{} module has reference in another module submodule: {}@{}'
                                 .format(name, revision, existing_module['name'], existing_module['revision']))
    path_to_delete = yc_gc.protocol + '://' + yc_gc.confd_ip + ':' + repr(
        yc_gc.confdPort) + '/restconf/data/yang-catalog:catalog/modules/module=' \
                     + name + ',' + revision + ',' + organization

    arguments = [yc_gc.protocol, yc_gc.confd_ip, repr(yc_gc.confdPort), yc_gc.credentials[0],
                 yc_gc.credentials[1], path_to_delete, 'DELETE', yc_gc.api_protocol, repr(yc_gc.api_port)]
    job_id = yc_gc.sender.send('#'.join(arguments))

    yc_gc.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


@app.route('/modules', methods=['DELETE'])
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
        abort(400, description="Missing input data to know which modules we want to delete")
    username = request.authorization['username']
    yc_gc.LOGGER.debug('Checking authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser, passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        results_num = cursor.execute("""SELECT * FROM `users` where Username=%s""", (username,))
        if results_num == 1:
            data = cursor.fetchone()
            accessRigths = data[7]
        db.close()
    except MySQLdb.MySQLError as err:
        if err.args[0] != 1049:
            db.close()
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))

    rpc = request.json
    if rpc.get('input'):
        modules = rpc['input'].get('modules')
    else:
        return abort(404, description="Data must start with input root element in json")
    for mod in modules:
        response = requests.get(yc_gc.protocol + '://' + yc_gc.confd_ip + ':' + repr(
            yc_gc.confdPort) + '/restconf/data/yang-catalog:catalog/modules/module=' + mod['name'] +
                                ',' + mod['revision'] + ',' + mod['organization'],
                                auth=(yc_gc.credentials[0], yc_gc.credentials[1]),
                                headers={'Content-type': 'application/yang-data+json',
                                         'Accept': 'application/yang-data+json'})
        if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
            return abort(404, description="module {}@{}/{} not found in confd database"
                         .format(mod['name'], mod['revision'], mod['organization']))
        read = response.json()

        if read['yang-catalog:module']['organization'] != accessRigths and accessRigths != '/':
            return abort(401, description="you do not have rights to delete module with organization {}"
                         .format(accessRigths))

        if read['yang-catalog:module'].get('implementations') is not None:
            return abort(400, description='This module has reference in vendors branch')

    all_mods = requests.get('{}search/modules'.format(yc_gc.yangcatalog_api_prefix)).json()

    for mod in modules:
        for existing_module in all_mods['module']:
            if existing_module.get('dependencies') is not None:
                dependency = existing_module['dependencies']
                for dep in dependency:
                    if dep['name'] == mod['name'] and dep.get('revision') == mod['revision']:
                        will_be_deleted = False
                        for mod2 in modules:
                            if mod2['name'] == existing_module['name'] and mod2['revision'] == existing_module[
                                'revision']:
                                will_be_deleted = True
                                break
                        if not will_be_deleted:
                            return abort(400,
                                         description='{}@{} module has reference in another module dependency: {}@{}'
                                         .format(mod['name'], mod['revision'], existing_module['name'],
                                                 existing_module['revision']))
            if existing_module.get('submodule') is not None:
                submodule = existing_module['submodule']
                for sub in submodule:
                    if sub['name'] == mod['name'] and sub.get('revision') == mod['revision']:
                        will_be_deleted = False
                        for mod2 in modules:
                            if mod2['name'] == existing_module['name'] and mod2['revision'] == existing_module[
                                'revision']:
                                will_be_deleted = True
                                break
                        if not will_be_deleted:
                            return abort(400,
                                         description='{}@{} module has reference in another module submodule: {}@{}'
                                         .format(mod['name'], mod['revision'], existing_module['name'],
                                                 existing_module['revision']))

    path_to_delete = json.dumps(rpc['input'])

    arguments = [yc_gc.protocol, yc_gc.confd_ip, repr(yc_gc.confdPort), yc_gc.credentials[0],
                 yc_gc.credentials[1], path_to_delete, 'DELETE_MULTIPLE',
                 yc_gc.api_protocol, repr(yc_gc.api_port)]
    job_id = yc_gc.sender.send('#'.join(arguments))

    yc_gc.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


@app.route('/vendors/<path:value>', methods=['DELETE'])
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
    yc_gc.LOGGER.info('Deleting vendor on path {}'.format(value))
    username = request.authorization['username']
    yc_gc.LOGGER.debug('Checking authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser, passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        results_num = cursor.execute("""SELECT * FROM `users` where Username=%s""", (username,))
        if results_num == 1:
            data = cursor.fetchone()
            accessRigths = data[8]
        db.close()
    except MySQLdb.MySQLError as err:
        if err.args[0] != 1049:
            db.close()
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))

    if accessRigths.startswith('/') and len(accessRigths) > 1:
        accessRigths = accessRigths[1:]
    rights = accessRigths.split('/')
    check_vendor = None
    check_platform = None
    check_software_version = None
    check_software_flavor = None
    if not rights[0] == '':
        check_vendor = rights[0]
        if len(rights) > 1:
            check_platform = rights[1]
        if len(rights) > 2:
            check_software_version = rights[2]
        if len(rights) > 3:
            check_software_flavor = rights[3]

    path_to_delete = '{}://{}:{}/restconf/data/yang-catalog:catalog/vendors/{}'.format(yc_gc.protocol,
                                                                                       yc_gc.confd_ip,
                                                                                       yc_gc.confdPort, value)

    vendor = 'None'
    platform = 'None'
    software_version = 'None'
    software_flavor = 'None'
    if '/vendor/' in path_to_delete:
        vendor = path_to_delete.split('/vendor/')[1].split('/')[0]
        path_to_delete = path_to_delete.replace('/vendor/', '/vendor=')
    if '/platform/' in path_to_delete:
        platform = path_to_delete.split('/platform/')[1].split('/')[0]
        path_to_delete = path_to_delete.replace('/platform/', '/platform=')
    if '/software-version/' in path_to_delete:
        software_version = path_to_delete.split('/software-version/')[1].split('/')[0]
        path_to_delete = path_to_delete.replace('/software-version/', '/software-version=')
    if '/software-flavor/' in path_to_delete:
        software_flavor = path_to_delete.split('/software-flavor/')[1].split('/')[0]
        path_to_delete = path_to_delete.replace('/software-flavor/', '/software-flavor=')

    if check_platform and platform != check_platform:
        return abort(401, description="User not authorized to supply data for this platform")
    if check_software_version and software_version != check_software_version:
        return abort(401, description="User not authorized to supply data for this software version")
    if check_software_flavor and software_flavor != check_software_flavor:
        return abort(401, description="User not authorized to supply data for this software flavor")
    if check_vendor and vendor != check_vendor:
        return abort(401, description="User not authorized to supply data for this vendor")

    arguments = [vendor, platform, software_version, software_flavor, yc_gc.protocol, yc_gc.confd_ip,
                 repr(yc_gc.confdPort), yc_gc.credentials[0],
                 yc_gc.credentials[1], path_to_delete, 'DELETE', yc_gc.api_protocol, repr(yc_gc.api_port)]
    job_id = yc_gc.sender.send('#'.join(arguments))

    yc_gc.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


@app.route('/modules', methods=['PUT', 'POST'])
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
        return abort(400, description='bad request - you need to input json body that conforms with'
                                      ' module-metadata.yang module. Received no json')
    body = request.json
    modules_cont = body.get('modules')
    if modules_cont is None:
        return abort(400, description='bad request - "modules" json object is missing and is mandatory')
    module_list = modules_cont.get('module')
    if module_list is None:
        return abort(400, description='bad request - "module" json list is missing and is mandatory')

    yc_gc.LOGGER.info('Adding modules with body {}'.format(body))
    tree_created = False

    with open('./prepare-sdo.json', "w") as plat:
        json.dump(body, plat)
    shutil.copy('./prepare-sdo.json', yc_gc.save_requests + '/sdo-'
                + str(datetime.utcnow()).split('.')[0].replace(' ', '_') + '-UTC.json')

    path = yc_gc.protocol + '://' + yc_gc.confd_ip + ':' + repr(
        yc_gc.confdPort) + '/restconf/data/module-metadata:modules'

    str_to_encode = '%s:%s' % (yc_gc.credentials[0], yc_gc.credentials[1])
    if sys.version_info >= (3, 4):
        str_to_encode = str_to_encode.encode(encoding='utf-8', errors='strict')
    base64string = base64.b64encode(str_to_encode)
    if sys.version_info >= (3, 4):
        base64string = base64string.decode(encoding='utf-8', errors='strict')
    response = requests.put(path, json.dumps(body), headers={'Authorization': 'Basic ' + base64string,
                                                             'Content-type': 'application/yang-data+json',
                                                             'Accept': 'application/yang-data+json'})

    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        return abort(400, description="The body you have provided could not be parsed. Confd error text: {} \n"
                                      " error code: {} \n error header items: {}"
                     .format(response.text, response.status_code, response.headers.items()))
    repo = {}
    warning = []

    direc = 0
    while True:
        if os.path.isdir('{}/{}'.format(yc_gc.temp_dir, direc)):
            direc += 1
        else:
            break
    direc = '{}/{}'.format(yc_gc.temp_dir, direc)
    try:
        os.makedirs(direc)
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            raise
    repo_url_dir_branch = {}
    for mod in module_list:
        yc_gc.LOGGER.info('{}'.format(mod))
        sdo = mod.get('source-file')
        if sdo is None:
            return abort(400,
                         description='bad request - at least one of modules "source-file" is missing and is mandatory')
        orgz = mod.get('organization')
        if orgz is None:
            return abort(400,
                         description='bad request - at least one of modules "organization" is missing and is mandatory')
        mod_name = mod.get('name')
        if mod_name is None:
            return abort(400, description='bad request - at least one of modules "name" is missing and is mandatory')
        mod_revision = mod.get('revision')
        if mod_revision is None:
            return abort(400,
                         description='bad request - at least one of modules "revision" is missing and is mandatory')
        if request.method == 'POST':
            path = '{}://{}:{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}'.format(yc_gc.protocol,
                                                                                                  yc_gc.confd_ip,
                                                                                                  yc_gc.confdPort,
                                                                                                  mod_name,
                                                                                                  mod_revision, orgz)
            response = requests.get(path, auth=(yc_gc.credentials[0], yc_gc.credentials[1]),
                                    headers={'Accept': 'application/yang-data+json'})
            if response.status_code != 404:
                continue
        sdo_path = sdo.get('path')
        if sdo_path is None:
            return abort(400, description=
            'bad request - at least one of modules source file "path" is missing and is mandatory')
        sdo_repo = sdo.get('repository')
        if sdo_repo is None:
            return abort(400, description=
            'bad request - at least one of modules source file "repository" is missing and is mandatory')
        sdo_owner = sdo.get('owner')
        if sdo_owner is None:
            return abort(400, description=
            'bad request - at least one of modules source file "owner" is missing and is mandatory')
        directory = '/'.join(sdo_path.split('/')[:-1])

        repo_url = '{}{}/{}'.format(url, sdo_owner, sdo_repo)
        if repo_url not in repo:
            yc_gc.LOGGER.info('Downloading repo {}'.format(repo_url))
            try:
                repo[repo_url] = repoutil.RepoUtil(repo_url)
                repo[repo_url].clone()
            except GitCommandError as e:
                return abort(400, description='bad request - cound not clone the github repository. Please check owner,'
                                              ' repository and path of the request - {}'.format(e.stderr))

        try:
            if sdo.get('branch'):
                branch = sdo.get('branch')
            else:
                branch = 'master'
            repo_url_dir_branch_temp = '{}/{}/{}'.format(repo_url, branch, directory)
            if repo_url_dir_branch.get(repo_url_dir_branch_temp) is None:
                branch = repo[repo_url].get_commit_hash(directory, branch)
                repo_url_dir_branch[repo_url_dir_branch_temp] = branch
            else:
                branch = repo_url_dir_branch[repo_url_dir_branch_temp]
        except GitCommandError as e:
            return abort(400, description='bad request - cound not clone the github repository. Please check owner,'
                                          ' repository and path of the request - {}'.format(e.stderr))
        save_to = '{}/temp/{}/{}/{}/{}'.format(direc, sdo_owner, sdo_repo.split('.')[0], branch, directory)
        try:
            os.makedirs(save_to)
        except OSError as e:
            # be happy if someone already created the path
            if e.errno != errno.EEXIST:
                raise
        shutil.copy('{}/{}'.format(repo[repo_url].localdir, sdo_path), save_to)

        tree_created = True
        organization = ''
        try:
            namespace = yangParser.parse(os.path.abspath('{}/{}'.format(save_to, sdo_path.split('/')[-1]))) \
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
                    belongs_to = yangParser.parse(os.path.abspath('{}/{}'.format(repo[repo_url].localdir, sdo_path))) \
                        .search('belongs-to')[0].arg
                except:
                    break
                try:
                    namespace = yangParser.parse(os.path.abspath('{}/{}/{}.yang'.format(repo[repo_url].localdir,
                                                                                        '/'.join(
                                                                                            sdo_path.split('/')[:-1]),
                                                                                        belongs_to))) \
                        .search('namespace')[0].arg
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
            if isinstance(resolved_authorization, str):
                return abort(401, description="You can not remove module with organization {}".format(organization))
            else:
                return abort(401, description="Unauthorized for server unknown reason")
        if 'organization' in repr(resolved_authorization):
            warning.append('{} {}'.format(sdo['path'].split('/')[-1], resolved_authorization))

    if os.path.isfile('./prepare-sdo.json'):
        shutil.move('./prepare-sdo.json', direc)
    for key in repo:
        repo[key].remove()

    yc_gc.LOGGER.debug('Sending a new job')
    populate_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)) + "/../../../parseAndPopulate/populate.py")
    arguments = ["python", populate_path, "--sdo", "--port", repr(yc_gc.confdPort), "--dir", direc, "--api",
                 "--ip", yc_gc.confd_ip, "--credentials", yc_gc.credentials[0], yc_gc.credentials[1],
                 repr(tree_created), yc_gc.protocol, yc_gc.api_protocol, repr(yc_gc.api_port)]
    job_id = yc_gc.sender.send('#'.join(arguments))
    yc_gc.LOGGER.info('job_id {}'.format(job_id))
    if len(warning) > 0:
        return jsonify({'info': 'Verification successful', 'job-id': job_id, 'warnings': [{'warning': val}
                                                                                          for val in warning]})
    else:
        return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


@app.route('/platforms', methods=['PUT', 'POST'])
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
        return abort(400, description='bad request - you need to input json body that conforms with'
                                      ' platform-implementation-metadata.yang module. Received no json')
    body = request.json

    platforms_cont = body.get('platforms')
    if platforms_cont is None:
        return abort(400, description='bad request - "platforms" json object is missing and is mandatory')
    platform_list = platforms_cont.get('platform')
    if platform_list is None:
        return abort(400, description='bad request - "platform" json list is missing and is mandatory')

    yc_gc.LOGGER.info('Adding vendor with body {}'.format(body))
    tree_created = False
    resolved_authorization = authorize_for_vendors(request, body)
    if 'passed' != resolved_authorization:
        return resolved_authorization
    with open(yc_gc.save_requests + '/vendor-' + str(datetime.utcnow()).split('.')[0].replace(' ', '_') +
              '-UTC.json', "w") as plat:
        json.dump(body, plat)

    path = '{}://{}:{}/restconf/data/platform-implementation-metadata:platforms'.format(yc_gc.protocol, yc_gc.confd_ip,
                                                                                        yc_gc.confdPort)

    str_to_encode = '%s:%s' % (yc_gc.credentials[0], yc_gc.credentials[1])
    if sys.version_info >= (3, 4):
        str_to_encode = str_to_encode.encode(encoding='utf-8', errors='strict')
    base64string = base64.b64encode(str_to_encode)
    if sys.version_info >= (3, 4):
        base64string = base64string.decode(encoding='utf-8', errors='strict')
    response = requests.put(path, json.dumps(body), headers={'Authorization': 'Basic ' + base64string,
                                                             'Content-type': 'application/yang-data+json',
                                                             'Accept': 'application/yang-data+json'})

    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        return abort(400, description="The body you have provided could not be parsed. Confd error text: {} \n"
                                      " error code: {} \n error header items: {}"
                     .format(response.text, response.status_code, response.headers.items()))

    repo = {}

    direc = 0
    while True:
        if os.path.isdir('{}/{}'.format(yc_gc.temp_dir, direc)):
            direc += 1
        else:
            break
    direc = '{}/{}'.format(yc_gc.temp_dir, direc)
    try:
        os.makedirs(direc)
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            raise

    repo_url_dir_branch = {}
    for platform in platform_list:
        capability = platform.get('module-list-file')
        if capability is None:
            return abort(400, description=
            'bad request - at least on of platform "module-list-file" is missing and is mandatory')
        capability_path = capability.get('path')
        if capability_path is None:
            return abort(400, description=
            'bad request - at least on of platform module-list-file "path" for module is missing and is mandatory')
        file_name = capability_path.split('/')[-1]
        repository = capability.get('repository')
        if repository is None:
            return abort(400, description=
            'bad request - at least on of platform module-list-file  "repository" for module is missing and is mandatory')
        owner = capability.get('owner')
        if owner is None:
            return abort(400, description=
            'bad request - at least on of platform module-list-file  "owner" for module is missing and is mandatory')
        if request.method == 'POST':
            repo_split = repository.split('.')[0]
            repoutil.pull(yc_gc.yang_models)
            if os.path.isfile(yc_gc.yang_models + '/vendor/' + owner + '/' + repo_split + '/' + capability_path):
                continue

        directory = '/'.join(capability_path.split('/')[:-1])
        repo_url = '{}{}/{}'.format(url, owner, repository)

        if repo_url not in repo:
            yc_gc.LOGGER.info('Downloading repo {}'.format(repo_url))
            try:
                repo[repo_url] = repoutil.RepoUtil(repo_url)
                repo[repo_url].clone()
            except GitCommandError as e:
                return abort(400, description='bad request - cound not clone the github repository. Please check owner,'
                                              ' repository and path of the request - {}'.format(e.stderr))
        try:
            if capability.get('branch'):
                branch = capability.get('branch')
            else:
                branch = 'master'
            repo_url_dir_branch_temp = '{}/{}/{}'.format(repo_url_dir_branch, directory, branch)
            if repo_url_dir_branch.get(repo_url_dir_branch_temp) is None:
                branch = repo[repo_url].get_commit_hash(directory, branch)
                repo_url_dir_branch[repo_url_dir_branch_temp] = branch
            else:
                branch = repo_url_dir_branch[repo_url_dir_branch_temp]
        except GitCommandError as e:
            return abort(400, description='bad request - cound not clone the github repository. Please check owner,'
                                          ' repository and path of the request - {}'.format(e.stderr))
        save_to = '{}/temp/{}/{}/{}/{}'.format(direc, owner, repository.split('.')[0], branch, directory)

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
    populate_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)) + "/../../../parseAndPopulate/populate.py")
    arguments = ["python", populate_path, "--port", repr(yc_gc.confdPort), "--dir", direc, "--api", "--ip",
                 yc_gc.confd_ip, "--credentials", yc_gc.credentials[0], yc_gc.credentials[1],
                 repr(tree_created), yc_gc.integrity_file_location, yc_gc.protocol,
                 yc_gc.api_protocol, repr(yc_gc.api_port)]
    job_id = yc_gc.sender.send('#'.join(arguments))
    yc_gc.LOGGER.info('job_id {}'.format(job_id))
    return make_response(jsonify({'info': 'Verification successful', 'job-id': job_id}), 202)


def authorize_for_vendors(request, body):
    """Authorize sender whether he has rights to send data via API to confd.
       Checks if sender has access on a given branch
                Arguments:
                    :param body: (str) json body of the request.
                    :param request: (request) Request sent to api.
                    :return whether authorization passed.
    """
    username = request.authorization['username']
    yc_gc.LOGGER.info('Checking vendor authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser, passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        results_num = cursor.execute("""SELECT * FROM `users` where Username=%s""", (username,))
        if results_num == 1:
            data = cursor.fetchone()
            accessRigths = data[8]
        db.close()
    except MySQLdb.MySQLError as err:
        if err.args[0] != 1049:
            db.close()
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))

    if accessRigths.startswith('/') and len(accessRigths) > 1:
        accessRigths = accessRigths[1:]
    rights = accessRigths.split('/')
    check_vendor = None
    check_platform = None
    check_software_version = None
    check_software_flavor = None
    if rights[0] == '':
        return 'passed'
    else:
        check_vendor = rights[0]
    if len(rights) > 1:
        check_platform = rights[1]
    if len(rights) > 2:
        check_software_version = rights[2]
    if len(rights) > 3:
        check_software_flavor = rights[3]

    for platform in body['platforms']['platform']:
        vendor = platform['vendor']
        platform_name = platform['name']
        software_version = platform['software-version']
        software_flavor = platform['software-flavor']

        if check_platform and platform_name != check_platform:
            return abort(401, description="User not authorized to supply data for this platform")
        if check_software_version and software_version != check_software_version:
            return abort(401, description="User not authorized to supply data for this software version")
        if check_software_flavor and software_flavor != check_software_flavor:
            return abort(401, description="User not authorized to supply data for this software flavor")
        if vendor != check_vendor:
            return abort(401, description="User not authorized to supply data for this vendor")
    return 'passed'


def authorize_for_sdos(request, organizations_sent, organization_parsed):
    """Authorize sender whether he has rights to send data via API to confd.
            Arguments:
                :param organization_parsed: (str) organization of a module sent by sender.
                :param organizations_sent: (str) organization of a module parsed from module.
                :param request: (request) Request sent to api.
                :return whether authorization passed.
    """
    username = request.authorization['username']
    yc_gc.LOGGER.info('Checking sdo authorization for user {}'.format(username))
    accessRigths = None
    try:
        db = MySQLdb.connect(host=yc_gc.dbHost, db=yc_gc.dbName, user=yc_gc.dbUser, passwd=yc_gc.dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        results_num = cursor.execute("""SELECT * FROM `users` where Username=%s""", (username,))
        if results_num == 1:
            data = cursor.fetchone()
            accessRigths = data[7]
        db.close()
    except MySQLdb.MySQLError as err:
        if err.args[0] != 1049:
            db.close()
        yc_gc.LOGGER.error('Cannot connect to database. MySQL error: {}'.format(err))

    passed = False
    if accessRigths == '/':
        if organization_parsed != organizations_sent:
            return "module`s organization is not the same as organization provided"
        return True
    if organizations_sent in accessRigths.split(','):
        if organization_parsed != organizations_sent:
            return "module`s organization is not in users rights"
        passed = True
    return passed


@app.route('/job/<job_id>', methods=['GET'])
def get_job(job_id):
    """Search for a job_id to see the process of the job
                :return response to the request with the job
    """
    yc_gc.LOGGER.info('Searching for job_id {}'.format(job_id))
    # EVY result = application.sender.get_response(job_id)
    result = yc_gc.sender.get_response(job_id)
    split = result.split('#split#')

    reason = None
    if split[0] == 'Failed':
        result = split[0]
        if len(split) == 2:
            reason = split[1]
        else:
            reason = ''

    return jsonify({'info': {'job-id': job_id,
                             'result': result,
                             'reason': reason}
                    })
