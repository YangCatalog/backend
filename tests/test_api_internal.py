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
import unittest
from unittest import mock

from api.authentication.auth import auth
from api.yangCatalogApi import app

app_config = app.config


class TestApiInternalClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        cls.client = app.test_client()
        with open(os.path.join(resources_path, 'payloads.json'), 'r') as f:
            cls.payloads_content = json.load(f)

    @mock.patch('api.sender.Sender.send', mock.MagicMock(return_value=1))
    def test_trigger_ietf_pull(self):
        auth.hash_password(lambda _: 'True')
        auth.get_password(lambda _: 'True')
        result = self.client.get('api/ietf', auth=('admin', 'admin'))

        self.assertEqual(result.status_code, 202)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)

    @mock.patch('api.sender.Sender.send', mock.MagicMock(return_value=1))
    def test_trigger_ietf_pull_not_admin(self):
        auth.hash_password(lambda _: 'True')
        auth.get_password(lambda _: 'True')
        result = self.client.get('api/ietf', auth=('user', 'user'))

        self.assertEqual(result.status_code, 401)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'User must be admin')

    @mock.patch('requests.post')
    @mock.patch('api.views.ycJobs.ycJobs.open', mock.mock_open(read_data='test'))
    def test_get_local_fork_passed(self, mock_post: mock.MagicMock):
        mock_post.return_value.status_code = 201
        body = self.payloads_content['check_local']
        body['repository']['owner_name'] = 'yang-catalog'
        body['result_message'] = 'Passed'
        body['type'] = 'push'
        result = self.client.post(
            'api/checkComplete',
            data={'payload': json.dumps(body)},
            headers=(('SIGNATURE', 'test'),),
        )

        self.assertEqual(result.status_code, 201)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')

    @mock.patch('requests.post')
    @mock.patch('api.views.ycJobs.ycJobs.open', mock.mock_open(read_data='test'))
    def test_get_local_fork_passed_couldnt_create(self, mock_post: mock.MagicMock):
        mock_post.return_value.status_code = 400
        body = self.payloads_content['check_local']
        body['repository']['owner_name'] = 'yang-catalog'
        body['result_message'] = 'Passed'
        body['type'] = 'push'
        result = self.client.post(
            'api/checkComplete',
            data={'payload': json.dumps(body)},
            headers=(('SIGNATURE', 'test'),),
        )

        self.assertEqual(result.status_code, 400)

    @mock.patch('requests.delete', mock.MagicMock())
    @mock.patch('api.views.ycJobs.ycJobs.open', mock.mock_open(read_data='test'))
    def test_get_local_fork_failed(self):
        body = self.payloads_content['check_local']
        body['repository']['owner_name'] = 'yang-catalog'
        body['result_message'] = 'Failed'
        body['type'] = 'push'
        result = self.client.post(
            'api/checkComplete',
            data={'payload': json.dumps(body)},
            headers=(('SIGNATURE', 'test'),),
        )

        self.assertEqual(result.status_code, 406)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Failed')

    @mock.patch('requests.post', mock.MagicMock())
    @mock.patch('requests.put', mock.MagicMock())
    @mock.patch('api.views.ycJobs.ycJobs.open', mock.mock_open(read_data='test'))
    def test_get_local_pr_passed(self):
        body = self.payloads_content['check_local']
        body['repository']['owner_name'] = 'YangModels'
        body['result_message'] = 'Passed'
        body['type'] = 'pull_request'
        result = self.client.post(
            'api/checkComplete',
            data={'payload': json.dumps(body)},
            headers=(('SIGNATURE', 'test'),),
        )

        self.assertEqual(result.status_code, 201)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')

    @mock.patch('requests.patch', mock.MagicMock())
    @mock.patch('requests.delete', mock.MagicMock())
    @mock.patch('api.views.ycJobs.ycJobs.open', mock.mock_open(read_data='test'))
    def test_get_local_pr_failed(self):
        body = self.payloads_content['check_local']
        body['repository']['owner_name'] = 'YangModels'
        body['result_message'] = 'Failed'
        body['type'] = 'pull_request'
        result = self.client.post(
            'api/checkComplete',
            data={'payload': json.dumps(body)},
            headers=(('SIGNATURE', 'test'),),
        )

        self.assertEqual(result.status_code, 406)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Failed')

    @mock.patch('api.views.ycJobs.ycJobs.open', mock.mock_open(read_data='test'))
    def test_get_local_unknown_owner(self):
        body = self.payloads_content['check_local']
        body['repository']['owner_name'] = 'nonexistent'
        body['result_message'] = 'Failed'
        result = self.client.post(
            'api/checkComplete',
            data={'payload': json.dumps(body)},
            headers=(('SIGNATURE', 'test'),),
        )

        self.assertEqual(result.status_code, 401)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('Error', data)
        self.assertEqual(data['Error'], 'Owner verfication failed')

    @mock.patch('api.views.ycJobs.ycJobs.open', mock.mock_open(read_data='no'))
    def test_get_local_unknown_commit(self):
        body = self.payloads_content['check_local']
        body['repository']['owner_name'] = 'yang-catalog'
        body['result_message'] = 'Passed'
        body['type'] = 'push'
        result = self.client.post(
            'api/checkComplete',
            data={'payload': json.dumps(body)},
            headers=(('SIGNATURE', 'test'),),
        )

        self.assertEqual(result.status_code, 500)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('Error', data)
        self.assertEqual(data['Error'], 'Fails')

    def test_get_local_commit_file_not_found(self):
        patcher = mock.patch('builtins.open')
        mock_open = patcher.start()
        self.addCleanup(patcher.stop)
        mock_open.side_effect = FileNotFoundError
        body = self.payloads_content.get('check_local')

        result = self.client.post(
            'api/checkComplete',
            data={'payload': json.dumps(body)},
            headers=(('SIGNATURE', 'test'),),
        )

        self.assertEqual(result.status_code, 404)

    @mock.patch('utility.message_factory.MessageFactory', mock.MagicMock())
    def test_get_local_not_authorized(self):
        result = self.client.post('api/checkComplete', data={'payload': json.dumps({'type': 'test'})})

        self.assertEqual(result.status_code, 401)

    @mock.patch.object(app_config.sender, 'send', mock.MagicMock())
    @mock.patch('utility.message_factory.MessageFactory')
    @mock.patch('utility.repoutil.pull', mock.MagicMock())
    def test_trigger_populate(self, mock_message_factory: mock.MagicMock):
        body = {
            'commits': [
                {
                    'added': ['vendor/cisco/nx/9.2-2/platform-metadata.json'],
                    'modified': ['vendor/cisco/xe/1651/platform-metadata.json'],
                },
            ],
        }
        result = self.client.post('api/check-platform-metadata', json=body)

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        mock_message_factory.return_value.send_new_modified_platform_metadata.call_args.assert_called_with(
            'vendor/cisco/nx/9.2-2',
            'vendor/cisco/xe/1651',
        )

    @mock.patch.object(app_config.sender, 'send', mock.MagicMock())
    @mock.patch('utility.message_factory.MessageFactory', mock.MagicMock())
    @mock.patch('utility.repoutil.pull', mock.MagicMock())
    def test_trigger_populate_empty(self):
        result = self.client.post('api/check-platform-metadata')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')

    @mock.patch('builtins.open', mock.mock_open(read_data='{"test": true}'))
    @mock.patch('os.path.exists')
    def test_get_statistics(self, mock_exists: mock.MagicMock):
        mock_exists.return_value = True
        result = self.client.get('api/get-statistics')

        self.assertEqual(result.status_code, 200)

    @mock.patch('os.path.exists')
    def test_get_statistics_not_generated(self, mock_exists: mock.MagicMock):
        mock_exists.return_value = False
        result = self.client.get('api/get-statistics')

        self.assertEqual(result.status_code, 404)
        self.assertEqual(result.content_type, 'application/json')
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Statistics file has not been generated yet')


if __name__ == '__main__':
    unittest.main()
