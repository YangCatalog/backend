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

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

import json
import os
import shutil
import unittest
from unittest import mock

from api.receiver import Receiver
from ddt import data, ddt
from parseAndPopulate.loadJsonFiles import LoadFiles
from redis import Redis
from redisConnections.redisConnection import RedisConnection
from utility.create_config import create_config


class MockConfdService:
    def patch_modules(self, new_data: str):
        r = mock.MagicMock()
        r.status_code = 201
        return r

    def patch_vendors(self, new_data: str):
        r = mock.MagicMock()
        r.status_code = 201
        return r

    def delete_dependent(self, module_key: str, dependent: str):
        r = mock.MagicMock()
        r.status_code = 204
        return r

    def delete_module(self, module_key: str):
        r = mock.MagicMock()
        r.status_code = 204
        return r

    def delete_vendor(self, confd_suffix: str):
        r = mock.MagicMock()
        r.status_code = 204
        return r

    def delete_implementation(self, module_key: str, implementation_key: str):
        r = mock.MagicMock()
        r.status_code = 204
        return r


class MockRepoUtil:
    localdir = 'test'

    def __init__(self, repourl, logger=None):
        pass

    def clone(self):
        pass

    def get_commit_hash(self, path=None, branch='master'):
        return branch

    def remove(self):
        pass


class TestReceiverBaseClass(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestReceiverBaseClass, self).__init__(*args, **kwargs)
        config = create_config()

        self.log_directory = config.get('Directory-Section', 'logs')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.private_dir = 'tests/resources/html/private'
        self.credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
        self.nonietf_dir = config.get('Directory-Section', 'non-ietf-directory')
        self.yang_models = config.get('Directory-Section', 'yang-models-dir')
        self.__redis_host = config.get('DB-Section', 'redis-host')
        self.__redis_port = config.get('DB-Section', 'redis-port')

        self.receiver = Receiver(os.environ['YANGCATALOG_CONFIG_PATH'])
        self.receiver.redisConnection = RedisConnection(modules_db=11, vendors_db=14)
        self.redisConnection = RedisConnection(modules_db=11, vendors_db=14)
        self.receiver.confdService = MockConfdService()
        self.modulesDB = Redis(host=self.__redis_host, port=self.__redis_port, db=11)
        self.vendorsDB = Redis(host=self.__redis_host, port=self.__redis_port, db=14)
        self.huawei_dir = '{}/vendor/huawei/network-router/8.20.0/ne5000e'.format(self.yang_models)
        self.direc = '{}/receiver_test'.format(self.temp_dir)
        self.resources_path = '{}/resources'.format(os.path.dirname(os.path.abspath(__file__)))

        with open('{}/receiver_tests_data.json'.format(self.resources_path), 'r') as f:
            self.test_data = json.load(f)

    def setUp(self):
        self.redis_modules_patcher = mock.patch('redisConnections.redisConnection.RedisConnection')
        self.mock_redis_modules = self.redis_modules_patcher.start()
        self.addCleanup(self.redis_modules_patcher.stop)
        self.mock_redis_modules.return_value = RedisConnection(modules_db=11, vendors_db=14)

        self.confd_patcher = mock.patch('utility.confdService.ConfdService')
        self.mock_confd_service = self.confd_patcher.start()
        self.addCleanup(self.confd_patcher.stop)
        self.mock_confd_service.side_effect = MockConfdService

    def tearDown(self):
        self.modulesDB.flushdb()
        self.vendorsDB.flushdb()


