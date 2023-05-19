# # Copyright The IETF Trust 2021, All Rights Reserved
# #
# # Licensed under the Apache License, Version 2.0 (the "License");
# # you may not use this file except in compliance with the License.
# # You may obtain a copy of the License at
# #
# #     http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS,
# # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # See the License for the specific language governing permissions and
# # limitations under the License.
#
# __author__ = 'Slavomir Mazur'
# __copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
# __license__ = 'Apache License, Version 2.0'
# __email__ = 'slavomir.mazur@pantheon.tech'
#
# import json
# import os
# import shutil
# import unittest
# from unittest import mock
#
# from ddt import data, ddt
# from redis import Redis
#
# from jobs import JobRunner
# from api.status_message import StatusMessage
# from redisConnections.redisConnection import RedisConnection
# from utility.create_config import create_config
#
#
# class MockModulesComplicatedAlgorithms:
#     def __init__(
#         self,
#         log_directory: str,
#         yangcatalog_api_prefix: str,
#         credentials: list,
#         save_file_dir: str,
#         direc: str,
#         all_modules,
#         yang_models_dir: str,
#         temp_dir: str,
#         json_ytree: str,
#     ):
#         pass
#
#     def parse_non_requests(self):
#         pass
#
#     def parse_requests(self):
#         pass
#
#     def populate(self):
#         pass
#
#
# class MockConfdService:
#     def patch_modules(self, new_data: str):
#         r = mock.MagicMock()
#         r.status_code = 201
#         return r
#
#     def patch_vendors(self, new_data: str):
#         r = mock.MagicMock()
#         r.status_code = 201
#         return r
#
#     def delete_dependent(self, module_key: str, dependent: str):
#         r = mock.MagicMock()
#         r.status_code = 204
#         return r
#
#     def delete_module(self, module_key: str):
#         r = mock.MagicMock()
#         r.status_code = 204
#         return r
#
#     def delete_vendor(self, confd_suffix: str):
#         r = mock.MagicMock()
#         r.status_code = 204
#         return r
#
#     def delete_implementation(self, module_key: str, implementation_key: str):
#         r = mock.MagicMock()
#         r.status_code = 204
#         return r
#
#
# class MockRepoUtil:
#     localdir = 'test'
#
#     def __init__(self, repourl, logger=None):
#         pass
#
#     def clone(self):
#         pass
#
#     def get_commit_hash(self, path=None, branch='master'):
#         return branch
#
#     def remove(self):
#         pass
#
#
# class TestJobRunnerBaseClass(unittest.TestCase):
#     job_runner: JobRunner
#     redis_connection: RedisConnection
#     directory: str
#     test_data: dict
#
#     @classmethod
#     def setUpClass(cls):
#         config = create_config()
#         cls.log_directory = config.get('Directory-Section', 'logs')
#         temp_dir = config.get('Directory-Section', 'temp')
#         cls.credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
#         cls.nonietf_dir = config.get('Directory-Section', 'non-ietf-directory')
#         yang_models = config.get('Directory-Section', 'yang-models-dir')
#         _redis_host = config.get('DB-Section', 'redis-host')
#         _redis_port = int(config.get('DB-Section', 'redis-port'))
#
#         cls.redis_connection = RedisConnection(modules_db=6, vendors_db=9)
#         cls.job_runner = JobRunner()
#         cls.job_runner.redis_connection = cls.redis_connection
#         cls.modulesDB = Redis(host=_redis_host, port=_redis_port, db=6)
#         cls.vendorsDB = Redis(host=_redis_host, port=_redis_port, db=9)
#         cls.huawei_dir = f'{yang_models}/vendor/huawei/network-router/8.20.0/ne5000e'
#         cls.directory = f'{temp_dir}/job_runner_test'
#         resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
#         cls.private_dir = os.path.join(resources_path, 'html/private')
#
#         with open(os.path.join(resources_path, 'job_runner_tests_data.json'), 'r') as f:
#             cls.test_data = json.load(f)
#
#         redis_modules_patcher = mock.patch('redisConnections.redisConnection.RedisConnection')
#         cls.mock_redis_modules = redis_modules_patcher.start()
#         cls.addClassCleanup(redis_modules_patcher.stop)
#         cls.mock_redis_modules.return_value = cls.redis_connection
#
#         confd_patcher = mock.patch('utility.confdService.ConfdService')
#         cls.mock_confd_service = confd_patcher.start()
#         cls.addClassCleanup(confd_patcher.stop)
#         cls.mock_confd_service.side_effect = MockConfdService
#
#     def tearDown(self):
#         self.modulesDB.flushdb()
#         self.vendorsDB.flushdb()
#
#
# class TestJobRunnerClass(TestJobRunnerBaseClass):
#     def setUp(self):
#         super().setUp()
#         os.makedirs(self.directory, exist_ok=True)
#
#     def tearDown(self):
#         super().tearDown()
#         if os.path.exists(self.directory):
#             shutil.rmtree(self.directory)
#
#     @mock.patch('api.views.user_specific_module_maintenance.repoutil.RepoUtil', MockRepoUtil)
#     @mock.patch('parseAndPopulate.populate.ModulesComplicatedAlgorithms', MockModulesComplicatedAlgorithms)
#     @mock.patch('parseAndPopulate.populate.Populate._reload_cache_in_parallel', mock.MagicMock)
#     @mock.patch('utility.message_factory.MessageFactory', mock.MagicMock)
#     def test_process_sdo(self):
#         data = self.test_data.get('request-data-content')
#         dst = os.path.join(self.directory, 'YangModels', 'yang', 'standard', 'ietf', 'RFC')
#         os.makedirs(dst, exist_ok=True)
#
#         rfc_dir = os.path.join(self.nonietf_dir, 'yangmodels', 'yang', 'standard', 'ietf', 'RFC')
#         shutil.copy(
#             os.path.join(rfc_dir, 'ietf-yang-types@2010-09-24.yang'),
#             os.path.join(dst, 'ietf-yang-types@2010-09-24.yang'),
#         )
#         with open(os.path.join(self.directory, 'request-data.json'), 'w') as f:
#             json.dump(data, f)
#
#         status = self.job_runner.process(self.directory, sdo=True, api=True)
#         redis_module = self.modulesDB.get('ietf-yang-types@2010-09-24/ietf')
#         redis_data = (redis_module or b'{}').decode('utf-8')
#
#         self.assertEqual(status, StatusMessage.SUCCESS)
#         self.assertNotEqual(redis_data, '{}')
#
#     @mock.patch('utility.message_factory.MessageFactory', mock.MagicMock)
#     def test_process_sdo_failed_populate(self):
#         status = self.job_runner.process(self.directory, sdo=True, api=True)
#         redis_module = self.modulesDB.get('openconfig-extensions@2020-06-16/openconfig')
#         redis_data = (redis_module or b'{}').decode('utf-8')
#
#         self.assertEqual(status, StatusMessage.FAIL)
#         self.assertEqual(redis_data, '{}')
#
#     @mock.patch('api.views.user_specific_module_maintenance.repoutil.RepoUtil', MockRepoUtil)
#     @mock.patch('parseAndPopulate.populate.ModulesComplicatedAlgorithms', MockModulesComplicatedAlgorithms)
#     @mock.patch('parseAndPopulate.populate.Populate._reload_cache_in_parallel', mock.MagicMock)
#     @mock.patch('utility.message_factory.MessageFactory', mock.MagicMock)
#     def test_process_vendor(self):
#         platform = self.test_data.get('capabilities-json-content')
#
#         dst = os.path.join(self.directory, 'huawei', 'yang', 'network-router', '8.20.0', 'ne5000e')
#         os.makedirs(dst, exist_ok=True)
#
#         shutil.copy(
#             os.path.join(self.huawei_dir, 'huawei-dsa.yang'),
#             os.path.join(dst, 'huawei-dsa.yang'),
#         )
#         shutil.copy(
#             os.path.join(self.huawei_dir, 'capabilities.xml'),
#             os.path.join(dst, 'capabilities.xml'),
#         )
#         with open(os.path.join(dst, 'capabilities.json'), 'w') as f:
#             json.dump(platform, f)
#
#         status = self.job_runner.process(self.directory, sdo=False, api=True)
#
#         self.assertEqual(status, StatusMessage.SUCCESS)
#
#     @mock.patch('api.job_runner.prepare_for_es_removal', mock.MagicMock)
#     def test_process_module_deletion(self):
#         module_to_populate = self.test_data['module-deletion-tests']
#         self.redis_connection.populate_modules(module_to_populate)
#         self.redis_connection.reload_modules_cache()
#
#         modules_to_delete = [{'name': 'another-yang-module', 'revision': '2020-03-01', 'organization': 'ietf'}]
#         deleted_module_key = 'another-yang-module@2020-03-01/ietf'
#         status = self.job_runner.process_module_deletion(modules_to_delete)
#         self.redis_connection.reload_modules_cache()
#         raw_all_modules = self.redis_connection.get_all_modules()
#         all_modules = json.loads(raw_all_modules)
#
#         self.assertEqual(status, StatusMessage.SUCCESS)
#         self.assertNotIn(deleted_module_key, all_modules)
#         for module in all_modules.values():
#             dependents_list = [f'{dep["name"]}@{dep.get("revision")}' for dep in module.get('dependents', [])]
#             self.assertNotIn('another-yang-module@2020-03-01', dependents_list)
#
#     @mock.patch('api.job_runner.prepare_for_es_removal', mock.MagicMock)
#     def test_process_module_deletion_cannot_delete(self):
#         module_to_populate = self.test_data['module-deletion-tests']
#         self.redis_connection.populate_modules(module_to_populate)
#         self.redis_connection.reload_modules_cache()
#
#         modules_to_delete = [{'name': 'yang-submodule', 'revision': '2020-02-01', 'organization': 'ietf'}]
#         deleted_module_key = 'yang-submodule@2020-02-01/ietf'
#         status = self.job_runner.process_module_deletion(modules_to_delete)
#         self.redis_connection.reload_modules_cache()
#         raw_all_modules = self.redis_connection.get_all_modules()
#         all_modules = json.loads(raw_all_modules)
#
#         self.assertEqual(status, StatusMessage.IN_PROGRESS)
#         self.assertIn(deleted_module_key, all_modules)
#
#     @mock.patch('api.job_runner.prepare_for_es_removal', mock.MagicMock)
#     def test_process_module_deletion_module_and_its_dependent(self):
#         module_to_populate = self.test_data['module-deletion-tests']
#         self.redis_connection.populate_modules(module_to_populate)
#         self.redis_connection.reload_modules_cache()
#
#         modules_to_delete = [
#             {'name': 'another-yang-module', 'revision': '2020-03-01', 'organization': 'ietf'},
#             {'name': 'yang-module', 'revision': '2020-01-01', 'organization': 'ietf'},
#         ]
#
#         status = self.job_runner.process_module_deletion(modules_to_delete)
#         self.redis_connection.reload_modules_cache()
#         raw_all_modules = self.redis_connection.get_all_modules()
#         all_modules = json.loads(raw_all_modules)
#
#         self.assertEqual(status, StatusMessage.SUCCESS)
#         self.assertNotIn('another-yang-module@2020-03-01/ietf', all_modules)
#         self.assertNotIn('yang-module@2020-01-01/ietf', all_modules)
#
#         for module in all_modules.values():
#             dependents_list = [f'{dep["name"]}@{dep.get("revision")}' for dep in module.get('dependents', [])]
#             self.assertNotIn('another-yang-module@2020-03-01', dependents_list)
#             self.assertNotIn('yang-module@2020-01-01/ietf', dependents_list)
#
#     @mock.patch('api.job_runner.prepare_for_es_removal', mock.MagicMock)
#     def test_process_module_deletion_empty_list_input(self):
#         module_to_populate = self.test_data['module-deletion-tests']
#         self.redis_connection.populate_modules(module_to_populate)
#         self.redis_connection.reload_modules_cache()
#
#         status = self.job_runner.process_module_deletion([])
#
#         self.assertEqual(status, StatusMessage.SUCCESS)
#
#
# @ddt
# class TestJobRunnerVendorsDeletionClass(TestJobRunnerBaseClass):
#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#         cls.vendors_to_populate = cls.test_data['vendor-deletion-tests']['vendors']
#         cls.modules_to_populate = cls.test_data['vendor-deletion-tests']['modules']
#
#     def setUp(self):
#         super().setUp()
#         self.redis_connection.populate_implementation([self.vendors_to_populate])
#         self.redis_connection.populate_modules(self.modules_to_populate)
#         self.redis_connection.reload_vendors_cache()
#         self.redis_connection.reload_modules_cache()
#
#     @data(
#         ('fujitsu', 'T100', '2.4', 'Linux'),
#         ('fujitsu', 'T100', '2.4', None),
#         ('fujitsu', 'T100', None, None),
#         ('fujitsu', None, None, None),
#         ('huawei', 'ne5000e', None, None),
#     )
#     @mock.patch('api.job_runner.prepare_for_es_removal')
#     def test_process_vendor_deletion(self, param_tuple, indexing_mock: mock.MagicMock):
#         indexing_mock.return_value = {}
#         vendor, platform, software_version, software_flavor = param_tuple
#         params = {
#             'vendor': vendor,
#             'platform': platform,
#             'software-version': software_version,
#             'software-flavor': software_flavor,
#         }
#
#         deleted_vendor_branch = ''
#         if vendor:
#             deleted_vendor_branch += f'{vendor}/'
#         if platform:
#             deleted_vendor_branch += f'{platform}/'
#         if software_version:
#             deleted_vendor_branch += f'{software_version}/'
#         if software_flavor:
#             deleted_vendor_branch += software_flavor
#
#         status = self.job_runner.process_vendor_deletion(params)
#         self.redis_connection.reload_vendors_cache()
#         self.redis_connection.reload_modules_cache()
#
#         created_vendors_dict = self.redis_connection.create_vendors_data_dict(deleted_vendor_branch)
#         self.assertEqual(status, StatusMessage.SUCCESS)
#         self.assertEqual(created_vendors_dict, [])
#         for key in self.vendorsDB.scan_iter():
#             redis_key = key.decode('utf-8')
#             self.assertNotIn(deleted_vendor_branch, redis_key)
#
#         raw_all_modules = self.redis_connection.get_all_modules()
#         all_modules = json.loads(raw_all_modules)
#         for module in all_modules.values():
#             implementations = module.get('implementations', {}).get('implementation', [])
#             for implementation in implementations:
#                 implementation_key = self.redis_connection.create_implementation_key(implementation)
#                 self.assertNotIn(deleted_vendor_branch, implementation_key)
#
#
# if __name__ == '__main__':
#     unittest.main()
