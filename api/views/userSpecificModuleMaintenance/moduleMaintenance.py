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

import errno
import json
import os
import shutil
import typing as t
from datetime import datetime

from flask.blueprints import Blueprint
from flask.globals import request
from git import GitCommandError, InvalidGitRepositoryError
from redis import RedisError
from werkzeug.exceptions import abort

from api.authentication.auth import auth
from api.my_flask import app
from utility import repoutil, yangParser
from utility.message_factory import MessageFactory
from utility.staticVariables import NAMESPACE_MAP, backup_date_format, github_url
from utility.util import hash_pw


class UserSpecificModuleMaintenance(Blueprint):
    def __init__(
        self,
        name,
        import_name,
        static_folder=None,
        static_url_path=None,
        template_folder=None,
        url_prefix=None,
        subdomain=None,
        url_defaults=None,
        root_path=None,
    ):
        super().__init__(
            name,
            import_name,
            static_folder,
            static_url_path,
            template_folder,
            url_prefix,
            subdomain,
            url_defaults,
            root_path,
        )


bp = UserSpecificModuleMaintenance('userSpecificModuleMaintenance', __name__)


@bp.before_request
def set_config():
    global ac, users
    ac = app.config
    users = ac.redis_users


@bp.route('/register-user', methods=['POST'])
def register_user():
    body = request.json
    for data in [
        'username',
        'password',
        'password-confirm',
        'email',
        'company',
        'first-name',
        'last-name',
        'motivation',
    ]:
        if data not in body:
            abort(400, description='bad request - missing {} data in input'.format(data))
    username = body['username']

    password = hash_pw(body['password'])
    email = body['email']
    confirm_password = hash_pw(body['password-confirm'])
    models_provider = body['company']
    first_name = body['first-name']
    last_name = body['last-name']
    motivation = body['motivation']
    if password != confirm_password:
        abort(400, 'Passwords do not match')
    try:
        if users.username_exists(username):
            id = users.id_by_username(username)
            if users.is_approved(id):
                abort(409, 'User with username {} already exists'.format(username))
            elif users.is_temp(id):
                abort(409, 'User with username {} is pending for permissions'.format(username))
        users.create(
            temp=True,
            username=username,
            password=password,
            email=email,
            models_provider=models_provider,
            first_name=first_name,
            last_name=last_name,
            motivation=motivation,
        )
    except RedisError as err:
        app.logger.error('Cannot connect to database. Redis error: {}'.format(err))
        return ({'error': 'Server problem connecting to database'}, 500)
    mf = MessageFactory()
    mf.send_new_user(username, email, motivation)
    return ({'info': 'User created successfully'}, 201)


@bp.route('/modules/module/<name>,<revision>,<organization>', methods=['DELETE'])
@bp.route('/modules', methods=['DELETE'])
@auth.login_required
def delete_modules(name: str = '', revision: str = '', organization: str = ''):
    """Delete a specific modules defined with name, revision and organization. This is
    not done right away but it will send another request to receiver which will work on deleting
    while this request will send a "job_id" in the response back to the user.
    User is able to check success of the job using this "job_id".

    :return response with "job_id" that user can use to check whether
            the job is still running or Failed or Finished successfully.
    """
    if all((name, revision, organization)):
        input_modules = [{'name': name, 'revision': revision, 'organization': organization}]
    else:
        rpc = request.json
        if not rpc.get('input'):
            abort(404, description='Data must start with "input" root element in json')
        input_modules = rpc['input'].get('modules', [])

    assert request.authorization, 'No authorization sent'
    username = request.authorization['username']
    app.logger.debug('Checking authorization for user {}'.format(username))
    access_rigths = get_user_access_rights(username)

    unavailable_modules = []
    for mod in input_modules:
        # Check if the module is already in Redis
        read = get_mod_redis(mod)
        if read == {} and access_rigths != '/':
            unavailable_modules.append(mod)
            continue

        if read.get('organization') != access_rigths and access_rigths != '/':
            abort(
                401,
                description='You do not have rights to delete modules with organization {}'.format(
                    read.get('organization'),
                ),
            )

        if read.get('implementations') is not None:
            unavailable_modules.append(mod)

    # Filter out unavailble modules
    input_modules = [x for x in input_modules if x not in unavailable_modules]
    modules_dict = json.dumps({'modules': input_modules})

    arguments = ['DELETE-MODULES', ac.s_confd_credentials[0], ac.s_confd_credentials[1], modules_dict]
    job_id = ac.sender.send('#'.join(arguments))

    app.logger.info('Running deletion of modules with job_id {}'.format(job_id))
    payload = {'info': 'Verification successful', 'job-id': job_id}
    if unavailable_modules:
        payload['skipped'] = unavailable_modules
    return (payload, 202)