class TestReceiverClass(TestReceiverBaseClass):
    def setUp(self):
        super(TestReceiverClass, self).setUp()
        os.makedirs(self.direc, exist_ok=True)

    def tearDown(self):
        super(TestReceiverClass, self).tearDown()
        shutil.rmtree(self.direc)

    def test_run_ping_successful(self):
        response = self.receiver.run_ping('ping')

        self.assertEqual(response, 'Finished successfully')

    def test_run_ping_failure(self):
        response = self.receiver.run_ping('pong')

        self.assertEqual(response, 'Failed')

    @ mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.repoutil.RepoUtil', MockRepoUtil)
    @ mock.patch('parseAndPopulate.capability.LoadFiles')
    def test_process_sdo(self, mock_load_files: mock.MagicMock):
        mock_load_files.return_value = LoadFiles(self.private_dir, self.log_directory)
        data = self.test_data.get('prepare-sdo-content')
        dst = '{}/temp/YangModels/yang/master/standard/ietf/RFC'.format(self.direc)
        os.makedirs(dst, exist_ok=True)

        RFC_dir = '{}/yangmodels/yang/standard/ietf/RFC'.format(self.nonietf_dir)
        shutil.copy('{}/ietf-yang-types@2010-09-24.yang'.format(RFC_dir),
                    '{}/ietf-yang-types@2010-09-24.yang'.format(dst))
        with open('{}/prepare-sdo.json'.format(self.direc), 'w') as f:
            json.dump(data, f)

        arguments = ['POPULATE-MODULES', '--sdo', '--dir', self.direc, '--api',
                     '--credentials', *self.credentials, 'True']

        response, all_modules = self.receiver.process(arguments)
        module = all_modules['module'][0]
        original_module_data = data['modules']['module'][0]
        redis_module = self.modulesDB.get('ietf-yang-types@2010-09-24/ietf')
        redis_data = (redis_module or b'{}').decode('utf-8')

        self.assertEqual(response, 'Finished successfully')
        self.assertNotEqual(redis_data, '{}')
        self.assertNotEqual(all_modules, {})
        self.assertIn('module', all_modules)
        for prop in ['name', 'revision', 'organization', 'module-classification', 'generated-from']:
            self.assertEqual(module[prop], original_module_data[prop])

    @ mock.patch('parseAndPopulate.capability.LoadFiles')
    def test_process_sdo_failed_populate(self, mock_load_files: mock.MagicMock):
        mock_load_files.side_effect = Exception
        arguments = ['POPULATE-MODULES', '--sdo', '--dir', self.direc,
                     '--api', '--credentials', *self.credentials, 'True']

        response, all_modules = self.receiver.process(arguments)
        redis_module = self.modulesDB.get('openconfig-extensions@2020-06-16/openconfig')
        redis_data = (redis_module or b'{}').decode('utf-8')

        self.assertEqual(response, 'Failed#split#Server error while running populate script')
        self.assertEqual(redis_data, '{}')
        self.assertEqual(all_modules, {})

    @ mock.patch('api.views.userSpecificModuleMaintenance.moduleMaintenance.repoutil.RepoUtil', MockRepoUtil)
    @ mock.patch('parseAndPopulate.capability.LoadFiles')
    def test_process_vendor(self, mock_load_files: mock.MagicMock):
        mock_load_files.return_value = LoadFiles(self.private_dir, self.log_directory)
        platform = self.test_data.get('capabilities-json-content')

        dst = '{}/temp/huawei/yang/master/network-router/8.20.0/ne5000e'.format(self.direc)
        os.makedirs(dst, exist_ok=True)

        shutil.copy('{}/huawei-dsa.yang'.format(self.huawei_dir), '{}/huawei-dsa.yang'.format(dst))
        shutil.copy('{}/capabilities.xml'.format(self.huawei_dir), '{}/capabilities.xml'.format(dst))
        with open('{}/capabilities.json'.format(dst), 'w') as f:
            json.dump(platform, f)

        arguments = ['POPULATE-VENDORS', '--dir', self.direc, '--api',
                     '--credentials', *self.credentials, 'True']

        response, all_modules = self.receiver.process(arguments)
        modules = all_modules.get('module')

        self.assertEqual(response, 'Finished successfully')
        self.assertNotEqual(all_modules, {})
        self.assertIn('module', all_modules)

        for module in modules:
            self.assertIn('implementations', module)
            implementations = module.get('implementations', {})
            self.assertIn('implementation', implementations)
            for implementation in implementations.get('implementation'):
                for prop in ['vendor', 'software-version', 'software-flavor']:
                    self.assertEqual(implementation.get(prop), platform.get(prop))
                self.assertEqual(implementation.get('platform'), platform.get('name'))

            # Test whether modules are stored in Redis database after running populate script
            redis_key = '{}@{}/{}'.format(module.get('name'), module.get('revision'), module.get('organization'))
            redis_module = self.modulesDB.get(redis_key)
            redis_data = (redis_module or b'{}').decode('utf-8')
            self.assertNotEqual(redis_data, '{}')

    @ mock.patch('parseAndPopulate.capability.LoadFiles')
    def test_process_vendor_failed_populate(self, mock_load_files: mock.MagicMock):
        mock_load_files.side_effect = Exception
        arguments = ['POPULATE-VENDORS', '--dir', self.direc, '--api',
                     '--credentials', *self.credentials, 'True']

        response, all_modules = self.receiver.process(arguments)

        self.assertEqual(response, 'Failed#split#Server error while running populate script')
        self.assertEqual(all_modules, {})

    @ mock.patch('api.receiver.prepare_to_indexing', mock.MagicMock)
    def test_process_module_deletion(self):
        module_to_populate = self.test_data.get('module-deletion-tests')
        redisConnection = RedisConnection(modules_db=11)
        redisConnection.populate_modules(module_to_populate)
        redisConnection.reload_modules_cache()

        modules_to_delete = {
            'modules': [
                {
                    'name': 'another-yang-module',
                    'revision': '2020-03-01',
                    'organization': 'ietf'
                }
            ]}
        deleted_module_key = 'another-yang-module@2020-03-01/ietf'
        arguments = ['DELETE-MODULES', *self.credentials, json.dumps(modules_to_delete)]
        response = self.receiver.process_module_deletion(arguments)
        redisConnection.reload_modules_cache()
        raw_all_modules = redisConnection.get_all_modules()
        all_modules = json.loads(raw_all_modules)

        self.assertEqual(response, 'Finished successfully')
        self.assertNotIn(deleted_module_key, all_modules)
        for module in all_modules.values():
            dependents_list = ['{}@{}'.format(dep['name'], dep.get('revision')) for dep in module.get('dependents', [])]
            self.assertNotIn('another-yang-module@2020-03-01', dependents_list)

    @ mock.patch('api.receiver.prepare_to_indexing', mock.MagicMock)
    def test_process_module_deletion_cannot_delete(self):
        module_to_populate = self.test_data.get('module-deletion-tests')
        redisConnection = RedisConnection(modules_db=11)
        redisConnection.populate_modules(module_to_populate)
        redisConnection.reload_modules_cache()

        modules_to_delete = {
            'modules': [
                {
                    'name': 'yang-submodule',
                    'revision': '2020-02-01',
                    'organization': 'ietf'
                }
            ]}
        deleted_module_key = 'yang-submodule@2020-02-01/ietf'
        arguments = ['DELETE-MODULES', *self.credentials, json.dumps(modules_to_delete)]
        response = self.receiver.process_module_deletion(arguments)
        redisConnection.reload_modules_cache()
        raw_all_modules = redisConnection.get_all_modules()
        all_modules = json.loads(raw_all_modules)

        self.assertEqual(response, 'Partially done#split#modules-not-deleted:yang-submodule,2020-02-01,ietf')
        self.assertIn(deleted_module_key, all_modules)

    @ mock.patch('api.receiver.prepare_to_indexing', mock.MagicMock)
    def test_process_module_deletion_module_and_its_dependent(self):
        module_to_populate = self.test_data.get('module-deletion-tests')
        redisConnection = RedisConnection(modules_db=11)
        redisConnection.populate_modules(module_to_populate)
        redisConnection.reload_modules_cache()

        modules_to_delete = {
            'modules': [
                {
                    'name': 'another-yang-module',
                    'revision': '2020-03-01',
                    'organization': 'ietf'
                },
                {
                    'name': 'yang-module',
                    'revision': '2020-01-01',
                    'organization': 'ietf'
                }
            ]}

        arguments = ['DELETE-MODULES', *self.credentials, json.dumps(modules_to_delete)]
        response = self.receiver.process_module_deletion(arguments)
        redisConnection.reload_modules_cache()
        raw_all_modules = redisConnection.get_all_modules()
        all_modules = json.loads(raw_all_modules)

        self.assertEqual(response, 'Finished successfully')
        self.assertNotIn('another-yang-module@2020-03-01/ietf', all_modules)
        self.assertNotIn('yang-module@2020-01-01/ietf', all_modules)

        for module in all_modules.values():
            dependents_list = ['{}@{}'.format(dep['name'], dep.get('revision')) for dep in module.get('dependents', [])]
            self.assertNotIn('another-yang-module@2020-03-01', dependents_list)
            self.assertNotIn('yang-module@2020-01-01/ietf', dependents_list)

    @ mock.patch('api.receiver.prepare_to_indexing', mock.MagicMock)
    def test_process_module_deletion_empty_list_input(self):
        module_to_populate = self.test_data.get('module-deletion-tests')
        redisConnection = RedisConnection(modules_db=11)
        redisConnection.populate_modules(module_to_populate)
        redisConnection.reload_modules_cache()

        arguments = ['DELETE-MODULES', *self.credentials, json.dumps({'modules': []})]
        response = self.receiver.process_module_deletion(arguments)

        self.assertEqual(response, 'Finished successfully')

    @ mock.patch('api.receiver.prepare_to_indexing', mock.MagicMock)
    def test_process_module_deletion_incorrect_arguments_input(self):
        module_to_populate = self.test_data.get('module-deletion-tests')
        redisConnection = RedisConnection(modules_db=11)
        redisConnection.populate_modules(module_to_populate)
        redisConnection.reload_modules_cache()

        arguments = ['DELETE-MODULES', *self.credentials, json.dumps([])]
        response = self.receiver.process_module_deletion(arguments)

        self.assertEqual(response, 'Failed#split#Server error -> Unable to parse arguments')


