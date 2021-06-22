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

from api.yangCatalogApi import application

class TestApiContributeClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestApiContributeClass, self).__init__(*args, **kwargs)
        self.resources_path = '{}/resources/'.format(os.path.dirname(os.path.abspath(__file__)))
        self.client = application.test_client()
        #TODO: setup authentication - create new user maybe?

    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_module(self, mock_sender: mock.MagicMock, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give admin access.
        Sender patched to return job-id 1.
        Test correct action is taken for a valid deletion attempt.
        """
        mock_sender.send.return_value = 1
        mock_access_rights.return_value = '/'
        name = 'yang-catalog'
        revision = '2018-04-03'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_module_not_found(self, mock_sender: mock.MagicMock, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give admin access.
        Test error response when the specified module is not in the database.
        """
        mock_sender.send.return_value = 1
        mock_access_rights.return_value = '/'
        name = 'nonexistent'
        revision = 'nonexistent'
        organization = 'nonexistent'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Module not found in ConfD database')

    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_module_insufficient_rights(self, mock_sender: mock.MagicMock, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give no rights.
        Test error response when the user has insufficient rights.
        """
        mock_sender.send.return_value = 1
        mock_access_rights.return_value = ''
        name = 'yang-catalog'
        revision = '2017-09-26'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'],
                         'You do not have rights to delete module with organization {}'.format(organization))

    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_module_has_implementation(self, mock_sender: mock.MagicMock, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give admin access.
        Test error response when the module has implementations.
        """
        mock_sender.send.return_value = 1
        mock_access_rights.return_value = '/'
        name = 'ietf-yang-types'
        revision = '2013-07-15'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'This module has reference in vendors branch')

    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_module_dependency(self, mock_sender: mock.MagicMock, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give admin access.
        Test error response when the module has dependents.
        """
        mock_sender.send.return_value = 1
        mock_access_rights.return_value = '/'
        name = 'ietf-snmp-community'
        revision = '2014-12-10'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description']
                            .startswith('{}@{} module has reference in another module '
                            .format(name, revision)),
                         True)

    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_module_submodule(self, mock_sender: mock.MagicMock, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give admin access.
        Test error response when the module is a submodule.
        """
        mock_sender.send.return_value = 1
        mock_access_rights.return_value = '/'
        name = 'ietf-ipv6-router-advertisements'
        revision = '2018-03-13'
        organization = 'ietf'
        path = '{},{},{}'.format(name, revision, organization)
        result = self.client.delete('api/modules/module/{}'.format(path), auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description']
                            .startswith('{}@{} module has reference in another module '
                            .format(name, revision)),
                         True)

    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_modules(self, mock_sender: mock.MagicMock):
        mock_sender.send.return_value = 1
        with open('{}/payloads.json'.format(self.resources_path), 'r') as f:
            content = json.load(f)
        body = content.get('delete_modules')

        result = self.client.delete('api/modules', json=body, auth=('admin', 'admin'))
        data = json.loads(result.data)
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_modules_missing_data(self, mock_sender: mock.MagicMock):
        mock_sender.send.return_value = 1
        result = self.client.delete('api/modules', auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Missing input data to know which modules we want to delete')

    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_modules_missing_input(self, mock_sender: mock.MagicMock):
        mock_sender.send.return_value = 1
        result = self.client.delete('api/modules', json={'input': {}}, auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], "Data must start with 'input' root element in json")

    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_vendor(self, mock_sender: mock.MagicMock, mock_access_rights: mock.MagicMock):
        """get_user_access_rights patched to give admin access.
        Sender patched to return job-id 1.
        Test correct action is taken for a valid deletion attempt.
        """
        mock_access_rights.return_value = '/'
        mock_sender.send.return_value = 1
        path = 'nonexistent'
        result = self.client.delete('api/vendors/{}'.format(path), auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    #TODO: fix this
    @mock.patch('api.views.userSpecificModuleMaintenace.moduleMaintanace.get_user_access_rights')
    @mock.patch('api.globalConfig.yc_gc.sender')
    def test_delete_vendor_insufficient_rights(self, mock_sender: mock.MagicMock, mock_access_rights: mock.MagicMock):
        mock_access_rights.return_value = 'cisco'
        mock_sender.send.return_value = 1
        vendor_name = 'fujitsu'
        path = 'vendor/{}'.format(vendor_name)
        result = self.client.delete('api/vendors/{}'.format(path), auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'User not authorized to supply data for this vendor')

    def test_add_modules(self):
        pass

    def test_add_modules_no_json(self):
        result =  self.client.put('api/modules', auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - you need to input json body that conforms with'
                                              ' module-metadata.yang module. Received no json')

    def test_add_modules_missing_modules(self):
        result =  self.client.put('api/modules', json={'invalid': True}, auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - "modules" json object is missing and is mandatory')

    def test_add_modules_missing_module(self):
        result =  self.client.put('api/modules', json={'modules': {}}, auth=('admin', 'admin'))
        data = json.loads(result.data)

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.content_type, 'application/json')
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'bad request - "module" json list is missing and is mandatory')

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
        