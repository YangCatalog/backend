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

__author__ = "Richard Zilincik"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "richard.zilincik@pantheon.tech"

import os
import unittest
from unittest import mock
import json

from flask import app

from api.yangCatalogApi import application
from api.globalConfig import yc_gc
from api.models import User
from api.views.admin.admin import hash_pw

db = yc_gc.sqlalchemy


class TestApiContributeClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestApiContributeClass, self).__init__(*args, **kwargs)
        self.resources_path = '{}/resources/'.format(os.path.dirname(os.path.abspath(__file__)))
        self.client = application.test_client()
        #TODO: setup authentication - create new user maybe?

    def setUp(self):
        self.patcher = mock.patch.object(yc_gc.sender, 'send')
        self.mock_send = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.mock_send.return_value = 1
        with application.app_context():
            self.user = User(Username='test', Password=hash_pw('test'), Email='test@test.test',
                        AccessRightsSdo='/', AccessRightsVendor='/')
            db.session.add(self.user)
            db.session.commit()

    def tearDown(self):
        with application.app_context():
            db.session.delete(self.user)
            db.session.commit()

    def test_delete_module(self):
        """Test correct action is taken for a valid deletion attempt.
        """
        name = 'yang-catalog'
        revision = '2018-04-03'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    def test_delete_module_not_found(self):
        """Test error response when the specified module is not in the database.
        """
        name = 'nonexistent'
        revision = 'nonexistent'
        organization = 'nonexistent'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Module not found in ConfD database')

    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    def test_delete_module_insufficient_rights(self, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give no rights.
        Test error response when the user has insufficient rights.
        """
        mock_access_rights.return_value = ''
        name = 'yang-catalog'
        revision = '2017-09-26'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'],
                         'You do not have rights to delete module with organization {}'.format(organization))

    def test_delete_module_has_implementation(self):
        """Test error response when the module has implementations.
        """
        name = 'ietf-yang-types'
        revision = '2013-07-15'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'This module has reference in vendors branch')

    def test_delete_module_dependency(self):
        """Test error response when the module has dependents.
        """
        name = 'ietf-snmp-community'
        revision = '2014-12-10'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertTrue(data['description']
                            .startswith('{}@{} module has reference in another module '
                            .format(name, revision)))

    def test_delete_module_submodule(self):
        """Test error response when the module is a submodule.
        """
        name = 'ietf-ipv6-router-advertisements'
        revision = '2018-03-13'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertTrue(data['description']
                            .startswith('{}@{} module has reference in another module '
                            .format(name, revision)))

    def test_delete_modules(self):
        with open('{}/payloads.json'.format(self.resources_path), 'r') as f:
            content = json.load(f)
        body = content.get('delete_modules')

        result = self.client.delete('api/modules', json=body, auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    def test_delete_modules_missing_data(self):
        result = self.client.delete('api/modules', auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Missing input data to know which modules we want to delete')

    def test_delete_modules_missing_input(self):
        result = self.client.delete('api/modules', json={'input': {}}, auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], "Data must start with 'input' root element in json")

    def test_delete_vendor(self):
        """Test correct action is taken for a valid deletion attempt.
        """
        path = 'nonexistent'
        result = self.client.delete('api/vendors/{}'.format(path), auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    def test_delete_vendor_insufficient_rights(self, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = 'cisco'
        vendor_name = 'fujitsu'
        path = 'vendor/{}'.format(vendor_name)
        result = self.client.delete('api/vendors/{}'.format(path), auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'User not authorized to supply data for this vendor')

    def test_add_modules(self):
        pass

    def test_add_modules_no_json(self):
        result =  self.client.put('api/modules', auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - you need to input json body that conforms with'
                                              ' module-metadata.yang module. Received no json')

    def test_add_modules_missing_modules(self):
        result =  self.client.put('api/modules', json={'invalid': True}, auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - "modules" json object is missing and is mandatory')

    def test_add_modules_missing_module(self):
        with open('{}/payloads.json'.format(self.resources_path), 'r') as f:
            content = json.load(f)
        body = content.get('add_modules')
        body['modules'] = {}

        result =  self.client.put('api/modules', json=body, auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - "module" json list is missing and is mandatory')

    def test_add_modules_unparsable(self):
        with open('{}/payloads.json'.format(self.resources_path), 'r') as f:
            content = json.load(f)
        body = content.get('add_modules')
        body['modules']['module'] = False

        result =  self.client.put('api/modules', json=body, auth=('test', 'test'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertTrue(data['description'].startswith('The body you have provided could not be parsed. Confd error text: '))

    @mock.patch('requests.put')
    def test_add_modules_no_source_file(self, mock_put: mock.MagicMock):
        with open('{}/payloads.json'.format(self.resources_path), 'r') as f:
            content = json.load(f)
        body = content.get('add_modules')
        body['modules']['module'] = [{}]
        mock_put.return_value = mock.MagicMock().status_code = 200

        result =  self.client.put('api/modules', json=body, auth=('test', 'test'))
        print(result.data)
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - at least one of modules "source-file" is missing and is mandatory')

    def test_get_job(self):
        job_id = 'invalid-id'
        result = self.client.get('api/job/{}'.format(job_id))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('info', data)
        self.assertIn('job-id', data['info'])
        self.assertEqual(data['info']['job-id'], 'invalid-id')
        self.assertIn('result', data['info'])
        self.assertEqual(data['info']['result'], 'does not exist')
        self.assertIn('reason', data['info'])
        self.assertEqual(data['info']['reason'], None)
        