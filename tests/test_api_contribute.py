# Copyright The IETF Trust 2021, All Rights Reserved
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

from redis import RedisError

import api.views.userSpecificModuleMaintenance.moduleMaintenance as mm
from api.globalConfig import yc_gc
from api.yangCatalogApi import app
from redisConnections.redis_users_connection import RedisUsersConnection
from utility.util import hash_pw


class MockRepoUtil:
    local_dir = 'test'

    def __init__(self, repourl, logger=None):
        pass

    def get_commit_hash(self, path=None, branch='master'):
        return branch


class TestApiContributeClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        cls.client = app.test_client()
        # TODO: Mock RedisUsersConnection to run on db=12 when running tests
        cls.users = RedisUsersConnection()

        with open(os.path.join(resources_path, 'payloads.json'), 'r') as f:
            cls.payloads_content = json.load(f)

        cls.send_patcher = mock.patch('api.yangCatalogApi.app.config.sender.send')
        cls.mock_send = cls.send_patcher.start()
        cls.addClassCleanup(cls.send_patcher.stop)
        cls.mock_send.return_value = 1

        cls.confd_patcher = mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_mod_redis')
        cls.mock_redis_get = cls.confd_patcher.start()
        cls.addClassCleanup(cls.confd_patcher.stop)
        cls.mock_redis_get.side_effect = mock_redis_get

        cls.get_patcher = mock.patch('requests.get')
        cls.mock_get = cls.get_patcher.start()
        cls.addClassCleanup(cls.get_patcher.stop)
        cls.mock_get.return_value.json.return_value = json.loads(yc_gc.redis.get('modules-data') or '{}')

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
        os.makedirs(yc_gc.save_requests, exist_ok=True)
        self.payloads_content = deepcopy(self.payloads_content)

    def tearDown(self):
        self.users.delete(self.uid, temp=False)
        shutil.rmtree(yc_gc.save_requests)

    @mock.patch('api.yangCatalogApi.app.config.redis_users.create', mock.MagicMock())
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.MessageFactory', mock.MagicMock)
    def test_register_user(self):
        # we use a username different from "test" because such a user already exists
        body = {
            'username': 'tset',
            'password': 'tset',
            'password-confirm': 'tset',
            'email': 'tset',
            'company': 'tset',
            'first-name': 'tset',
            'last-name': 'tset',
            'motivation': 'tset',
        }
        result = self.client.post('api/register-user', json=body)

        self.assertEqual(result.status_code, 201)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'User created successfully')

    def test_register_user_no_data(self):
        result = self.client.post('api/register-user')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(
            data['description'],
            'The browser (or proxy) sent a request that this server could not understand.',
        )

    def test_register_user_missing_field(self):
        body = {k: 'test' for k in ['username', 'password', 'password-confirm', 'email', 'company', 'first-name']}
        result = self.client.post('api/register-user', json=body)

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - missing last-name data in input')

    def test_register_user_mismatched_passwd(self):
        body = {
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
        body['password-confirm'] = 'different'
        result = self.client.post('api/register-user', json=body)

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Passwords do not match')

    def test_register_user_user_exist(self):
        body = {
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
        result = self.client.post('api/register-user', json=body)

        self.assertEqual(result.status_code, 409)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'User with username test already exists')

    @mock.patch('api.yangCatalogApi.app.config.redis_users.is_approved', mock.MagicMock(return_value=False))
    @mock.patch('api.yangCatalogApi.app.config.redis_users.is_temp', mock.MagicMock(return_value=True))
    def test_register_user_tempuser_exist(self):
        body = {
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
        result = self.client.post('api/register-user', json=body)

        self.assertEqual(result.status_code, 409)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'User with username test is pending for permissions')

    @mock.patch('api.yangCatalogApi.app.config.redis_users.username_exists', mock.MagicMock(side_effect=RedisError))
    def test_register_user_db_exception(self):
        body = {
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
        result = self.client.post('api/register-user', json=body)

        self.assertEqual(result.status_code, 500)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Server problem connecting to database')

    def test_delete_modules_one_module(self):
        """Test correct action is taken for a valid deletion attempt."""
        name = 'yang-catalog'
        revision = '2018-04-03'
        organization = 'ietf'
        path = f'{name},{revision},{organization}'
        result = self.client.delete(f'api/modules/module/{path}', auth=('test', 'test'))

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
    def test_delete_modules_unavailable_module(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = ''
        mod = {'name': 'test', 'revision': '2017-01-01', 'organization': 'ietf'}
        path = f'{mod["name"]},{mod["revision"]},{mod["organization"]}'
        result = self.client.delete(f'api/modules/module/{path}', auth=('test', 'test'))

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
    def test_delete_modules_insufficient_rights(self, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give no rights.
        Test error response when the user has insufficient rights.
        """
        mock_access_rights.return_value = ''
        mod = {'name': 'yang-catalog', 'revision': '2017-09-26', 'organization': 'ietf'}
        path = f'{mod["name"]},{mod["revision"]},{mod["organization"]}'
        result = self.client.delete(f'api/modules/module/{path}', auth=('test', 'test'))

        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(
            data['description'],
            f'You do not have rights to delete modules with organization {mod["organization"]}',
        )

    def test_delete_modules_has_implementation(self):
        """Test skipped modules when the module has implementations."""
        mod = {'name': 'ietf-yang-types', 'revision': '2013-07-15', 'organization': 'ietf'}
        path = f'{mod["name"]},{mod["revision"]},{mod["organization"]}'
        result = self.client.delete(f'api/modules/module/{path}', auth=('test', 'test'))

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('skipped', data)
        self.assertEqual(data['skipped'], [mod])

    def test_delete_modules(self):
        body = self.payloads_content.get('delete_modules')

        result = self.client.delete('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    def test_delete_modules_missing_data(self):
        result = self.client.delete('api/modules', auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(
            data['description'],
            'The browser (or proxy) sent a request that this server could not understand.',
        )

    def test_delete_modules_missing_input(self):
        result = self.client.delete('api/modules', json={'input': {}}, auth=('test', 'test'))

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Data must start with "input" root element in json')

    def test_delete_vendor(self):
        """Test correct action is taken for a valid deletion attempt."""
        path = 'nonexistent'
        result = self.client.delete(f'api/vendors/{path}', auth=('test', 'test'))

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
    def test_delete_vendor_insufficient_rights(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = '/cisco'
        vendor_name = 'fujitsu'
        path = f'vendor/{vendor_name}'
        result = self.client.delete(f'api/vendors/{path}', auth=('test', 'test'))

        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'User not authorized to supply data for this vendor')

    def test_organization_by_namespace(self):
        self.assertEqual(mm.organization_by_namespace('http://cisco.com/test'), 'cisco')
        self.assertEqual(mm.organization_by_namespace('urn:test:test'), 'test')
        self.assertEqual(mm.organization_by_namespace('test'), '')

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.shutil.move')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.shutil.copy')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.shutil.rmtree')
    @mock.patch('utility.repoutil.RepoUtil', mock.MagicMock(**{'return_value.get_commit_hash.return_value': 'master'}))
    @mock.patch('requests.put')
    def test_add_modules(self, mock_put: mock.MagicMock, *args):
        body = self.payloads_content.get('add_modules')
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertIn(result.status_code, (200, 202))
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    @mock.patch('shutil.move')
    @mock.patch('shutil.copy')
    @mock.patch('shutil.rmtree')
    @mock.patch('utility.repoutil.RepoUtil')
    @mock.patch('requests.put')
    def test_add_modules_post(self, mock_put: mock.MagicMock, *args):
        body = self.payloads_content.get('add_modules')
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        result = self.client.post('api/modules', json=body, auth=('test', 'test'))

        self.assertIn(result.status_code, (200, 202))
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    def test_add_modules_no_json(self):
        result = self.client.put('api/modules', auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(
            data['description'],
            'The browser (or proxy) sent a request that this server could not understand.',
        )

    def test_add_modules_missing_modules(self):
        result = self.client.put('api/modules', json={'invalid': True}, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - "modules" json object is missing and is mandatory')

    def test_add_modules_missing_module(self):
        body = self.payloads_content.get('add_modules')
        body['modules'] = {}

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - "module" json list is missing and is mandatory')

    @mock.patch('requests.put')
    def test_add_modules_unparsable(self, mock_put: mock.MagicMock):
        mock_put.return_value.status_code = 400
        mock_put.return_value.text = 'test'
        body = self.payloads_content.get('add_modules')
        body['modules']['module'] = False

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertTrue(
            data['description'].startswith('The body you have provided could not be parsed. ConfD error text:'),
        )

    @mock.patch('requests.put')
    def test_add_modules_no_source_file(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        body['modules']['module'][0].pop('source-file')
        mock_put.return_value.status_code = 200

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('source-file', data['description'])

    @mock.patch('requests.put')
    def test_add_modules_no_organization(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        body['modules']['module'][0].pop('organization')
        mock_put.return_value.status_code = 200

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('organization', data['description'])

    @mock.patch('requests.put')
    def test_add_modules_no_name(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        body['modules']['module'][0].pop('name')
        mock_put.return_value.status_code = 200

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('name', data['description'])

    @mock.patch('requests.put')
    def test_add_modules_no_revision(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        body['modules']['module'][0].pop('revision')
        mock_put.return_value.status_code = 200

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('revision', data['description'])

    @mock.patch('requests.put')
    def test_add_modules_no_path(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        body['modules']['module'][0]['source-file'].pop('path')
        mock_put.return_value.status_code = 200

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('path', data['description'])

    @mock.patch('requests.put')
    def test_add_modules_no_repository(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        body['modules']['module'][0]['source-file'].pop('repository')
        mock_put.return_value.status_code = 200

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('repository', data['description'])

    @mock.patch('requests.put')
    def test_add_modules_no_owner(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        body['modules']['module'][0]['source-file'].pop('owner')
        mock_put.return_value.status_code = 200

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('owner', data['description'])

    @mock.patch('requests.put')
    def test_add_modules_invalid_repo(self, mock_put: mock.MagicMock):
        body = self.payloads_content.get('add_modules')
        body['modules']['module'][0]['source-file']['owner'] = 'foobar'
        mock_put.return_value.status_code = 200

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertTrue(
            data['description'].startswith(
                'bad request - could not clone the Github repository.'
                ' Please check owner, repository and path of the request - ',
            ),
        )

    @mock.patch('shutil.move')
    @mock.patch('shutil.copy')
    @mock.patch('shutil.rmtree')
    @mock.patch('utility.repoutil.RepoUtil')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
    @mock.patch('requests.put')
    def test_add_modules_unauthorized(self, mock_put: mock.MagicMock, mock_access_rights: mock.MagicMock, *args):
        body = self.payloads_content.get('add_modules')
        mock_put.return_value.status_code = 200
        mock_access_rights.return_value = ''

        result = self.client.put('api/modules', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Unauthorized for server unknown reason')

    @mock.patch('requests.put')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.authorize_for_vendors')
    @mock.patch('shutil.copy', mock.MagicMock)
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.repoutil.ModifiableRepoUtil', MockRepoUtil)
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.open', mock.mock_open())
    def test_add_vendor(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        body = self.payloads_content.get('add_vendor')
        result = self.client.put('api/platforms', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.repoutil.pull')
    @mock.patch('requests.put')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.authorize_for_vendors')
    @mock.patch('shutil.copy', mock.MagicMock)
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.repoutil.ModifiableRepoUtil', MockRepoUtil)
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.open', mock.mock_open())
    def test_add_vendor_post(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock, mock_pull: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        body = self.payloads_content.get('add_vendor')
        result = self.client.post('api/platforms', json=body, auth=('test', 'test'))

        mock_pull.assert_called()
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    def test_add_vendor_no_body(self):
        result = self.client.put('api/platforms', auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(
            data['description'],
            'The browser (or proxy) sent a request that this server could not understand.',
        )

    def test_add_vendor_no_platforms(self):
        result = self.client.put('api/platforms', json={'test': 'test'}, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('platforms', data['description'])

    def test_add_vendor_no_platform(self):
        result = self.client.put('api/platforms', json={'platforms': {'test': 'test'}}, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('platform', data['description'])

    @mock.patch('requests.put')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.authorize_for_vendors')
    def test_add_vendor_confd_error(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 400
        mock_put.return_value.text = 'test'
        result = self.client.put('api/platforms', json={'platforms': {'platform': 'test'}}, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertEqual(
            data['description'],
            'The body you have provided could not be parsed. ConfD error text:\ntest\nError code: 400',
        )

    @mock.patch('requests.put')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.authorize_for_vendors')
    def test_add_vendor_no_module_file_list(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        result = self.client.put(
            'api/platforms',
            json={'platforms': {'platform': [{'test': 'test'}]}},
            auth=('test', 'test'),
        )

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('module-list-file', data['description'])

    @mock.patch('requests.put')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.authorize_for_vendors')
    def test_add_vendor_no_path(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        body = self.payloads_content.get('add_vendor')
        body['platforms']['platform'][0]['module-list-file'].pop('path')
        result = self.client.put('api/platforms', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('path', data['description'])

    @mock.patch('requests.put')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.authorize_for_vendors')
    def test_add_vendor_no_repository(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        body = self.payloads_content.get('add_vendor')
        body['platforms']['platform'][0]['module-list-file'].pop('repository')
        result = self.client.put('api/platforms', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('repository', data['description'])

    @mock.patch('requests.put')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.authorize_for_vendors')
    def test_add_vendor_no_owner(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        body = self.payloads_content.get('add_vendor')
        body['platforms']['platform'][0]['module-list-file'].pop('owner')
        result = self.client.put('api/platforms', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertIn('owner', data['description'])

    @mock.patch('requests.put')
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.authorize_for_vendors')
    @mock.patch('shutil.copy', mock.MagicMock)
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.repoutil.RepoUtil', MockRepoUtil)
    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.open', mock.mock_open())
    def test_add_vendor_git_error(self, mock_authorize: mock.MagicMock, mock_put: mock.MagicMock):
        mock_authorize.return_value = True
        mock_put.return_value.status_code = 200
        body = self.payloads_content.get('add_vendor')
        result = self.client.put('api/platforms', json=body, auth=('test', 'test'))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('description', data)
        self.assertTrue(
            data['description'].startswith(
                'bad request - could not clone the Github repository.'
                ' Please check owner, repository and path of the request - ',
            ),
        )

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
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

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
    def test_authorize_for_vendors_root(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = '/'
        request = mock.MagicMock()
        request.authorization = {'username': 'test'}
        with app.app_context():
            result = mm.authorize_for_vendors(request, {})

        self.assertEqual(result, True)

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
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

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
    def test_authorize_for_sdos_root(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = '/'
        request = mock.MagicMock()
        request.authorization = {'username': 'test'}
        with app.app_context():
            result = mm.authorize_for_sdos(request, 'test', 'test')

        self.assertTrue(result)

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
    def test_authorize_for_sdos(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = 'test'
        request = mock.MagicMock()
        request.authorization = {'username': 'test'}
        with app.app_context():
            result = mm.authorize_for_sdos(request, 'test', 'test')

        self.assertTrue(result)

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
    def test_authorize_for_sdos_not_same(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = '/'
        request = mock.MagicMock()
        request.authorization = {'username': 'test'}
        with app.app_context():
            result = mm.authorize_for_sdos(request, 'test', 'other')

        self.assertEqual(result, 'module`s organization is not the same as organization provided')

    @mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.get_user_access_rights')
    def test_authorize_for_sdos_not_in_rights(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = 'test'
        request = mock.MagicMock()
        request.authorization = {'username': 'test'}
        with app.app_context():
            result = mm.authorize_for_sdos(request, 'test', 'other')

        self.assertEqual(result, 'module`s organization is not in users rights')

    @mock.patch('api.sender.Sender.get_response', mock.MagicMock(return_value='Failed#split#reason'))
    def test_get_job(self):
        job_id = 'invalid-id'
        result = self.client.get(f'api/job/{job_id}')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        data = json.loads(result.data)
        self.assertIn('info', data)
        self.assertIn('job-id', data['info'])
        self.assertEqual(data['info']['job-id'], 'invalid-id')
        self.assertIn('result', data['info'])
        self.assertEqual(data['info']['result'], 'Failed')
        self.assertIn('reason', data['info'])
        self.assertEqual(data['info']['reason'], 'reason')


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