@bp.route('/vendors/<path:value>', methods=['DELETE'])
@auth.login_required
def delete_vendor(value: str):
    """Delete a specific vendor defined with path. This is
    not done right away but it will send another request to receiver which will work on deleting
    while this request will send a "job_id" in the response back to the user.
    User is able to check success of the job using this "job_id".

    Argument:
        :param value    (str) path to the branch that needs to be deleted

    :return response with "job_id" that user can use to check whether
            the job is still running or Failed or Finished successfully.
    """
    assert request.authorization, 'No authorization sent'
    username = request.authorization['username']
    app.logger.debug('Checking authorization for user {}'.format(username))
    access_rigths = get_user_access_rights(username, is_vendor=True)
    assert access_rigths is not None, "Couldn't get access rights of user {}".format(username)

    if access_rigths.startswith('/') and len(access_rigths) > 1:
        access_rigths = access_rigths[1:]
    rights = access_rigths.split('/')
    rights += [None] * (4 - len(rights))

    path = '/vendors/{}'.format(value)

    param_names = ['vendor', 'platform', 'software-version', 'software-flavor']
    params = []
    for param_name in param_names[::-1]:
        path, _, param = path.partition('/{}s/{}/'.format(param_name, param_name))
        params.append(param or 'None')
    params = params[::-1]

    for param_name, param, right in zip(param_names, params, rights):
        if right and param != right:
            abort(401, description='User not authorized to supply data for this {}'.format(param_name))

    arguments = ['DELETE-VENDORS', ac.s_confd_credentials[0], ac.s_confd_credentials[1], *params]
    job_id = ac.sender.send('#'.join(arguments))

    app.logger.info('Running deletion of vendors metadata with job_id {}'.format(job_id))
    payload = {'info': 'Verification successful', 'job-id': job_id}
    return (payload, 202)