@ddt
class TestReceiverVendorsDeletionClass(TestReceiverBaseClass):
    def setUp(self):
        super(TestReceiverVendorsDeletionClass, self).setUp()
        vendors_to_populate = self.test_data.get('vendor-deletion-tests').get('vendors')
        modules_to_populate = self.test_data.get('vendor-deletion-tests').get('modules')
        self.redisConnection.populate_implementation([vendors_to_populate])
        self.redisConnection.populate_modules(modules_to_populate)
        self.redisConnection.reload_vendors_cache()
        self.redisConnection.reload_modules_cache()

    @data(
        ('fujitsu', 'T100', '2.4', 'Linux'),
        ('fujitsu', 'T100', '2.4', 'None'),
        ('fujitsu', 'T100', 'None', 'None'),
        ('fujitsu', 'None', 'None', 'None'),
        ('huawei', 'ne5000e', 'None', 'None')
    )
    @ mock.patch('api.receiver.prepare_to_indexing')
    def test_process_vendor_deletion(self, params, indexing_mock: mock.MagicMock):
        indexing_mock.return_value = {}
        vendor, platform, software_version, software_flavor = params

        confd_suffix = ''
        deleted_vendor_branch = ''
        if vendor != 'None':
            confd_suffix += 'vendors/vendor/{}'.format(vendor)
            deleted_vendor_branch += '{}/'.format(vendor)
        if platform != 'None':
            confd_suffix += '/platforms/platform/{}'.format(platform)
            deleted_vendor_branch += '{}/'.format(platform)
        if software_version != 'None':
            confd_suffix += '/software-versions/software-version/{}'.format(software_version)
            deleted_vendor_branch += '{}/'.format(software_version)
        if software_flavor != 'None':
            confd_suffix += '/software-flavors/software-flavor/{}'.format(software_flavor)
            deleted_vendor_branch += software_flavor

        arguments = ['DELETE-VENDORS', *self.credentials, vendor, platform, software_version, software_flavor, confd_suffix]
        response = self.receiver.process_vendor_deletion(arguments)
        self.redisConnection.reload_vendors_cache()
        self.redisConnection.reload_modules_cache()

        created_vendors_dict = self.redisConnection.create_vendors_data_dict(deleted_vendor_branch)
        self.assertEqual(response, 'Finished successfully')
        self.assertEqual(created_vendors_dict, [])
        for key in self.vendorsDB.scan_iter():
            redis_key = key.decode('utf-8')
            self.assertNotIn(deleted_vendor_branch, redis_key)

        raw_all_modules = self.redisConnection.get_all_modules()
        all_modules = json.loads(raw_all_modules)
        for module in all_modules.values():
            implementations = module.get('implementations', {}).get('implementation', [])
            for implementation in implementations:
                implementation_key = self.redisConnection.create_implementation_key(implementation)
                self.assertNotIn(deleted_vendor_branch, implementation_key)


if __name__ == '__main__':
    unittest.main()
