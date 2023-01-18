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
import time
import unittest
from unittest import mock

import utility.util as util
from api.globalConfig import yc_gc
from parseAndPopulate.models.schema_parts import SchemaParts
from sandbox import constants as sandbox_constants
from sandbox import generate_schema_urls
from utility.create_config import create_config
from utility.staticVariables import JobLogStatuses


class TestUtilClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        generate_schema_urls.main(os.environ['TEST_REPO'])
        cls.filename = os.path.basename(__file__).split('.py')[0]
        cls.job_log_properties = ['start', 'end', 'status', 'error', 'messages', 'last_successfull']
        cls.resources_path = os.path.join(os.environ['BACKEND'], 'utility/tests/resources')
        cls.util_tests_dir = os.path.join(yc_gc.temp_dir, 'util-tests')
        cls.cronjob_file_path = os.path.join(yc_gc.temp_dir, 'cronjob.json')

    @classmethod
    def tearDownClass(cls):
        modules_paths_to_remove_file_path = os.path.join(
            create_config().get('Directory-Section', 'cache'),
            sandbox_constants.NEW_COPIED_MODULES_PATHS_FILENAME,
        )
        with open(modules_paths_to_remove_file_path, 'r') as f:
            modules_paths_to_remove = json.load(f)
        for module_path in modules_paths_to_remove:
            if not os.path.exists(module_path):
                continue
            os.remove(module_path)

    def test_create_signature(self):
        """Test the result of the method with the given arguments."""
        secret_key = 'S3cr3t_k3y'
        string_to_sign = 'test'

        result = util.create_signature(secret_key, string_to_sign)
        self.assertEqual(result, '33f57bcec731bb8f9ddf964bd1910e657ace0a64')

    def test_create_signature_empty_arguments(self):
        """Test the result of the method with the given arguments."""
        result = util.create_signature('', '')
        self.assertEqual(result, 'fbdb1d1b18aa6c08324b7d64b71fb76370690e1d')

    def test_job_log_success(self):
        """Test if job run information was correctly dumped into cronjob.json file if status is Success.
        Check if structure is correct.
        """
        start_time = int(time.time())
        util.write_job_log(start_time, yc_gc.temp_dir, status=JobLogStatuses.SUCCESS, filename=self.filename)
        cronjob_data = self.load_cronjob_data()

        job_log = cronjob_data.get(self.filename, {})

        self.assertNotEqual(cronjob_data, {})
        self.assertIn(self.filename, cronjob_data)
        self.assertEqual('Success', job_log['status'])
        for prop in self.job_log_properties:
            self.assertIn(prop, job_log)

        self.clear_job_log()

    def test_job_log_fail(self):
        """Test if job run information was correctly dumped into cronjob.json file if status is Fail.
        Check if structure is correct.
        """
        start_time = int(time.time())
        util.write_job_log(
            start_time,
            yc_gc.temp_dir,
            error='Error occured',
            status=JobLogStatuses.FAIL,
            filename=self.filename,
        )

        cronjob_data = self.load_cronjob_data()
        job_log = cronjob_data.get(self.filename, {})

        self.assertNotEqual(cronjob_data, {})
        self.assertIn(self.filename, cronjob_data)
        self.assertEqual('Fail', job_log['status'])
        for prop in self.job_log_properties:
            self.assertIn(prop, job_log)

        self.clear_job_log()

    def test_job_log_messages(self):
        """
        Test if job run information was correctly dumped into cronjob.json file if there are some additional messages.
        Check if structure is correct.
        """
        start_time = int(time.time())
        messages = [{'label': 'Message label', 'message': 'Message text'}]
        util.write_job_log(
            start_time,
            yc_gc.temp_dir,
            messages=messages,
            status=JobLogStatuses.SUCCESS,
            filename=self.filename,
        )

        cronjob_data = self.load_cronjob_data()
        job_log = cronjob_data.get(self.filename, {})
        job_log_messages = job_log['messages']

        self.assertNotEqual(cronjob_data, {})
        self.assertIn(self.filename, cronjob_data)
        self.assertEqual('Success', job_log['status'])
        self.assertNotEqual(len(job_log_messages), 0)
        for prop in self.job_log_properties:
            self.assertIn(prop, job_log)

        for message in job_log_messages:
            self.assertIn('label', message)
            self.assertIn('message', message)

        self.clear_job_log()

    def test_fetch_module_by_schema_successfully(self):
        """Test if content of yang module was successfully fetched from Github and stored to the file."""
        schema_parts = SchemaParts(
            repo_owner='YangModels',
            repo_name='yang',
            commit_hash='2608a6f38bd2bfe947b6e61f4e0c87cc80f831aa',
        )
        suffix = 'experimental/ietf-extracted-YANG-modules/ietf-yang-types@2020-07-06.yang'
        schema = os.path.join(schema_parts.schema_base_hash, suffix)

        yang_name_rev = 'successful@1970-01-01.yang'
        dst_path = f'{yc_gc.save_file_dir}/{yang_name_rev}'
        result = util.fetch_module_by_schema(schema, dst_path)

        self.assertEqual(result, True)
        self.assertEqual(os.path.isfile(dst_path), True)

    def test_fetch_module_by_schema_unsuccessfully(self):
        """Check if method returned False if wrong schema was passed as an argument.
        File should not be created.
        """
        schema_parts = SchemaParts(repo_owner='YangModels', repo_name='yang', commit_hash='random-hash')
        suffix = 'experimental/ietf-extracted-YANG-modules/ietf-yang-types@2020-07-06.yang'
        schema = os.path.join(schema_parts.schema_base_hash, suffix)

        yang_name_rev = 'unsuccessful@1970-01-01.yang'
        dst_path = f'{yc_gc.save_file_dir}/{yang_name_rev}'
        result = util.fetch_module_by_schema(schema, dst_path)

        self.assertEqual(result, False)
        self.assertEqual(os.path.isfile(dst_path), False)

    def test_fetch_module_by_schema_empty_schema(self):
        """Check if method returned False if non-existing URL was passed as schema argument.
        File should not be created.
        """
        schema = ''

        yang_name_rev = 'empty@1970-01-01.yang'
        dst_path = f'{yc_gc.save_file_dir}/{yang_name_rev}'
        result = util.fetch_module_by_schema(schema, dst_path)

        self.assertEqual(result, False)
        self.assertEqual(os.path.isfile(dst_path), False)

    def test_context_check_update_from(self):
        """Test result of pyang --check-update-from validation using context of two ietf-yang-types revisions."""
        old_schema = f'{yc_gc.save_file_dir}/ietf-yang-types@2010-09-24.yang'
        new_schema = f'{yc_gc.save_file_dir}/ietf-yang-types@2013-07-15.yang'

        ctx, new_schema_ctx = util.context_check_update_from(
            old_schema,
            new_schema,
            yc_gc.yang_models,
            yc_gc.save_file_dir,
        )

        self.assertIsNotNone(new_schema_ctx)
        self.assertEqual(new_schema_ctx.arg, 'ietf-yang-types')  # pyright: ignore
        self.assertNotEqual(ctx, None)
        self.assertEqual(len(ctx.errors), 0)
        self.assertEqual(ctx.errors, [])

    @mock.patch('pyang.context.Context.validate')
    def test_context_check_update_from_ctx_validate_exception(self, mock_ctx_validate: mock.MagicMock):
        """Test result of pyang --check-update-from validation using context of two ietf-yang-types revisions.
        ctx.validate() method is patched to achieve Exception raising

        Argument:
        :param mock_ctx_validate  (mock.MagicMock) ctx.validate() method is patched to raise Exception
        """
        mock_ctx_validate.side_effect = Exception()
        old_schema = f'{yc_gc.save_file_dir}/ietf-yang-types@2010-09-24.yang'
        new_schema = f'{yc_gc.save_file_dir}/ietf-yang-types@2013-07-15.yang'

        with self.assertRaises(Exception):
            util.context_check_update_from(old_schema, new_schema, yc_gc.yang_models, yc_gc.save_file_dir)

    def clear_job_log(self):
        """Clear job log for util_test if any exist in cronjob.json file."""
        cronjob_json_data = self.load_cronjob_data()

        if self.filename in cronjob_json_data:
            del cronjob_json_data[self.filename]

        with open(self.cronjob_file_path, 'w') as f:
            f.write(json.dumps(cronjob_json_data, indent=4))

    def load_cronjob_data(self) -> dict:
        """Load content of cronjob.json file."""
        try:
            with open(self.cronjob_file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


if __name__ == '__main__':
    unittest.main()