@bp.route('/modules', methods=['PUT', 'POST'])
@auth.login_required
def add_modules():
    """Endpoint is used to add new modules using the API.
    PUT request is used for updating each module in request body.
    POST request is used for creating new modules that are not in ConfD/Redis yet.
    First it checks if the sent request is ok and if so, it will send a another request
    to the receiver which will work on adding/updating modules while this request
    will send a "job_id" in the response back to the user.
    User is able to check success of the job using this "job_id"
    the job process.

    :return response with "job_id" that user can use to check whether
            the job is still running or Failed or Finished successfully.
    """
    body = request.json
    modules_cont = body.get('modules')
    if modules_cont is None:
        abort(400, description='bad request - "modules" json object is missing and is mandatory')
    module_list = modules_cont.get('module')
    if module_list is None:
        abort(400, description='bad request - "module" json list is missing and is mandatory')

    dst_path = os.path.join(ac.d_save_requests, 'sdo-{}.json'.format(datetime.utcnow().strftime(backup_date_format)))
    if not os.path.exists(ac.d_save_requests):
        os.mkdir(ac.d_save_requests)
    with open(dst_path, 'w') as f:
        json.dump(body, f)

    response = app.confdService.put_module_metadata(json.dumps(body))

    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        abort(
            400,
            description='The body you have provided could not be parsed. ConfD error text:\n{}\n'
            'Error code: {}'.format(response.text, response.status_code),
        )
    direc_num = 0
    while os.path.isdir(os.path.join(ac.d_temp, str(direc_num))):
        direc_num += 1
    direc = os.path.join(ac.d_temp, str(direc_num))
    try:
        os.makedirs(direc)
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            raise
    repos: t.Dict[str, repoutil.RepoUtil] = {}
    warning = []
    missing_msg = 'bad request - at least one module object is missing mandatory field {}'
    for module in module_list:
        app.logger.debug(module)
        source_file: dict = module.get('source-file')
        if source_file is None:
            abort(400, description=missing_msg.format('source-file'))
        organization_sent = module.get('organization')
        if organization_sent is None:
            abort(400, description=missing_msg.format('organization'))
        name = module.get('name')
        if name is None:
            abort(400, description=missing_msg.format('name'))
        revision = module.get('revision')
        if revision is None:
            abort(400, description=missing_msg.format('revision'))
        if request.method == 'POST':
            # Check if the module is already in Redis
            redis_module = get_mod_redis(module)
            if redis_module != {}:
                continue
        module_path = source_file.get('path')
        if module_path is None:
            abort(400, description=missing_msg.format('source-file["path"]'))
        repo_name = source_file.get('repository')
        if repo_name is None:
            abort(400, description=missing_msg.format('source-file["repository"]'))
        owner = source_file.get('owner')
        if owner is None:
            abort(400, description=missing_msg.format('source-file["owner"]'))

        dir_in_repo = os.path.dirname(module_path)
        repo_url = os.path.join(github_url, owner, repo_name)
        if repo_url not in repos:
            repos[repo_url] = get_repo(repo_url, owner, repo_name)

        save_to = os.path.join(direc, owner, repo_name.split('.')[0], dir_in_repo)
        try:
            os.makedirs(save_to)
        except OSError as e:
            # be happy if someone already created the path
            if e.errno != errno.EEXIST:
                raise
        try:
            shutil.copy(os.path.join(repos[repo_url].local_dir, module_path), save_to)
        except FileNotFoundError:
            app.logger.exception('Problem with file {}'.format(module_path))
            warning.append(
                '{} does not exist'.format(
                    os.path.join(repo_url, 'blob', source_file.get('branch', 'HEAD'), module_path),
                ),
            )
            continue

        organization_parsed = ''
        try:
            path_to_parse = os.path.abspath(os.path.join(save_to, os.path.basename(module_path)))
            namespace = yangParser.parse(path_to_parse).search('namespace')[0].arg
            organization_parsed = organization_by_namespace(namespace)
        except (yangParser.ParseException, FileNotFoundError, IndexError, AttributeError):
            try:
                path_to_parse = os.path.abspath(os.path.join(repos[repo_url].local_dir, module_path))
                belongs_to = yangParser.parse(path_to_parse).search('belongs-to')[0].arg
            except (yangParser.ParseException, FileNotFoundError, IndexError, AttributeError):
                pass
            else:
                namespace = (
                    yangParser.parse(
                        os.path.abspath(
                            '{}/{}/{}.yang'.format(repos[repo_url].local_dir, os.path.dirname(module_path), belongs_to),
                        ),
                    )
                    .search('namespace')[0]
                    .arg
                )
                organization_parsed = organization_by_namespace(namespace)
        resolved_authorization = authorize_for_sdos(request, organization_sent, organization_parsed)
        if not resolved_authorization:
            shutil.rmtree(direc)
            abort(401, description='Unauthorized for server unknown reason')
        if 'organization' in repr(resolved_authorization):
            warning.append('{} {}'.format(os.path.basename(module_path), resolved_authorization))

    with open(os.path.join(direc, 'request-data.json'), 'w') as f:
        json.dump(body, f)

    arguments = [
        'POPULATE-MODULES',
        '--sdo',
        '--dir',
        direc,
        '--api',
        '--credentials',
        ac.s_confd_credentials[0],
        ac.s_confd_credentials[1],
    ]
    job_id = ac.sender.send('#'.join(arguments))
    app.logger.info('Running populate.py with job_id {}'.format(job_id))
    if len(warning) > 0:
        return {'info': 'Verification successful', 'job-id': job_id, 'warnings': [{'warning': val} for val in warning]}
    else:
        return {'info': 'Verification successful', 'job-id': job_id}, 202


