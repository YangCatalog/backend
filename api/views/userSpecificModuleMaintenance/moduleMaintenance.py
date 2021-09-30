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

import requests
from api.authentication.auth import auth, hash_pw
from api.models import TempUser, User
from flask import Blueprint, abort
from flask import current_app as app
from flask import jsonify, make_response, request
from git import GitCommandError
from sqlalchemy.exc import SQLAlchemyError
from utility import repoutil, yangParser
from utility.messageFactory import MessageFactory
from utility.staticVariables import NS_MAP, confd_headers, github_url


class UserSpecificModuleMaintenance(Blueprint):

    def __init__(self, name, import_name, static_folder=None, static_url_path=None, template_folder=None,
                 url_prefix=None, subdomain=None, url_defaults=None, root_path=None):
        super().__init__(name, import_name, static_folder, static_url_path, template_folder, url_prefix, subdomain,
                         url_defaults, root_path)


bp = UserSpecificModuleMaintenance('userSpecificModuleMaintenance', __name__)

@bp.before_request
def set_config():
    global ac, db
    ac = app.config
    db = ac.sqlalchemy


### ROUTE ENDPOINT DEFINITIONS ###
@bp.route('/register-user', methods=['POST'])
def register_user():
    if not request.json:
        abort(400, description='bad request - no data received')
    body = request.json
    for data in ['username', 'password', 'password-confirm', 'email',
                 'company', 'first-name', 'last-name', 'motivation']:
        if data not in body:
            abort(400, description='bad request - missing {} data in input'.format(data))
    username = body['username']

    password = hash_pw(body['password'])
    email = body['email']
    confirm_password = hash_pw(body['password-confirm'])
    models_provider = body['company']
    name = body['first-name']
    last_name = body['last-name']
    motivation = body['motivation']
    if password != confirm_password:
        abort(400, 'Passwords do not match')
    try:
        if db.session.query(User).filter_by(Username=username).all():
            abort(409, 'User with username {} already exists'.format(username))
        if db.session.query(TempUser).filter_by(Username=username).all():
            abort(409, 'User with username {} is pending for permissions'.format(username))
        temp_user = TempUser(Username=username, Password=password, Email=email, ModelsProvider=models_provider,
                             FirstName=name, LastName=last_name, Motivation=motivation,
                             RegistrationDatetime=datetime.utcnow())
        db.session.add(temp_user)
        db.session.commit()
    except SQLAlchemyError as err:
        app.logger.error('Cannot connect to database. MySQL error: {}'.format(err))
        return ({'error': 'Server problem connecting to database'}, 500)
    mf = MessageFactory()
    mf.send_new_user(username, email, motivation)
    return ({'info': 'User created successfully'}, 201)

@bp.route('/modules/module/<name>,<revision>,<organization>', methods=['DELETE'])
@bp.route('/modules', methods=['DELETE'])
@auth.login_required
def delete_modules(name: str = '', revision: str = '', organization: str = ''):
    """Delete a specific modules defined with name, revision and organization. This is
    not done right away but it will send a request to receiver which will work on deleting
    while this request will send a job_id of the request which user can use to see the job
    process.

    Arguments:
        :return response to the request with job_id that user can use to
            see if the job is still on or Failed or Finished successfully
    """
    if all((name, revision, organization)):
        input_modules = [{
            'name': name,
            'revision': revision,
            'organization': organization
        }]
    else:
        if not request.json:
            abort(400, description='Missing input data to know which modules we want to delete')
        rpc = request.json
        if rpc.get('input'):
            input_modules = rpc['input'].get('modules', [])
        else:
            abort(404, description="Data must start with 'input' root element in json")

    username = request.authorization['username']
    app.logger.debug('Checking authorization for user {}'.format(username))
    accessRigths = get_user_access_rights(username)

    unavailable_modules = []
    for mod in input_modules:
        response = get_mod_confd(mod['name'], mod['revision'], mod['organization'])
        if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
            # If admin, then possible to delete this module from other's modules dependents
            if accessRigths != '/':
                unavailable_modules.append(mod)
            continue
        read = response.json()

        if read['yang-catalog:module'][0].get('organization') != accessRigths and accessRigths != '/':
            abort(401, description='You do not have rights to delete modules with organization {}'
                       .format(read['yang-catalog:module'][0].get('organization')))

        if read['yang-catalog:module'][0].get('implementations') is not None:
            unavailable_modules.append(mod)

    # Filter out unavailble modules
    input_modules = [x for x in input_modules if x not in unavailable_modules]
    path_to_delete = json.dumps({'modules':input_modules})

    arguments = [ac.g_protocol_confd, ac.w_confd_ip, ac.w_confd_port, ac.s_confd_credentials[0],
                 ac.s_confd_credentials[1], path_to_delete, 'DELETE',
                 ac.g_protocol_api, ac.w_api_port]
    job_id = ac.sender.send('#'.join(arguments))

    app.logger.info('job_id {}'.format(job_id))
    payload = {'info': 'Verification successful', 'job-id': job_id}
    if unavailable_modules:
        payload['skipped'] = unavailable_modules
    return (payload, 202)


