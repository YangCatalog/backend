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
from copy import deepcopy
from pathlib import Path
from unittest import mock

from redis import RedisError
from werkzeug.exceptions import HTTPException

import api.views.admin as admin
from api.yangcatalog_api import app
from redisConnections.redis_users_connection import RedisUsersConnection

app_config = app.config


class TestApiAdminClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        cls.client = app.test_client()
        cls.users = RedisUsersConnection()
        with open(os.path.join(resources_path, 'payloads.json'), 'r') as f:
            content = json.load(f)
        fields = content['user']['input']
        cls.user_info_fields = {key.replace('-', '_'): value for key, value in fields.items()}
        with open(os.path.join(resources_path, 'testlog.log'), 'r') as f:
            cls.test_log_text = f.read()
        with open(os.path.join(resources_path, 'payloads.json'), 'r') as f:
            cls.payloads_content = json.load(f)

    def setUp(self):
        self.uid = self.users.create(temp=True, **self.user_info_fields)

    def tearDown(self):
        self.users.delete(self.uid, temp=True)

    def test_catch_db_error(self):
        with app.app_context():

            def error():
                raise RedisError

            result = admin.catch_db_error(error)()

        self.assertEqual(result, ({'error': 'Server problem connecting to database'}, 500))

    def test_get_input(self):
        result = admin.get_input({'input': 'test'})
        self.assertEqual(result, 'test')

    def test_get_input_empty(self):
        try:
            admin.get_input(None)
        except HTTPException as e:
            self.assertEqual(e.description, 'bad-request - body can not be empty')

    def test_get_input_empty_no_input(self):
        try:
            admin.get_input({})
        except HTTPException as e:
            self.assertEqual(e.description, 'bad-request - body has to start with "input" and can not be empty')

    def test_logout(self):
        result = self.client.post('api/admin/logout')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')

    def test_check(self):
        result = self.client.get('api/admin/check')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')

    @mock.patch('builtins.open', mock.mock_open(read_data='test'))
    def test_read_admin_file(self):
        path = 'all_modules/yang-catalog@2018-04-03.yang'
        result = self.client.get(f'api/admin/directory-structure/read/{path}')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], 'test')

    def test_read_admin_file_not_found(self):
        path = 'nonexistent'
        result = self.client.get(f'api/admin/directory-structure/read/{path}')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'error - file does not exist')

    def test_read_admin_file_directory(self):
        path = 'all_modules'
        result = self.client.get(f'api/admin/directory-structure/read/{path}')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'error - file does not exist')

    @mock.patch('os.unlink')
    def test_delete_admin_file(self, mock_unlink: mock.MagicMock):
        path = 'all_modules/yang-catalog@2018-04-03.yang'
        result = self.client.delete(f'api/admin/directory-structure/{path}')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(
            data['data'],
            f'directory of file {app_config.d_var}/{path} removed succesfully',
        )

    @mock.patch('shutil.rmtree')
    def test_delete_admin_file_directory(self, mock_rmtree: mock.MagicMock):
        result = self.client.delete('api/admin/directory-structure')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], f'directory of file {app_config.d_var}/ removed succesfully')

    def test_delete_admin_file_nonexistent(self):
        result = self.client.delete('api/admin/directory-structure/nonexistent')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'error - file or folder does not exist')

    @mock.patch('builtins.open', mock.mock_open())
    def test_write_to_directory_structure(self):
        path = 'all_modules/yang-catalog@2018-04-03.yang'
        result = self.client.put(f'api/admin/directory-structure/{path}', json={'input': {'data': 'test'}})

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], 'test')

    def test_write_to_directory_structure_no_data(self):
        path = 'all_modules/yang-catalog@2018-04-03.yang'
        result = self.client.put(f'api/admin/directory-structure/{path}', json={'input': {}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], '"data" must be specified')

    def test_write_to_directory_structure_not_found(self):
        path = 'nonexistent'
        result = self.client.put(f'api/admin/directory-structure/{path}', json={'input': {'data': 'test'}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'error - file does not exist')

    @mock.patch('os.walk')
    @mock.patch('os.lstat')
    @mock.patch.object(Path, 'glob')
    @mock.patch.object(Path, 'stat')
    def test_get_var_yang_directory_structure(
        self,
        mock_stat: mock.MagicMock,
        mock_glob: mock.MagicMock,
        mock_lstat: mock.MagicMock,
        mock_walk: mock.MagicMock,
    ):
        good_stat = mock.MagicMock()
        good_stat.st_size = 0
        good_stat.st_gid = 0
        good_stat.st_uid = 0
        good_stat.st_mtime = 0
        bad_stat = mock.MagicMock()
        bad_stat.st_size = 0
        bad_stat.st_gid = 2354896
        bad_stat.st_uid = 2354896
        bad_stat.st_mtime = 0
        mock_stat.side_effect = [good_stat, bad_stat, good_stat, bad_stat]
        mock_glob.return_value = ()
        lstat = mock.MagicMock()
        lstat.st_mode = 0o777
        mock_lstat.return_value = lstat
        mock_walk.return_value = [('root', ('testdir', 'testdir2'), ('test', 'test2'))].__iter__()
        result = self.client.get('api/admin/directory-structure')

        structure = {
            'name': 'root',
            'files': [
                {'name': 'test', 'size': 0, 'group': 'root', 'user': 'root', 'permissions': '0o777', 'modification': 0},
                {
                    'name': 'test2',
                    'size': 0,
                    'group': 2354896,
                    'user': 2354896,
                    'permissions': '0o777',
                    'modification': 0,
                },
            ],
            'folders': [
                {
                    'name': 'testdir',
                    'size': 0,
                    'group': 'root',
                    'user': 'root',
                    'permissions': '0o777',
                    'modification': 0,
                },
                {
                    'name': 'testdir2',
                    'size': 0,
                    'group': 2354896,
                    'user': 2354896,
                    'permissions': '0o777',
                    'modification': 0,
                },
            ],
        }

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], structure)

    @mock.patch('os.listdir')
    def test_read_yangcatalog_nginx_files(self, mock_listdir: mock.MagicMock):
        mock_listdir.return_value = ['test']
        result = self.client.get('api/admin/yangcatalog-nginx')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], ['sites-enabled/test', 'nginx.conf', 'conf.d/test'])

    @mock.patch('builtins.open', mock.mock_open(read_data='test'))
    def test_read_yangcatalog_nginx(self):
        result = self.client.get('api/admin/yangcatalog-nginx/test')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], 'test')

    @mock.patch('builtins.open', mock.mock_open(read_data='test'))
    def test_read_yangcatalog_config(self):
        result = self.client.get('api/admin/yangcatalog-config')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], 'test')

    @mock.patch('api.yangcatalog_api.app.config.sender.send', mock.MagicMock)
    @mock.patch('api.views.admin.open')
    def test_update_yangcatalog_config(self, mock_open: mock.MagicMock):
        mock.mock_open(mock_open)
        result = self.client.put('/api/admin/yangcatalog-config', json={'input': {'data': 'test'}})

        f = mock_open()
        f.write.assert_called_with('test')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)

    @mock.patch('requests.post')
    @mock.patch('api.sender.Sender.send')
    @mock.patch('api.yangcatalog_api.app.load_config')
    @mock.patch('builtins.open')
    def test_update_yangcatalog_config_errors(
        self,
        mock_open: mock.MagicMock,
        mock_load_config: mock.MagicMock,
        mock_send: mock.MagicMock,
        mock_post: mock.MagicMock,
    ):
        mock.mock_open(mock_open)
        mock_load_config.side_effect = Exception
        mock_send.side_effect = Exception
        mock_post.return_value.status_code = 404
        result = self.client.put('/api/admin/yangcatalog-config', json={'input': {'data': 'test'}})

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        info = {'api': 'error loading data', 'receiver': 'error loading data'}
        self.assertEqual(data['info'], info)
        self.assertIn('new-data', data)
        self.assertEqual(data['new-data'], 'test')

    def test_update_yangcatalog_config_no_data(self):
        result = self.client.put('/api/admin/yangcatalog-config', json={'input': {}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], '"data" must be specified')

    @mock.patch('os.walk')
    def test_get_log_files(self, mock_walk: mock.MagicMock):
        mock_walk.return_value = [('root/logs', [], ['test', 'test.log'])]
        result = self.client.get('api/admin/logs')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], ['test'])

    @mock.patch('os.walk')
    def test_find_files(self, mock_walk: mock.MagicMock):
        mock_walk.return_value = iter((('/', (), ('thing.bad', 'badlog', 'good.log', 'good.log-more')),))
        result = tuple(admin.find_files('/', 'good.log*'))

        self.assertEqual(result, ('/good.log', '/good.log-more'))

    @mock.patch('os.path.getmtime')
    @mock.patch('api.views.admin.find_files')
    def test_filter_from_date(self, mock_find_files: mock.MagicMock, mock_getmtime: mock.MagicMock):
        mock_find_files.return_value = iter(('test1', 'test2', 'test3'))
        mock_getmtime.side_effect = (1, 2, 3)

        result = admin.filter_from_date(['logfile'], 2)

        self.assertEqual(result, ['test2', 'test3'])

    def test_filter_from_date_no_from_timestamp(self):
        result = admin.filter_from_date(['logfile'], None)

        self.assertEqual(result, [f'{app_config.d_logs}/logfile.log'])

    @mock.patch('builtins.open')
    def test_find_timestamp(self, mock_open: mock.MagicMock):
        mock.mock_open(mock_open, read_data='2000-01-01 00:00:00')
        result = admin.find_timestamp(
            'test',
            r'([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))',
            r'(?:[01]\d|2[0-3]):(?:[0-5]\d):(?:[0-5]\d)',
        )
        self.assertEqual(result, 946684800.0)

    @mock.patch('builtins.open')
    def test_find_timestamp_not_found(self, mock_open: mock.MagicMock):
        mock.mock_open(mock_open, read_data='test')
        result = admin.find_timestamp(
            'test',
            r'([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))',
            r'(?:[01]\d|2[0-3]):(?:[0-5]\d):(?:[0-5]\d)',
        )
        self.assertEqual(result, None)

    @mock.patch('builtins.open')
    def test_determine_formatting_false(self, mock_open: mock.MagicMock):
        mock.mock_open(mock_open, read_data='test')
        result = admin.determine_formatting(
            'test',
            r'([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))',
            r'(?:[01]\d|2[0-3]):(?:[0-5]\d):(?:[0-5]\d)',
        )

        self.assertFalse(result)

    @mock.patch('builtins.open')
    def test_determine_formatting_true(self, mock_open: mock.MagicMock):
        data = '2000-01-01 00:00:00 ERROR two words =>\n' * 2
        mock.mock_open(mock_open, read_data=data)
        result = admin.determine_formatting(
            'test',
            r'([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))',
            r'(?:[01]\d|2[0-3]):(?:[0-5]\d):(?:[0-5]\d)',
        )

        self.assertTrue(result)

    def test_generate_output(self):
        date_regex = r'([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))'
        time_regex = r'(?:[01]\d|2[0-3]):(?:[0-5]\d):(?:[0-5]\d)'
        with mock.patch('builtins.open', mock.mock_open(read_data=self.test_log_text)):
            result = admin.generate_output(False, ['test'], None, None, None, date_regex, time_regex)

        self.assertEqual(result, list(reversed(self.test_log_text.splitlines())))

    def test_generate_output_filter(self):
        filter = {
            'match-case': False,
            'match-words': True,
            'filter-out': 'deleting',
            'search-for': 'yangcatalog',
            'level': 'warning',
        }
        date_regex = r'([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))'
        time_regex = r'(?:[01]\d|2[0-3]):(?:[0-5]\d):(?:[0-5]\d)'
        with mock.patch('builtins.open', mock.mock_open(read_data=self.test_log_text)):
            result = admin.generate_output(True, ['test'], filter, 1609455600.0, 1640905200.0, date_regex, time_regex)

        self.assertEqual(
            result,
            ['2021-07-07 11:02:39 WARNING     admin.py   api => Getting yangcatalog log files - 298\nt'],
        )

    def test_generate_output_filter_match_case(self):
        filter = {
            'match-case': True,
            'match-words': True,
            'filter-out': 'Deleting',
            'search-for': 'yangcatalog',
            'level': 'warning',
        }
        date_regex = r'([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))'
        time_regex = r'(?:[01]\d|2[0-3]):(?:[0-5]\d):(?:[0-5]\d)'
        with mock.patch('builtins.open', mock.mock_open(read_data=self.test_log_text)):
            result = admin.generate_output(True, ['test'], filter, 1609455600.0, 1640905200.0, date_regex, time_regex)

        self.assertEqual(
            result,
            ['2021-07-07 11:02:39 WARNING     admin.py   api => Getting yangcatalog log files - 298\nt'],
        )

    @mock.patch('api.views.admin.generate_output', mock.MagicMock(return_value=3 * ['test']))
    @mock.patch('api.views.admin.determine_formatting', mock.MagicMock(return_value=True))
    @mock.patch('api.views.admin.find_timestamp', mock.MagicMock(return_value=0))
    @mock.patch('api.views.admin.filter_from_date', mock.MagicMock())
    def test_get_logs(self):
        body = {'input': {'lines-per-page': 2, 'page': 2}}

        result = self.client.post('/api/admin/logs', json=body)

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('meta', data)
        meta = {
            'file-names': ['yang'],
            'from-date': 0,
            'to-date': data['meta'].get('to-date'),
            'lines-per-page': 2,
            'page': 2,
            'pages': 2,
            'filter': None,
            'format': True,
        }
        self.assertEqual(data['meta'], meta)
        self.assertIn('output', data)
        self.assertEqual(data['output'], ['test'])

    def test_move_user(self):
        self.addCleanup(self.users.delete, self.uid, temp=False)
        body = {'id': self.uid, 'access-rights-sdo': 'test'}
        result = self.client.post('api/admin/move-user', json={'input': body})

        self.assertEqual(result.status_code, 201)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'user successfully approved')
        self.assertIn('data', data)
        self.assertEqual(data['data'], body)
        self.assertTrue(self.users.is_approved(self.uid))

    def test_move_user_no_id(self):
        result = self.client.post('api/admin/move-user', json={'input': {}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'id of a user is missing')

    def test_move_user_no_access(self):
        result = self.client.post('api/admin/move-user', json={'input': {'id': self.uid}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'access-rights-sdo OR access-rights-vendor must be specified')

    def test_create_user(self):
        body = self.payloads_content['user']

        result = self.client.post('api/admin/users/temp', json=body)

        self.assertEqual(result.status_code, 201)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'data successfully added to database')
        self.assertIn('data', data)
        self.assertEqual(data['data'], body['input'])
        self.assertIn('id', data)
        self.assertTrue(self.users.is_temp(data['id']))
        self.users.delete(data['id'], temp=True)

    def test_create_user_invalid_status(self):
        body = self.payloads_content['user']

        result = self.client.post('api/admin/users/fake', json=body)

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'invalid status "fake", use only "temp" or "approved" allowed')

    def test_create_user_args_missing(self):
        body = deepcopy(self.payloads_content['user'])
        body['input']['username'] = ''

        result = self.client.post('api/admin/users/temp', json=body)

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(
            data['description'],
            'username - , firstname - john, last-name - doe,'
            ' email - j@d.com and password - secret must be specified',
        )

    def test_create_user_missing_access_rights(self):
        body = self.payloads_content['user']

        result = self.client.post('api/admin/users/approved', json=body)

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'access-rights-sdo OR access-rights-vendor must be specified')

    def test_delete_user(self):
        result = self.client.delete(f'api/admin/users/temp/id/{self.uid}')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], f'id {self.uid} deleted successfully')
        self.assertFalse(self.users.is_temp(self.uid))

    def test_delete_user_invalid_status(self):
        result = self.client.delete(f'api/admin/users/fake/id/{self.uid}')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'invalid status "fake", use only "temp" or "approved" allowed')

    def test_delete_user_id_not_found(self):
        result = self.client.delete('api/admin/users/approved/id/24857629847625894258476')

        self.assertEqual(result.status_code, 404)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'id 24857629847625894258476 not found with status approved')

    def test_update_user(self):
        body = deepcopy(self.payloads_content['user'])
        body['input']['username'] = 'jdoe'

        result = self.client.put(f'api/admin/users/temp/id/{self.uid}', json=body)

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], f'ID {self.uid} updated successfully')
        self.assertEqual(self.users.get_field(self.uid, 'username'), 'jdoe')

    def test_update_user_invalid_status(self):
        result = self.client.put(f'api/admin/users/fake/id/{self.uid}')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'invalid status "fake", use only "temp" or "approved" allowed')

    def test_update_user_args_missing(self):
        result = self.client.put(f'api/admin/users/temp/id/{self.uid}', json={'input': {}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'username and email must be specified')

    def test_update_user_id_not_found(self):
        result = self.client.put('api/admin/users/approved/id/24857629847625894258476')

        self.assertEqual(result.status_code, 404)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'id 24857629847625894258476 not found with status approved')

    def test_get_users(self):
        result = self.client.get('api/admin/users/temp')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertTrue(isinstance(data, list))

    def test_get_script_details(self):
        result = self.client.get('api/admin/scripts/reviseSemver')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('data', data)

    def test_get_script_details_invalid_name(self):
        result = self.client.get('api/admin/scripts/invalid')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], '"invalid" is not valid script name')

    @mock.patch('api.yangcatalog_api.app.config.job_runner', mock.MagicMock())
    @mock.patch('uuid.uuid4', mock.MagicMock(return_value='1'))
    def test_run_script_with_args(self):
        result = self.client.post('api/admin/scripts/populate', json={'input': 'test'})

        self.assertEqual(result.status_code, 202)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], '1')
        self.assertIn('arguments', data)
        self.assertEqual(data['arguments'], ['parseAndPopulate', 'populate', 'test'])

    @mock.patch('api.yangcatalog_api.app.config.job_runner', mock.MagicMock())
    @mock.patch('uuid.uuid4', mock.MagicMock(return_value='1'))
    def test_run_script_with_args_invalid_name(self):
        result = self.client.post('api/admin/scripts/invalid')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], '"invalid" is not valid script name')

    def test_get_script_names(self):
        result = self.client.get('api/admin/scripts')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('data', data)
        self.assertIsInstance(data['data'], list)
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')

    def test_get_disk_usage(self):
        result = self.client.get('api/admin/disk-usage')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('data', data)
        self.assertIn('total', data['data'])
        self.assertIn('used', data['data'])
        self.assertIn('free', data['data'])
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')


if __name__ == '__main__':
    unittest.main()