@bp.route('/platforms', methods=['PUT', 'POST'])
@auth.login_required
def add_vendors():
    """Endpoint is used to add new vendors using the API.
    PUT request is used for updating each vendor in request body.
    POST request is used for creating new vendors that are not in ConfD/Redis yet.
    First it checks if the sent request is ok and if so, it will send another request
    to the receiver which will work on adding/updating vendors while this request
    will send a "job_id" in the response back to the user.
    User is able to check the success of the job using this "job_id".

    :return response with "job_id" that the user can use to check whether
            the job is still running or Failed or Finished successfully.
    """
    body = request.json
    platforms_contents = body.get('platforms')
    if platforms_contents is None:
        abort(400, description='bad request - "platforms" json object is missing and is mandatory')
    platform_list = platforms_contents.get('platform')
    if platform_list is None:
        abort(400, description='bad request - "platform" json list is missing and is mandatory')

    app.logger.info('Adding vendor with body\n{}'.format(json.dumps(body, indent=2)))
    tree_created = False
    authorization = authorize_for_vendors(request, body)
    if authorization is not True:
        abort(401, description='User not authorized to supply data for this {}'.format(authorization))

    dst_path = os.path.join(ac.d_save_requests, 'vendor-{}.json'.format(datetime.utcnow().strftime(backup_date_format)))
    if not os.path.exists(ac.d_save_requests):
        os.mkdir(ac.d_save_requests)
    with open(dst_path, 'w') as f:
        json.dump(body, f)

    response = app.confdService.put_platform_metadata(json.dumps(body))

    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        abort(
            400,
            description='The body you have provided could not be parsed. ConfD error text:\n{}\n'
            'Error code: {}'.format(response.text, response.status_code),
        )

    direc_num = 0
    while os.path.isdir(os.path.join(ac.d_temp, str(direc_num))):
        direc_num += 1
    direc = os.path.join(ac.d_temp, str(direc_num))
    try:
        os.makedirs(direc)
    except OSError as e:
        # be happy if someone already created the path
        if e.errno != errno.EEXIST:
            raise

    repos: t.Dict[str, repoutil.RepoUtil] = {}
    missing_msg = 'bad request - at least one platform object is missing mandatory field {}'
    for platform in platform_list:
        module_list_file = platform.get('module-list-file')
        if module_list_file is None:
            abort(400, description=missing_msg.format('module-list-file'))
        xml_path = module_list_file.get('path')
        if xml_path is None:
            abort(400, description=missing_msg.format('module-list-file["path"]'))
        file_name = os.path.basename(xml_path)
        repo_name = module_list_file.get('repository')
        if repo_name is None:
            abort(400, description=missing_msg.format('module-list-file["repository"]'))
        owner = module_list_file.get('owner')
        if owner is None:
            abort(400, description=missing_msg.format('module-list-file["owner"]'))
        if request.method == 'POST':
            repoutil.pull(ac.d_yang_models_dir)
            if os.path.isfile(os.path.join(ac.d_yang_models_dir, xml_path)):
                continue

        dir_in_repo = os.path.dirname(xml_path)
        repo_url = os.path.join(github_url, owner, repo_name)

        if repo_url not in repos:
            repos[repo_url] = get_repo(repo_url, owner, repo_name)

        save_to = os.path.join(direc, owner, repo_name.split('.')[0], dir_in_repo)

        try:
            shutil.copytree(
                os.path.join(repos[repo_url].local_dir, dir_in_repo),
                save_to,
                ignore=shutil.ignore_patterns('*.json', '*.xml', '*.sh', '*.md', '*.txt', '*.bin'),
            )
        except OSError:
            pass
        with open('{}/{}.json'.format(save_to, file_name.split('.')[0]), 'w') as f:
            json.dump(platform, f)
        shutil.copy(os.path.join(repos[repo_url].local_dir, module_list_file['path']), save_to)
        tree_created = True

    arguments = [
        'POPULATE-VENDORS',
        '--dir',
        direc,
        '--api',
        '--credentials',
        ac.s_confd_credentials[0],
        ac.s_confd_credentials[1],
        repr(tree_created),
    ]
    job_id = ac.sender.send('#'.join(arguments))
    app.logger.info('Running populate.py with job_id {}'.format(job_id))
    return {'info': 'Verification successful', 'job-id': job_id}, 202