@bp.route('/vendors/<path:value>', methods=['DELETE'])
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
    app.logger.info('Deleting vendor on path {}'.format(value))
    username = request.authorization['username']
    app.logger.debug('Checking authorization for user {}'.format(username))
    accessRigths = get_user_access_rights(username, is_vendor=True)

    if accessRigths.startswith('/') and len(accessRigths) > 1:
        accessRigths = accessRigths[1:]
    rights = accessRigths.split('/')
    rights += [None] * (4 - len(rights))

    confd_prefix = '{}://{}:{}'.format(ac.g_protocol_confd, ac.w_confd_ip, ac.w_confd_port)
    path_to_delete = '{}/restconf/data/yang-catalog:catalog/vendors/{}'.format(confd_prefix, value)

    param_names = ['vendor', 'platform', 'software-version', 'software-flavor']
    params = []
    for param_name in param_names:
        if '/{}/'.format(param_name) in path_to_delete:
            params.append(path_to_delete.split('/{}/'.format(param_name))[1].split('/')[0])
        else:
            params.append('None')
        path_to_delete = path_to_delete.replace('/{}/'.format(param_name), '/{}='.format(param_name))

    for param_name, param, right in zip(param_names, params, rights):
        if right and param != right:
            abort(401, description='User not authorized to supply data for this {}'.format(param_name))

    arguments = [*params, ac.g_protocol_confd, ac.w_confd_ip,
                 ac.w_confd_port, ac.s_confd_credentials[0],
                 ac.s_confd_credentials[1], path_to_delete, 'DELETE', ac.g_protocol_api, ac.w_api_port]
    job_id = ac.sender.send('#'.join(arguments))

    app.logger.info('job_id {}'.format(job_id))
    return ({'info': 'Verification successful', 'job-id': job_id}, 202)

def organization_by_namespace(namespace):
    for ns, org in NS_MAP.items():
        if ns in namespace:
                return org
        else:
            if 'urn:' in namespace:
                return namespace.split('urn:')[1].split(':')[0]    
            else:
                return ''

