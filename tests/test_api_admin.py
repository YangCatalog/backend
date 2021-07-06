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

from pathlib import Path
from unittest import mock
import unittest
import os
import json

from sqlalchemy.exc import SQLAlchemyError

from api.globalConfig import yc_gc
from api.yangCatalogApi import application
from api.models import User
from api.views.admin.admin import catch_db_error


class TestApiAdminClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestApiAdminClass, self).__init__(*args, **kwargs)
        self.resources_path = '{}/resources/'.format(os.path.dirname(os.path.abspath(__file__)))
        self.client = application.test_client()

    def setUp(self):
        self.patcher = mock.patch('flask_oidc.OpenIDConnect.user_loggedin')
        self.mock_user_loggedin = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.mock_user_loggedin = True

    def test_catch_db_error(self):
        def error():
            raise SQLAlchemyError
        result = catch_db_error(error)()

        self.assertEqual(result, ({'error': 'Server problem connecting to database'}, 500))

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
        result = self.client.get('api/admin/directory-structure/read/{}'.format(path))

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], 'test')

    def test_read_admin_file_not_found(self):
        path = 'nonexistent'
        result = self.client.get('api/admin/directory-structure/read/{}'.format(path))

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'error - file does not exist')

    def test_read_admin_file_directory(self):
        path = 'all_modules'
        result = self.client.get('api/admin/directory-structure/read/{}'.format(path))

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'error - file does not exist')

    @mock.patch('os.unlink')
    def test_delete_admin_file(self, mock_unlink: mock.MagicMock):
        path = 'all_modules/yang-catalog@2018-04-03.yang'
        result = self.client.delete('api/admin/directory-structure/{}'.format(path))

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], 'directory of file {} removed succesfully'
                                       .format('{}/{}'.format(yc_gc.var_yang, path)))

    @mock.patch('shutil.rmtree')
    def test_delete_admin_file_directory(self, mock_rmtree: mock.MagicMock):
        result = self.client.delete('api/admin/directory-structure')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], 'directory of file {}/ removed succesfully'.format(yc_gc.var_yang))

    @mock.patch('builtins.open', mock.mock_open())
    def test_write_to_directory_structure(self):
        path = 'all_modules/yang-catalog@2018-04-03.yang'
        result = self.client.put('api/admin/directory-structure/{}'.format(path), json={'input': {'data': 'test'}})

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Success')
        self.assertIn('data', data)
        self.assertEqual(data['data'], 'test')

    def test_write_to_directory_structure_no_data(self):
        path = 'all_modules/yang-catalog@2018-04-03.yang'
        result = self.client.put('api/admin/directory-structure/{}'.format(path), json={'input': {}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], '"data" must be specified')

    def test_write_to_directory_structure_not_found(self):
        path = 'nonexistent'
        result = self.client.put('api/admin/directory-structure/{}'.format(path), json={'input': {'data': 'test'}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'error - file does not exist')

    @mock.patch('os.walk')
    @mock.patch('os.lstat')
    @mock.patch.object(Path, 'glob')
    @mock.patch.object(Path, 'stat')
    def test_get_var_yang_directory_structure(self, mock_stat: mock.MagicMock, mock_glob: mock.MagicMock,
                                              mock_lstat: mock.MagicMock, mock_walk: mock.MagicMock):
        stat = mock.MagicMock()
        stat.st_size = 0
        stat.st_gid = 0
        stat.st_uid = 0
        stat.st_mtime = 0
        mock_stat.return_value = stat
        mock_glob.return_value = ()
        lstat = mock.MagicMock()
        lstat.st_mode = 0o777
        mock_lstat.return_value = lstat
        mock_walk.return_value = [('root', ('testdir',), ('test',))].__iter__()
        result = self.client.get('api/admin/directory-structure')

        structure = {
            'name': 'root',
            'files': [{
                'name': 'test',
                'size': 0,
                'group': 'root',
                'user': 'root',
                'permissions': '0o777',
                'modification': 0
            }],
            'folders': [{
                'name': 'testdir',
                'size': 0,
                'group': 'root',
                'user': 'root',
                'permissions': '0o777',
                'modification': 0
            }]
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

    # unfinished
    # redis is trowing an error for some reason
    @mock.patch('builtins.open')
    def test_update_yangcatalog_config(self, mock_open: mock.MagicMock):
        return
        mock.mock_open(mock_open)
        result = self.client.put('/api/admin/yangcatalog-config', json={'input': {'data': 'test'}})

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)

    @mock.patch('requests.post')
    @mock.patch.object(yc_gc.sender, 'send')
    @mock.patch.object(yc_gc, 'load_config')
    @mock.patch('builtins.open')
    def test_update_yangcatalog_config_errors(self, mock_open: mock.MagicMock, mock_load_config: mock.MagicMock,
                                              mock_send: mock.MagicMock, mock_post: mock.MagicMock):
        mock.mock_open(mock_open)
        mock_load_config.side_effect = Exception
        mock_send.side_effect = Exception
        mock_post.return_value.status_code = 404
        result = self.client.put('/api/admin/yangcatalog-config', json={'input': {'data': 'test'}})

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        info = {
            'api': 'error loading data',
            'receiver': 'error loading data',
            'yang-search': 'error loading data'
        }
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

    # this is my bane
    def test_get_logs(self):
        pass

    def test_get_sql_tables(self):
        result = self.client.get('api/admin/sql-tables')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertEqual(data, [
            {
                'name': 'users',
                'label': 'approved users'
            },
            {
                'name': 'users_temp',
                'label': 'users waiting for approval'
            }
        ])
    
    def test_move_user(self):
        pass

    def test_move_user_no_id(self):
        result = self.client.post('api/admin/move-user', json={'input': {}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Id of a user is missing')

    # skip db stuff for now

    @mock.patch.object(yc_gc.sqlalchemy.session, 'add')
    def test_create_sql_row(self, mock_add: mock.MagicMock):
        with open('{}/payloads.json'.format(self.resources_path), 'r') as f:
            content = json.load(f)
        body = content.get('create_sql_row')

        result = self.client.post('/api/admin/sql-tables/users_temp', json=body)

        self.assertEqual(result.status_code, 201)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'data successfully added to database')
        self.assertIn('data', data)
        self.assertEqual(data['data'], body['input'])
        # test for correct user object?

    @mock.patch.object(yc_gc.sqlalchemy.session, 'add')
    def test_create_sql_row_invalid_table(self, mock_add: mock.MagicMock):
        with open('{}/payloads.json'.format(self.resources_path), 'r') as f:
            content = json.load(f)
        body = content.get('create_sql_row')

        result = self.client.post('/api/admin/sql-tables/fake', json=body)

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'no such table fake, use only users or users_temp')

    @mock.patch.object(yc_gc.sqlalchemy.session, 'add')
    def test_create_sql_row_missing_access_rights(self, mock_add: mock.MagicMock):
        with open('{}/payloads.json'.format(self.resources_path), 'r') as f:
            content = json.load(f)
        body = content.get('create_sql_row')

        result = self.client.post('/api/admin/sql-tables/users', json=body)

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'access-rights-sdo OR access-rights-vendor must be specified')

    @mock.patch.object(yc_gc.sqlalchemy.session, 'delete')
    def test_delete_sql_row(self, mock_delete: mock.MagicMock):
        mock_delete.side_effect = yc_gc.sqlalchemy.session.expunge
        result = self.client.delete('/api/admin/sql-tables/users/id/1')

        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'id 1 deleted successfully')
        self.assertTrue(len(mock_delete.call_args.args))
        user = mock_delete.call_args.args[0]
        self.assertTrue(isinstance(user, User))
        self.assertEqual(user.Id, 1)

    @mock.patch.object(yc_gc.sqlalchemy.session, 'delete')
    def test_delete_sql_row_invalid_table(self, mock_delete: mock.MagicMock):
        result = self.client.delete('/api/admin/sql-tables/fake/id/1')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'no such table fake, use only users or users_temp')

    @mock.patch.object(yc_gc.sqlalchemy.session, 'delete')
    def test_delete_sql_row_id_not_found(self, mock_delete: mock.MagicMock):
        result = self.client.delete('/api/admin/sql-tables/users/id/24857629847625894258476')

        self.assertEqual(result.status_code, 404)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'id 24857629847625894258476 not found in table users')

    def test_update_sql_row_invalid_table(self):
        result = self.client.put('/api/admin/sql-tables/fake/id/24857629847625894258476')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'no such table fake, use only users or users_temp')
    
    @mock.patch.object(yc_gc.sqlalchemy.session, 'commit', new=mock.MagicMock())
    def test_update_sql_row_args_missing(self):
        result = self.client.put('/api/admin/sql-tables/users/id/1', json={'input': {}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'username and email must be specified')

    def test_get_script_details_invalid_name(self):
        result = self.client.get('/api/admin/scripts/invalid')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], '"invalid" is not valid script name')

    @mock.patch('api.globalConfig.yc_gc.sender.send')
    def test_run_script_with_args(self, mock_send: mock.MagicMock):
        mock_send.return_value = 1
        result = self.client.post('/api/admin/scripts/populate', json={'input': 'test'})

        self.assertEqual(result.status_code, 202)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('info', data)
        self.assertEqual(data['info'], 'Verification successful')
        self.assertIn('job-id', data)
        self.assertEqual(data['job-id'], 1)
        self.assertIn('arguments', data)
        self.assertEqual(data['arguments'], ['parseAndPopulate', 'populate', '"test"'])

    @mock.patch('api.globalConfig.yc_gc.sender', mock.MagicMock())
    def test_run_script_with_args_invalid_name(self):
        result = self.client.post('/api/admin/scripts/invalid')

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], '"invalid" is not valid script name')

    @mock.patch('api.globalConfig.yc_gc.sender', mock.MagicMock())
    def test_run_script_with_args_empty(self):
        result = self.client.post('/api/admin/scripts/validate', json={'input': {'row_id': '', 'user_email': ''}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Failed to validate - user-email and row-id cannot be empty strings')

    @mock.patch('api.globalConfig.yc_gc.sender', mock.MagicMock())
    def test_run_script_with_args_missing(self):
        result = self.client.post('/api/admin/scripts/validate', json={'input': {}})

        self.assertEqual(result.status_code, 400)
        self.assertTrue(result.is_json)
        data = result.json
        self.assertIn('description', data)
        self.assertEqual(data['description'], 'Failed to validate - user-email and row-id must exist')