@bp.route('/job/<job_id>', methods=['GET'])
def get_job(job_id: str):
    """Search for a "job_id" to see the process of the job.

    :return response to the request with the job
    """
    app.logger.info('Searching for job_id {}'.format(job_id))
    result = ac.sender.get_response(job_id)
    split = result.split('#split#')

    reason = None
    if split[0] == 'Failed' or split[0] == 'In progress':
        result = split[0]
        if len(split) == 2:
            reason = split[1]
        else:
            reason = ''

    return {'info': {'job-id': job_id, 'result': result, 'reason': reason}}


def authorize_for_vendors(request, body: dict):
    """Authorize the sender whether he has the rights to send data via API to Redis.

    Arguments:
        :param body     (dict) body of the send request
        :param request  (request) Request sent to api.

        :return     whether authorization passed or not
    """
    username = request.authorization['username']
    app.logger.info('Checking vendor authorization for user {}'.format(username))
    access_rigths = get_user_access_rights(username, is_vendor=True)
    assert access_rigths is not None, "Couldn't get access rights of user {}".format(username)

    if access_rigths.startswith('/') and len(access_rigths) > 1:
        access_rigths = access_rigths[1:]
    rights = access_rigths.split('/')
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


def authorize_for_sdos(request, organizations_sent: str, organization_parsed: str):
    """Authorize the sender whether he has the rights to send data via API to Redis.

    Arguments:
        :param request              (request) Request sent to API
        :param organizations_sent   (str) organization of a module parsed from module
        :param organization_parsed  (str) organization of a module sent by sender

        :return     whether authorization passed or not
    """
    username = request.authorization['username']
    app.logger.info('Checking sdo authorization for user {}'.format(username))
    access_rigths = get_user_access_rights(username)
    assert access_rigths is not None, "Couldn't get access rights of user {}".format(username)

    passed = False
    if access_rigths == '/':
        if organization_parsed != organizations_sent:
            return 'module`s organization is not the same as organization provided'
        return True
    if organizations_sent in access_rigths.split(','):
        if organization_parsed != organizations_sent:
            return 'module`s organization is not in users rights'
        passed = True
    return passed


def get_user_access_rights(username: str, is_vendor: bool = False):
    """
    Query Redis for information about the user by given username.

    Arguments:
        :param username     (str) authorized user's username
        :param is_vendor    (bool) whether method should return vendor or SDO accessRigt
    """
    try:
        if users.username_exists(username):
            id = users.id_by_username(username)
            return users.get_field(id, 'access-rights-vendor' if is_vendor else 'access-rights-sdo')
    except RedisError as err:
        app.logger.error('Cannot connect to database. Redis error: {}'.format(err))
    return None


def get_mod_redis(module: dict):
    redis_key = '{}@{}/{}'.format(module.get('name'), module.get('revision'), module.get('organization'))
    redis_module = app.redisConnection.get_module(redis_key)
    return json.loads(redis_module)


def organization_by_namespace(namespace: str):
    for ns, org in NAMESPACE_MAP:
        if ns in namespace:
            return org
        else:
            if 'urn:' in namespace:
                return namespace.split('urn:')[1].split(':')[0]
    return ''


def get_repo(repo_url: str, owner: str, repo_name: str) -> repoutil.RepoUtil:
    if owner == 'YangModels' and repo_name == 'yang':
        app.logger.info('Using repo already downloaded from {}'.format(repo_url))
        repoutil.pull(ac.d_yang_models_dir)
        try:
            yang_models_repo = repoutil.load(ac.d_yang_models_dir, github_url)
        except InvalidGitRepositoryError:
            raise Exception("Couldn't load YangModels/yang from directory")
        return yang_models_repo
    else:
        app.logger.info('Downloading repo {}'.format(repo_url))
        try:
            repo = repoutil.ModifiableRepoUtil(repo_url)
            return repo
        except GitCommandError as e:
            abort(
                400,
                description='bad request - could not clone the Github repository. Please check owner,'
                ' repository and path of the request - {}'.format(e.stderr),
            )