@bp.route('/modules', methods=['PUT', 'POST'])
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
        abort(400, description='bad request - you need to input json body that conforms with'
                               ' module-metadata.yang module. Received no json')
    body = request.json
    modules_cont = body.get('modules')
    if modules_cont is None:
        abort(400, description='bad request - "modules" json object is missing and is mandatory')
    module_list = modules_cont.get('module')
    if module_list is None:
        abort(400, description='bad request - "module" json list is missing and is mandatory')

    app.logger.info('Adding modules with body {}'.format(body))
    tree_created = False

    with open('./prepare-sdo.json', 'w') as plat:
        json.dump(body, plat)
    shutil.copy('./prepare-sdo.json', ac.d_save_requests + '/sdo-'
                + str(datetime.utcnow()).split('.')[0].replace(' ', '_') + '-UTC.json')

    confd_prefix = '{}://{}:{}'.format(ac.g_protocol_confd, ac.w_confd_ip, ac.w_confd_port)
    path = '{}/restconf/data/module-metadata:modules'.format(confd_prefix)

    str_to_encode = '%s:%s' % (ac.s_confd_credentials[0], ac.s_confd_credentials[1])
    if sys.version_info >= (3, 4):
        str_to_encode = str_to_encode.encode(encoding='utf-8', errors='strict')
    base64string = base64.b64encode(str_to_encode)
    if sys.version_info >= (3, 4):
        base64string = base64string.decode(encoding='utf-8', errors='strict')
    response = requests.put(path, json.dumps(body), headers={'Authorization': 'Basic {}'.format(base64string),
                                                             **confd_headers})

    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        abort(400,
              description='The body you have provided could not be parsed. Confd error text: {} \n'
                          ' error code: {} \n error header items: {}'
                          .format(response.text, response.status_code, response.headers.items()))
    repo = {}
    warning = []

    direc = 0
    while os.path.isdir('{}/{}'.format(ac.d_temp, direc)):
        direc += 1
    direc = '{}/{}'.format(ac.d_temp, direc)
    try:
        os.makedirs(direc)
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            raise
    repo_url_dir_branch = {}
    for mod in module_list:
        app.logger.info('{}'.format(mod))
        sdo = mod.get('source-file')
        if sdo is None:
            abort(400, description='bad request - at least one of modules "source-file" is missing and is mandatory')
        orgz = mod.get('organization')
        if orgz is None:
            abort(400, description='bad request - at least one of modules "organization" is missing and is mandatory')
        mod_name = mod.get('name')
        if mod_name is None:
            abort(400, description='bad request - at least one of modules "name" is missing and is mandatory')
        mod_revision = mod.get('revision')
        if mod_revision is None:
            abort(400, description='bad request - at least one of modules "revision" is missing and is mandatory')
        if request.method == 'POST':
            response = get_mod_confd(mod_name, mod_revision, orgz)
            if response.status_code != 404:
                continue
        sdo_path = sdo.get('path')
        if sdo_path is None:
            abort(400, description='bad request - at least one of modules source file "path" is missing and is mandatory')
        sdo_repo = sdo.get('repository')
        if sdo_repo is None:
            abort(400, description='bad request - at least one of modules source file "repository" is missing and is mandatory')
        sdo_owner = sdo.get('owner')
        if sdo_owner is None:
            abort(400, description='bad request - at least one of modules source file "owner" is missing and is mandatory')
        directory = '/'.join(sdo_path.split('/')[:-1])

        repo_url = '{}/{}/{}'.format(github_url, sdo_owner, sdo_repo)
        if repo_url not in repo:
            app.logger.info('Downloading repo {}'.format(repo_url))
            try:
                repo[repo_url] = repoutil.RepoUtil(repo_url)
                repo[repo_url].clone()
            except GitCommandError as e:
                abort(400, description='bad request - cound not clone the github repository. Please check owner,'
                                        ' repository and path of the request - {}'.format(e.stderr))

        try:
            if 'branch' in sdo:
                branch = sdo.get('branch')
            else:
                branch = 'master'
            repo_url_dir_branch_temp = '{}/{}/{}'.format(repo_url, branch, directory)
            if repo_url_dir_branch_temp not in repo_url_dir_branch:
                branch = repo[repo_url].get_commit_hash(directory, branch)
                repo_url_dir_branch[repo_url_dir_branch_temp] = branch
            else:
                branch = repo_url_dir_branch[repo_url_dir_branch_temp]
        except GitCommandError as e:
            abort(400, description='bad request - cound not clone the github repository. Please check owner,'
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
            organization = organization_by_namespace(namespace)
        except:
            while True:
                try:
                    belongs_to = yangParser.parse(os.path.abspath('{}/{}'.format(repo[repo_url].localdir, sdo_path))) \
                        .search('belongs-to')[0].arg
                except:
                    break
                try:
                    namespace = yangParser.parse(
                        os.path.abspath('{}/{}/{}.yang'.format(repo[repo_url].localdir,
                                                               '/'.join(sdo_path.split('/')[:-1]),
                                                               belongs_to))
                        ).search('namespace')[0].arg
                    organization = organization_by_namespace(namespace)
                    break
                except:
                    pass
        resolved_authorization = authorize_for_sdos(request, orgz, organization)
        if not resolved_authorization:
            shutil.rmtree(direc)
            for key in repo:
                repo[key].remove()
            abort(401, description='Unauthorized for server unknown reason')
        if 'organization' in repr(resolved_authorization):
            warning.append('{} {}'.format(sdo['path'].split('/')[-1], resolved_authorization))

    if os.path.isfile('./prepare-sdo.json'):
        shutil.move('./prepare-sdo.json', direc)
    for key in repo:
        repo[key].remove()

    app.logger.debug('Sending a new job')
    populate_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)) + '/../../../parseAndPopulate/populate.py')
    arguments = ['python', populate_path, '--sdo', '--port', ac.w_confd_port, '--dir', direc, '--api',
                 '--ip', ac.w_confd_ip, '--credentials', ac.s_confd_credentials[0], ac.s_confd_credentials[1],
                 repr(tree_created), ac.g_protocol_confd, ac.g_protocol_api, ac.w_api_port]
    job_id = ac.sender.send('#'.join(arguments))
    app.logger.info('job_id {}'.format(job_id))
    if len(warning) > 0:
        return {'info': 'Verification successful', 'job-id': job_id, 'warnings': [{'warning': val} for val in warning]}
    else:
        return ({'info': 'Verification successful', 'job-id': job_id}, 202)


