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

# We always check result.is_json, so result.json will never return None.
# pyright: reportOptionalSubscript=false

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'

import json
import os
import shutil
import unittest
from copy import deepcopy
from unittest import mock

from celery import states
from redis import RedisError

import api.views.user_specific_module_maintenance as mm
from api.globalConfig import yc_gc
from api.yangcatalog_api import app
from jobs.status_messages import StatusMessage
from redisConnections.redis_users_connection import RedisUsersConnection
from utility.util import hash_pw

import_string = 'api.views.user_specific_module_maintenance'


class MockRepoUtil:
    local_dir = 'test'

    def __init__(self, repourl, logger=None):
        pass

    def get_commit_hash(self, path=None, branch='master'):
        return branch

    @classmethod
    def clone(cls, *args, **kwargs):
        return MockRepoUtil(None)

    @classmethod
    def load(cls, *args, **kwargs):
        return MockRepoUtil(None)


class MockRedisUsers:
    def __init__(self):
        self.create = mock.MagicMock(return_value=1)
        self.is_approved = mock.MagicMock(return_value=False)
        self.is_temp = mock.MagicMock(return_value=True)
        self.username_exists = mock.MagicMock(return_value=False)
        self.id_by_username = mock.MagicMock(return_value=1)


class TestApiContributeClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        cls.client = app.test_client()
        cls.users = RedisUsersConnection()

        with open(os.path.join(resources_path, 'payloads.json'), 'r') as f:
            cls.payloads_content = json.load(f)

        cls.process_task_patcher = mock.patch(f'{import_string}.process.s')
        cls.process = cls.process_task_patcher.start()
        cls.addClassCleanup(cls.process_task_patcher.stop)
        cls.process.return_value.apply_async.return_value = mock.MagicMock(id=1)

        cls.process_module_deletion_task_patcher = mock.patch(f'{import_string}.process_module_deletion.s')
        cls.process_module_deletion = cls.process_module_deletion_task_patcher.start()
        cls.addClassCleanup(cls.process_module_deletion_task_patcher.stop)
        cls.process_module_deletion.return_value.apply_async.return_value = mock.MagicMock(id=1)

        cls.process_vendor_deletion_task_patcher = mock.patch(f'{import_string}.process_vendor_deletion.s')
        cls.process_vendor_deletion = cls.process_vendor_deletion_task_patcher.start()
        cls.addClassCleanup(cls.process_vendor_deletion_task_patcher.stop)
        cls.process_vendor_deletion.return_value.apply_async.return_value = mock.MagicMock(id=1)

        cls.confd_patcher = mock.patch(f'{import_string}.get_mod_redis')
        cls.mock_redis_get = cls.confd_patcher.start()
        cls.addClassCleanup(cls.confd_patcher.stop)
        cls.mock_redis_get.side_effect = mock_redis_get

        cls.get_patcher = mock.patch('requests.get')
        cls.mock_get = cls.get_patcher.start()
        cls.addClassCleanup(cls.get_patcher.stop)
        cls.mock_get.return_value.json.return_value = json.loads(yc_gc.redis.get('modules-data') or '{}')

        cls.message_factory_patcher = mock.patch(f'{import_string}.MessageFactory')
        cls.mock_message_factory = cls.message_factory_patcher.start()
        cls.addClassCleanup(cls.message_factory_patcher.stop)

    def setUp(self):
        self.uid = self.users.create(
            temp=False,
            username='test',
            password=hash_pw('test'),
            email='test@test.test',
            models_provider='test',
            first_name='test',
            last_name='test',
            access_rights_sdo='/',
            access_rights_vendor='/',
        )
        self.user_registration_data = {
            k: 'test'
            for k in [
                'username',
                'password',
                'password-confirm',
                'email',
                'company',
                'first-name',
                'last-name',
                'motivation',
            ]
        }
        os.makedirs(yc_gc.save_requests, exist_ok=True)
        self.payloads_content = deepcopy(self.payloads_content)

    def tearDown(self):
        self.users.delete(self.uid, temp=False)
        shutil.rmtree(yc_gc.save_requests)

    def assertJsonResponse(self, response, status_code: int, field: str, value, contains: bool = False):  # noqa: N802
        self.assertEqual(response.status_code, status_code)
        self.assertTrue(response.is_json)
        data = response.json
        self.assertIn(field, data)
        if contains:
            self.assertIn(value, data[field])
        else:
            self.assertEqual(data[field], value)

    def assertJobSuccess(self, response):  # noqa: N802
        self.assertTrue(200 <= response.status_code < 300)
        self.assertJsonResponse(response, response.status_code, 'info', 'Verification successful')
        self.assertJsonResponse(response, response.status_code, 'job-id', 1)

    @mock.patch('api.yangcatalog_api.app.config.redis_users', MockRedisUsers())
    def test_register_user(self):
        # we use a username different from "test" because such a user already exists
        body = {
            k: 'tset'
            for k in [
                'username',
                'password',
                'password-confirm',
                'email',
                'company',
                'first-name',
                'last-name',
                'motivation',
            ]
        }
        result = self.client.post('api/register-user', json=body)

        self.assertJsonResponse(result, 201, 'info', 'User created successfully')

    def test_register_user_mismatched_passwd(self):
        body = self.user_registration_data
        body['password-confirm'] = 'different'
        result = self.client.post('api/register-user', json=body)

        self.assertJsonResponse(result, 400, 'description', 'Passwords do not match')

    def test_register_user_user_exist(self):
        body = self.user_registration_data
        result = self.client.post('api/register-user', json=body)

        self.assertJsonResponse(result, 409, 'description', 'User with username test already exists')

    @mock.patch('api.yangcatalog_api.app.config.redis_users', new_callable=MockRedisUsers)
    def test_register_user_tempuser_exist(self, mock_redis_users: MockRedisUsers):
        mock_redis_users.is_approved.return_value = False
        mock_redis_users.is_temp.return_value = True
        mock_redis_users.username_exists.return_value = True
        body = self.user_registration_data
        result = self.client.post('api/register-user', json=body)

        self.assertJsonResponse(result, 409, 'description', 'User with username test is pending for permissions')

    @mock.patch('api.yangcatalog_api.app.config.redis_users', new_callable=MockRedisUsers)
    def test_register_user_db_exception(self, mock_redis_users: MockRedisUsers):
        mock_redis_users.username_exists.side_effect = RedisError
        body = self.user_registration_data
        result = self.client.post('api/register-user', json=body)

        self.assertJsonResponse(result, 500, 'error', 'Server problem connecting to database')

    def test_delete_modules_one_module(self):
        """Test correct action is taken for a valid deletion attempt."""
        name = 'yang-catalog'
        revision = '2018-04-03'
        organization = 'ietf'
        path = f'{name},{revision},{organization}'
        result = self.client.delete(f'api/modules/module/{path}', auth=('test', 'test'))

        self.assertJobSuccess(result)

    @mock.patch(f'{import_string}.get_user_access_rights')
    def test_delete_modules_unavailable_module(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = ''
        mod = {'name': 'test', 'revision': '2017-01-01', 'organization': 'ietf'}
        path = f'{mod["name"]},{mod["revision"]},{mod["organization"]}'
        result = self.client.delete(f'api/modules/module/{path}', auth=('test', 'test'))

        self.assertJobSuccess(result)

    @mock.patch(f'{import_string}.get_user_access_rights')
    def test_delete_modules_insufficient_rights(self, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give no rights.
        Test error response when the user has insufficient rights.
        """
        mock_access_rights.return_value = ''
        mod = {'name': 'yang-catalog', 'revision': '2017-09-26', 'organization': 'ietf'}
        path = f'{mod["name"]},{mod["revision"]},{mod["organization"]}'
        result = self.client.delete(f'api/modules/module/{path}', auth=('test', 'test'))

        self.assertJsonResponse(
            result,
            401,
            'description',
            f'You do not have rights to delete modules with organization {mod["organization"]}',
        )

    def test_delete_modules_has_implementation(self):
        """Test skipped modules when the module has implementations."""
        mod = {'name': 'ietf-yang-types', 'revision': '2013-07-15', 'organization': 'ietf'}
        path = f'{mod["name"]},{mod["revision"]},{mod["organization"]}'
        result = self.client.delete(f'api/modules/module/{path}', auth=('test', 'test'))

        self.assertJsonResponse(result, 202, 'skipped', [mod])

    def test_delete_modules(self):
        body = self.payloads_content.get('delete_modules')

        result = self.client.delete('api/modules', json=body, auth=('test', 'test'))

        self.assertJobSuccess(result)

    def test_delete_vendor(self):
        """Test correct action is taken for a valid deletion attempt."""
        path = 'nonexistent'
        result = self.client.delete(f'api/vendors/{path}', auth=('test', 'test'))

        self.assertJobSuccess(result)

    @mock.patch(f'{import_string}.get_user_access_rights')
    def test_delete_vendor_insufficient_rights(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = '/cisco'
        vendor_name = 'fujitsu'
        path = f'vendor/{vendor_name}'
        result = self.client.delete(f'api/vendors/{path}', auth=('test', 'test'))

        self.assertJsonResponse(result, 401, 'description', 'User not authorized to supply data for this vendor')

    def test_organization_by_namespace(self):
        self.assertEqual(mm.organization_by_namespace('http://cisco.com/test'), 'cisco')
        self.assertEqual(mm.organization_by_namespace('urn:test:test'), 'test')
        self.assertEqual(mm.organization_by_namespace('test'), '')

    @mock.patch(f'{import_string}.shutil', mock.MagicMock())
    @mock.patch('utility.repoutil.RepoUtil', mock.MagicMock)
    @mock.patch('requests.put')
    def test_add_modules(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertJobSuccess(result)

    @mock.patch(f'{import_string}.shutil', mock.MagicMock())
    @mock.patch('utility.repoutil.RepoUtil', mock.MagicMock)
    @mock.patch('requests.put')
    def test_add_modules_post(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        result = self.client.post('api/modules', json=body, auth=('test', 'test'))

        self.assertJobSuccess(result)

    @mock.patch(f'{import_string}.shutil', mock.MagicMock())
    @mock.patch('utility.repoutil.RepoUtil', mock.MagicMock)
    @mock.patch('requests.put')
    def test_add_modules_unparsable(self, mock_put: mock.MagicMock):
        mock_put.return_value.status_code = 400
        mock_put.return_value.text = 'test'
        body = self.payloads_content.get('add_modules')
        body['modules']['module'] = []

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertJsonResponse(
            result,
            400,
            'description',
            'The body you have provided could not be parsed. ConfD error text:\ntest\nError code: 400',
        )

    @mock.patch(f'{import_string}.shutil', mock.MagicMock())
    @mock.patch('utility.repoutil.RepoUtil', mock.MagicMock)
    @mock.patch('requests.put')
    def test_add_modules_invalid_repo(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        body['modules']['module'][0]['source-file']['owner'] = 'foobar'
        mock_put.return_value.status_code = 200

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertJsonResponse(
            result,
            400,
            'description',
            'bad request - could not clone the Github repository.'
            ' Please check owner, repository and path of the request - ',
            contains=True,
        )

    @mock.patch(f'{import_string}.shutil', mock.MagicMock())
    @mock.patch('utility.repoutil.RepoUtil', mock.MagicMock)
    @mock.patch(f'{import_string}.authorize_for_sdos')
    @mock.patch('requests.put')
    def test_add_modules_unauthorized(self, mock_put: mock.MagicMock, mock_access_rights: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        mock_put.return_value.status_code = 200
        mock_access_rights.return_value = ''

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertJsonResponse(result, 401, 'description', 'Unauthorized for server unknown reason')

    @mock.patch(f'{import_string}.shutil', mock.MagicMock())
    @mock.patch(f'{import_string}.RepoUtil', MockRepoUtil)
    @mock.patch(f'{import_string}.open', mock.mock_open())
    @mock.patch('requests.put')
    @mock.patch(f'{import_string}.authorize_for_vendors')
    def test_add_vendor(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        body = self.payloads_content.get('add_vendor')
        result = self.client.put('api/platforms', json=body, auth=('test', 'test'))

        self.assertJobSuccess(result)

    @mock.patch(f'{import_string}.shutil', mock.MagicMock())
    @mock.patch(f'{import_string}.RepoUtil', MockRepoUtil)
    @mock.patch(f'{import_string}.open', mock.mock_open())
    @mock.patch(f'{import_string}.repoutil.pull')
    @mock.patch('requests.put')
    @mock.patch(f'{import_string}.authorize_for_vendors')
    def test_add_vendor_post(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock, mock_pull: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        body = self.payloads_content.get('add_vendor')
        result = self.client.post('api/platforms', json=body, auth=('test', 'test'))

        mock_pull.assert_called()
        self.assertJobSuccess(result)

    @mock.patch(f'{import_string}.shutil', mock.MagicMock())
    @mock.patch('requests.put')
    @mock.patch(f'{import_string}.authorize_for_vendors')
    def test_add_vendor_confd_error(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 400
        mock_put.return_value.text = 'test'
        result = self.client.put('api/platforms', json={'platforms': {'platform': []}}, auth=('test', 'test'))

        self.assertJsonResponse(
            result,
            400,
            'description',
            'The body you have provided could not be parsed. ConfD error text:\ntest\nError code: 400',
        )

    @mock.patch(f'{import_string}.shutil', mock.MagicMock())
    @mock.patch(f'{import_string}.repoutil.RepoUtil', MockRepoUtil)
    @mock.patch(f'{import_string}.open', mock.mock_open())
    @mock.patch('requests.put')
    @mock.patch(f'{import_string}.authorize_for_vendors')
    def test_add_vendor_git_error(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        body = self.payloads_content.get('add_vendor')
        result = self.client.put('api/platforms', json=body, auth=('test', 'test'))

        self.assertJsonResponse(
            result,
            400,
            'description',
            'bad request - could not clone the Github repository.'
            ' Please check owner, repository and path of the request - ',
            contains=True,
        )

    @mock.patch(f'{import_string}.get_user_access_rights')
    def test_authorize_for_vendors(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = '/test/test/test/test'
        request = mock.MagicMock()
        request.authorization = {'username': 'test'}
        body = {
            'platforms': {
                'platform': [{'name': 'test', 'vendor': 'test', 'software-version': 'test', 'software-flavor': 'test'}],
            },
        }
        with app.app_context():
            result = mm.authorize_for_vendors(request, body)

        self.assertEqual(result, True)

    @mock.patch(f'{import_string}.get_user_access_rights')
    def test_authorize_for_vendors_root(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = '/'
        request = mock.MagicMock()
        request.authorization = {'username': 'test'}
        with app.app_context():
            result = mm.authorize_for_vendors(request, {})

        self.assertEqual(result, True)

    @mock.patch(f'{import_string}.get_user_access_rights')
    def test_authorize_for_vendors_missing_rights(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = 'test'
        request = mock.MagicMock()
        request.authorization = {'username': 'test'}
        body = {
            'platforms': {
                'platform': [
                    {'name': 'other', 'vendor': 'other', 'software-version': 'other', 'software-flavor': 'other'},
                ],
            },
        }
        with app.app_context():
            result = mm.authorize_for_vendors(request, body)

        self.assertEqual(result, 'vendor')

    @mock.patch(f'{import_string}.get_user_access_rights')
    def test_authorize_for_sdos(self, mock_access_rights: mock.MagicMock):
        request = mock.MagicMock()
        request.authorization = {'username': 'test'}
        with app.app_context():
            mock_access_rights.return_value = '/'
            self.assertTrue(mm.authorize_for_sdos(request, 'test', 'test'), 'root access rights')
            mock_access_rights.return_value = 'test'
            self.assertTrue(mm.authorize_for_sdos(request, 'test', 'test'), 'matching access rights')
            self.assertEqual(
                mm.authorize_for_sdos(request, 'test', 'other'),
                'module`s organization is not the same as organization provided',
                'mismatches reported and parsed organization',
            )
            mock_access_rights.return_value = 'other'
            self.assertEqual(mm.authorize_for_sdos(request, 'test', 'test'), False, 'incorrect access rights')

    def test_get_job(self):
        job_id = 'invalid-id'
        celery_app_mock = mock.MagicMock()
        celery_app_mock.AsyncResult.return_value.ready.return_value = True
        celery_app_mock.AsyncResult.return_value.status = states.SUCCESS
        celery_app_mock.AsyncResult.return_value.get.return_value = StatusMessage.SUCCESS.value
        with mock.patch('api.yangcatalog_api.app.config.celery_app', celery_app_mock):
            result = self.client.get(f'api/job/{job_id}')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertIn('job-id', data['info'])
        self.assertEqual(data['info']['job-id'], 'invalid-id')
        self.assertIn('result', data['info'])
        self.assertEqual(data['info']['result'], StatusMessage.SUCCESS.value)


def mock_redis_get(module: dict):
    file = f'{os.environ["BACKEND"]}/tests/resources/confd_responses/{module["name"]}@{module["revision"]}.json'
    if not os.path.isfile(file):
        return json.loads('{}')
    else:
        with open(file) as f:
            data = json.load(f)
            return data.get('yang-catalog:module')[0]


if __name__ == '__main__':
    unittest.main()