@bp.route('/platforms', methods=['PUT', 'POST'])
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
        abort(400, description='bad request - you need to input json body that conforms with'
                               ' platform-implementation-metadata.yang module. Received no json')
    body = request.json

    platforms_cont = body.get('platforms')
    if platforms_cont is None:
        abort(400, description='bad request - "platforms" json object is missing and is mandatory')
    platform_list = platforms_cont.get('platform')
    if platform_list is None:
        abort(400, description='bad request - "platform" json list is missing and is mandatory')

    app.logger.info('Adding vendor with body {}'.format(body))
    tree_created = False
    authorization = authorize_for_vendors(request, body)
    if authorization is not True:
        abort(401, description='User not authorized to supply data for this {}'.format(authorization))
    path = '{}/vendor-{}-UTC.json'.format(ac.d_save_requests, str(datetime.utcnow()).split('.')[0].replace(' ', '_'))
    with open(path, 'w') as plat:
        json.dump(body, plat)

    path = '{}://{}:{}/restconf/data/platform-implementation-metadata:platforms'.format(ac.g_protocol_confd, ac.w_confd_ip,
                                                                                        ac.w_confd_port)

    str_to_encode = '{}:{}'.format(ac.s_confd_credentials[0], ac.s_confd_credentials[1])
    if sys.version_info >= (3, 4):
        str_to_encode = str_to_encode.encode(encoding='utf-8', errors='strict')
    base64string = base64.b64encode(str_to_encode)
    if sys.version_info >= (3, 4):
        base64string = base64string.decode(encoding='utf-8', errors='strict')
    response = requests.put(path, json.dumps(body), headers={'Authorization': 'Basic {}'.format(base64string),
                                                             **confd_headers})

    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        abort(400,
              description='The body you have provided could not be parsed. Confd error text: {} \n'
                          ' error code: {} \n error header items: {}'
                          .format(response.text, response.status_code, response.headers.items()))

    repo = {}

    direc = 0
    while os.path.isdir('{}/{}'.format(ac.d_temp, direc)):
        direc += 1
    direc = '{}/{}'.format(ac.d_temp, direc)
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
            abort(400, description='bad request - at least on of platform "module-list-file" is missing and is mandatory')
        capability_path = capability.get('path')
        if capability_path is None:
            abort(400, description='bad request - at least on of platform module-list-file "path" for module is missing and is mandatory')
        file_name = capability_path.split('/')[-1]
        repository = capability.get('repository')
        if repository is None:
            abort(400, description='bad request - at least on of platform module-list-file  "repository" for module is missing and is mandatory')
        owner = capability.get('owner')
        if owner is None:
            abort(400, description='bad request - at least on of platform module-list-file  "owner" for module is missing and is mandatory')
        if request.method == 'POST':
            repo_split = repository.split('.')[0]
            repoutil.pull(ac.d_yang_models_dir)
            if os.path.isfile('{}/vendor/{}/{}/{}'.format(ac.d_yang_models_dir, owner, repo_split, capability_path)):
                continue

        directory = '/'.join(capability_path.split('/')[:-1])
        repo_url = '{}/{}/{}'.format(github_url, owner, repository)

        if repo_url not in repo:
            app.logger.info('Downloading repo {}'.format(repo_url))
            try:
                repo[repo_url] = repoutil.RepoUtil(repo_url)
                repo[repo_url].clone()
            except GitCommandError as e:
                abort(400, description='bad request - cound not clone the github repository. Please check owner,'
                                              ' repository and path of the request - {}'.format(e.stderr))
        try:
            if 'branch' in capability:
                branch = capability.get('branch')
            else:
                branch = 'master'
            repo_url_dir_branch_temp = '{}/{}/{}'.format(repo_url, directory, branch)
            if repo_url_dir_branch_temp not in repo_url_dir_branch:
                branch = repo[repo_url].get_commit_hash(directory, branch)
                repo_url_dir_branch[repo_url_dir_branch_temp] = branch
            else:
                branch = repo_url_dir_branch[repo_url_dir_branch_temp]
        except GitCommandError as e:
            abort(400, description='bad request - cound not clone the github repository. Please check owner,'
                                   ' repository and path of the request - {}'.format(e.stderr))
        save_to = '{}/temp/{}/{}/{}/{}'.format(direc, owner, repository.split('.')[0], branch, directory)

        try:
            shutil.copytree('{}/{}'.format(repo[repo_url].localdir, directory), save_to,
                            ignore=shutil.ignore_patterns('*.json', '*.xml', '*.sh', '*.md', '*.txt', '*.bin'))
        except OSError:
            pass
        with open('{}/{}.json'.format(save_to, file_name.split('.')[0]), 'w') as f:
            json.dump(platform, f)
        shutil.copy('{}/{}'.format(repo[repo_url].localdir, capability['path']), save_to)
        tree_created = True

    for key in repo:
        repo[key].remove()
    populate_path = os.path.abspath(
        os.path.dirname('{}/../../../parseAndPopulate/populate.py'.format(os.path.realpath(__file__))))
    arguments = ['python', populate_path, '--port', ac.w_confd_port, '--dir', direc, '--api', '--ip',
                 ac.w_confd_ip, '--credentials', ac.s_confd_credentials[0], ac.s_confd_credentials[1],
                 repr(tree_created), ac.w_public_directory, ac.g_protocol_confd,
                 ac.g_protocol_api, ac.w_api_port]
    job_id = ac.sender.send('#'.join(arguments))
    app.logger.info('job_id {}'.format(job_id))
    return ({'info': 'Verification successful', 'job-id': job_id}, 202)


def authorize_for_vendors(request, body):
    """Authorize sender whether he has rights to send data via API to confd.
       Checks if sender has access on a given branch
                Arguments:
                    :param body: (str) json body of the request.
                    :param request: (request) Request sent to api.
                    :return whether authorization passed.
    """
    username = request.authorization['username']
    app.logger.info('Checking vendor authorization for user {}'.format(username))
    accessRigths = get_user_access_rights(username, is_vendor=True)

    if accessRigths.startswith('/') and len(accessRigths) > 1:
        accessRigths = accessRigths[1:]
    rights = accessRigths.split('/')
    rights += [None] * (4 - len(rights))
    if rights[0] == '':
        return True

    param_names = ['vendor', 'platform', 'software-version', 'software-flavor']
    for platform in body['platforms']['platform']:
        platform['platform'] = platform['name']
        params = [platform[param_name] for param_name in param_names]
        for param_name, param, right in zip(param_names, params, rights):
            if right and param != right:
                return param_name
    return True


def authorize_for_sdos(request, organizations_sent, organization_parsed):
    """Authorize sender whether he has rights to send data via API to confd.
            Arguments:
                :param organization_parsed: (str) organization of a module sent by sender.
                :param organizations_sent: (str) organization of a module parsed from module.
                :param request: (request) Request sent to api.
                :return whether authorization passed.
    """
    username = request.authorization['username']
    app.logger.info('Checking sdo authorization for user {}'.format(username))
    accessRigths = get_user_access_rights(username)

    passed = False
    if accessRigths == '/':
        if organization_parsed != organizations_sent:
            return 'module`s organization is not the same as organization provided'
        return True
    if organizations_sent in accessRigths.split(','):
        if organization_parsed != organizations_sent:
            return 'module`s organization is not in users rights'
        passed = True
    return passed


@bp.route('/job/<job_id>', methods=['GET'])
def get_job(job_id):
    """Search for a job_id to see the process of the job
                :return response to the request with the job
    """
    app.logger.info('Searching for job_id {}'.format(job_id))
    # EVY result = application.sender.get_response(job_id)
    result = ac.sender.get_response(job_id)
    split = result.split('#split#')

    reason = None
    if split[0] == 'Failed' or split[0] == 'Partially done':
        result = split[0]
        if len(split) == 2:
            reason = split[1]
        else:
            reason = ''

    return {'info': {'job-id': job_id,
                     'result': result,
                     'reason': reason}
                    }

### HELPER DEFINITIONS ###


def get_user_access_rights(username: str, is_vendor: bool = False):
    """
    Create MySQL connection and execute query to get information about user by given username.

    Arguments:
        :param username     (str) authorized user's username
        :param is_vendor    (bool) whether method should return vendor or SDO accessRigt
    """
    accessRigths = None
    try:
        result = db.session.query(User).filter_by(Username=username).first()
        if result:
            return result.AccessRightsVendor if is_vendor else result.AccessRightsSdo
    except SQLAlchemyError as err:
        app.logger.error('Cannot connect to database. MySQL error: {}'.format(err))

    return accessRigths

def get_mod_confd(name: str, revision: str, organization: str):
    confd_prefix = '{}://{}:{}'.format(ac.g_protocol_confd, ac.w_confd_ip, ac.w_confd_port)
    url = '{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}'.format(
        confd_prefix, name, revision, organization)
    return requests.get(url, auth=(ac.s_confd_credentials[0], ac.s_confd_credentials[1]), headers=confd_headers)
