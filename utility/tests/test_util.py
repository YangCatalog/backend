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
from utility.staticVariables import github_raw


class TestUtilClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestUtilClass, self).__init__(*args, **kwargs)
        self.filename = os.path.basename(__file__).split('.py')[0]
        self.job_log_properties = ['start', 'end', 'status', 'error', 'messages', 'last_successfull']
        self.resources_path = '{}/resources'.format(os.path.dirname(os.path.abspath(__file__)))
        self.util_tests_dir = '{}/util-tests'.format(yc_gc.temp_dir)

    #########################
    ### TESTS DEFINITIONS ###
    #########################

    def test_get_curr_dir(self):
        """ Test result of method for path passed as an argument.
        """
        path = '/example/folder/example.txt'
        result = util.get_curr_dir(path)

        self.assertEqual(result, '/example/folder')

    def test_get_curr_dir_empty_path(self):
        """ Test result of method, when empty string is passed as an argument.
        """
        result = util.get_curr_dir('')

        self.assertEqual(result, os.getcwd())

    def test_find_first_file_with_specific_revision(self):
        """ Try to find the first file that matches the pattern with specific revision.
        Test if a module with the same name and revision was found.
        """
        pattern = 'ietf-yang-types.yang'
        pattern_with_revision = 'ietf-yang-types@2010-09-24.yang'

        result = util.find_first_file(self.util_tests_dir, pattern, pattern_with_revision)

        self.assertEqual(result, '{}/ietf-yang-types@2010-09-24.yang'.format(self.util_tests_dir))

    def test_find_first_file_with_wildcard_revision(self):
        """ Try to find the first file that matches the pattern with
        an unspecified revision (specified by an asterisk).
        Test if a module with the same name and without revision in name is returned.
        """
        pattern = 'ietf-yang-types.yang'
        pattern_with_revision = 'ietf-yang-types@*.yang'

        result = util.find_first_file(self.util_tests_dir, pattern, pattern_with_revision)

        self.assertEqual(result, '{}/ietf-yang-types.yang'.format(self.util_tests_dir))

    def test_find_first_file_without_revision(self):
        """ Try to find the first file that matches the pattern without specified revision.
        It will try to parse the yang module to get its revision
        and check if that revision is also in 'pattern_with_revision' variable.
        """
        pattern = 'ietf-yang-types.yang'
        pattern_with_revision = 'ietf-yang-types@2013-07-15.yang'

        result = util.find_first_file(self.util_tests_dir, pattern, pattern_with_revision)

        self.assertEqual(result, '{}/ietf-yang-types.yang'.format(self.util_tests_dir))

    @mock.patch('utility.yangParser.parse')
    def test_find_first_file_without_revision_empty_search(self, mock_yang_parse: mock.MagicMock):
        """ Try to find the first file that matches the pattern without specified revision.
        It will try to parse the yang module to get its revision, but exception occur during parsing.
        """
        mock_yang_parse.return_value.search.return_value = []
        pattern = 'ietf-yang-types.yang'
        pattern_with_revision = 'ietf-yang-types@2013-07-15.yang'

        result = util.find_first_file(self.util_tests_dir, pattern, pattern_with_revision)

        self.assertEqual(result, None)

    def test_find_first_file_empty_arguments(self):
        """ Test result of method, when empty strings are passed as an argument.
        Nothing should be found in this case.
        """
        directory = ''
        pattern = ''
        pattern_with_revision = ''

        result = util.find_first_file(directory, pattern, pattern_with_revision)

        self.assertEqual(result, None)

    def test_create_signature(self):
        """ Test the result of the method with the given arguments.
        """
        secret_key = 'S3cr3t_k3y'
        string_to_sign = 'test'

        result = util.create_signature(secret_key, string_to_sign)
        self.assertEqual(result, '33f57bcec731bb8f9ddf964bd1910e657ace0a64')

    def test_create_signature_empty_arguments(self):
        """ Test the result of the method with the given arguments.
        """
        result = util.create_signature('', '')
        self.assertEqual(result, 'fbdb1d1b18aa6c08324b7d64b71fb76370690e1d')

    def test_job_log_succes(self):
        """ Test if job run information was correctly dumped into cronjob.json file if status is Success.
        Check if structure is correct.
        """
        start_time = int(time.time())
        util.job_log(start_time, yc_gc.temp_dir, status='Success', filename=self.filename)
        file_content = self.load_cronjobs_json()

        job_log = file_content.get(self.filename, {})

        self.assertNotEqual(file_content, {})
        self.assertIn(self.filename, file_content)
        self.assertEqual('Success', job_log['status'])
        for prop in self.job_log_properties:
            self.assertIn(prop, job_log)

        self.clear_job_log()

    def test_job_log_fail(self):
        """ Test if job run information was correctly dumped into cronjob.json file if status is Fail.
        Check if structure is correct.
        """
        start_time = int(time.time())
        util.job_log(start_time, yc_gc.temp_dir, error='Error occured', status='Fail', filename=self.filename)
        file_content = self.load_cronjobs_json()

        job_log = file_content.get(self.filename, {})

        self.assertNotEqual(file_content, {})
        self.assertIn(self.filename, file_content)
        self.assertEqual('Fail', job_log['status'])
        for prop in self.job_log_properties:
            self.assertIn(prop, job_log)

        self.clear_job_log()

    def test_job_log_messages(self):
        """ Test if job run information was correctly dumped into cronjob.json file if there are some additional messages.
        Check if structure is correct.
        """
        start_time = int(time.time())
        messages = [
            {'label': 'Message label', 'message': 'Message text'}
        ]
        util.job_log(start_time, yc_gc.temp_dir, messages=messages, status='Success', filename=self.filename)
        file_content = self.load_cronjobs_json()

        job_log = file_content.get(self.filename, {})
        job_log_messages = job_log['messages']

        self.assertNotEqual(file_content, {})
        self.assertIn(self.filename, file_content)
        self.assertEqual('Success', job_log['status'])
        self.assertNotEqual(len(job_log_messages), 0)
        for prop in self.job_log_properties:
            self.assertIn(prop, job_log)

        for message in job_log_messages:
            self.assertIn('label', message)
            self.assertIn('message', message)

        self.clear_job_log()

    def test_fetch_module_by_schema_successfully(self):
        """ Test if content of yang module was successfully fetched from Github and stored to the file.
        """
        schema = '{}/YangModels/yang/2608a6f38bd2bfe947b6e61f4e0c87cc80f831aa' \
            '/experimental/ietf-extracted-YANG-modules/ietf-yang-types@2020-07-06.yang' \
            .format(github_raw)
        yang_name_rev = 'successful@1970-01-01.yang'
        dst_path = '{}/{}'.format(yc_gc.save_file_dir, yang_name_rev)
        result = util.fetch_module_by_schema(schema, dst_path)

        self.assertEqual(result, True)
        self.assertEqual(os.path.isfile(dst_path), True)

    def test_fetch_module_by_schema_unsuccessfully(self):
        """ Check if method returned False if wrong schema was passed as an argument.
        File should not be created.
        """
        schema = '{}/YangModels/yang/random-hash' \
            '/experimental/ietf-extracted-YANG-modules/ietf-yang-types@2020-07-06.yang' \
            .format(github_raw)

        yang_name_rev = 'unsuccessful@1970-01-01.yang'
        dst_path = '{}/{}'.format(yc_gc.save_file_dir, yang_name_rev)
        result = util.fetch_module_by_schema(schema, dst_path)

        self.assertEqual(result, False)
        self.assertEqual(os.path.isfile(dst_path), False)

    def test_fetch_module_by_schema_empty_schema(self):
        """ Check if method returned False if non-existing URL was passed as schema argument.
        File should not be created.
        """
        schema = ''

        yang_name_rev = 'empty@1970-01-01.yang'
        dst_path = '{}/{}'.format(yc_gc.save_file_dir, yang_name_rev)
        result = util.fetch_module_by_schema(schema, dst_path)

        self.assertEqual(result, False)
        self.assertEqual(os.path.isfile(dst_path), False)

    @mock.patch('utility.util.Elasticsearch.search')
    def test_get_module_from_es_result_found(self, mock_es: mock.MagicMock):
        """ Test whether Elasticsearch search has the correct structure
        and contains the searched data when the module was found in the database.

        Arguments:
        :param mock_es  (mock.MagicMock) Elasticsearch search() method is patched,
        so it is not necessary to have a running Elasticsearch instance
        """
        # Load desired Elasticsearch search result
        with open('{}/utility_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            es_search_result_found = file_content.get('es_search_result_found', {})
        mock_es.return_value = es_search_result_found
        name = 'ietf-yang-types'
        revision = '2013-07-15'
        organization = 'ietf'
        desired_dir = '{}/{}@{}.yang'.format(yc_gc.save_file_dir, name, revision)
        result = util.get_module_from_es(name, revision)

        self.assertNotEqual(result, {})
        self.assertIn('hits', result)
        self.assertIn('total', result['hits'])
        self.assertNotEqual(result['hits']['total'], 0)

        hits = result['hits']['hits']
        for module in hits:
            self.assertEqual(module['_source']['module'], name)
            self.assertEqual(module['_source']['revision'], revision)
            self.assertEqual(module['_source']['organization'], organization)
            self.assertEqual(module['_source']['dir'], desired_dir)

    @mock.patch('utility.util.Elasticsearch.search')
    def test_get_module_from_es_result_not_found(self, mock_es: mock.MagicMock):
        """ Test whether Elasticsearch search has the correct structure
        and contains the searched data when the module was NOT found in the database.

        Arguments:
        :param mock_es  (mock.MagicMock) Elasticsearch search() method is patched,
        so it is not necessary to have a running Elasticsearch instance
        """
        # Load desired Elasticsearch search result
        with open('{}/utility_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            es_search_result_not_found = file_content.get('es_search_result_not_found', {})
        mock_es.return_value = es_search_result_not_found
        name = 'non-existing-module'
        revision = '2013-07-15'
        result = util.get_module_from_es(name, revision)

        self.assertNotEqual(result, {})
        self.assertIn('hits', result)
        self.assertIn('total', result['hits'])
        self.assertEqual(result['hits']['total'], 0)

        hits = result['hits']['hits']
        self.assertEqual(hits, [])

    @mock.patch('utility.util.Elasticsearch.search')
    def test_get_module_from_es_missing_arguments(self, mock_es: mock.MagicMock):
        """ Test whether method returned empty dictionaty when Elasticsearch search raised exception.

        Arguments:
        :param mock_es  (mock.MagicMock) Elasticsearch search() method is patched,
        so it is not necessary to have a running Elasticsearch instance
        """
        mock_es.side_effect = Exception()
        name = ''
        revision = ''
        result = util.get_module_from_es(name, revision)

        self.assertEqual(result, {})

    def test_context_check_update_from(self):
        """ Test result of pyang --check-update-from validation using context of two ietf-yang-types revisions.
        """
        old_schema = '{}/ietf-yang-types@2010-09-24.yang'.format(yc_gc.save_file_dir)
        new_schema = '{}/ietf-yang-types@2013-07-15.yang'.format(yc_gc.save_file_dir)

        ctx, new_schema_ctx = util.context_check_update_from(old_schema, new_schema,
                                                             yc_gc.yang_models, yc_gc.save_file_dir)

        self.assertNotEqual(new_schema_ctx, None)
        self.assertEqual(new_schema_ctx.arg, 'ietf-yang-types')
        self.assertNotEqual(ctx, None)
        self.assertEqual(len(ctx.errors), 0)
        self.assertEqual(ctx.errors, [])

    @mock.patch('pyang.context.Context.validate')
    def test_context_check_update_from_ctx_validate_exception(self, mock_ctx_validate: mock.MagicMock):
        """ Test result of pyang --check-update-from validation using context of two ietf-yang-types revisions.
        ctx.validate() method is patched to achieve Exception raising

        Argument:
        :param mock_ctx_validate  (mock.MagicMock) ctx.validate() method is patched to raise Exception
        """
        mock_ctx_validate.side_effect = Exception()
        old_schema = '{}/ietf-yang-types@2010-09-24.yang'.format(yc_gc.save_file_dir)
        new_schema = '{}/ietf-yang-types@2013-07-15.yang'.format(yc_gc.save_file_dir)

        with self.assertRaises(Exception):
            util.context_check_update_from(old_schema, new_schema, yc_gc.yang_models, yc_gc.save_file_dir)

    ##########################
    ### HELPER DEFINITIONS ###
    ##########################

    def clear_job_log(self):
        """ Clear job log for util_test if any exist in cronjob.json file.
        """
        file_content = self.load_cronjobs_json()

        if self.filename in file_content:
            del file_content[self.filename]

        with open('{}/cronjob.json'.format(yc_gc.temp_dir), 'w') as f:
            f.write(json.dumps(file_content, indent=4))

    def load_cronjobs_json(self):
        """ Load content of cronjobs.json file.
        """
        try:
            with open('{}/cronjob.json'.format(yc_gc.temp_dir), 'r') as f:
                file_content = json.load(f)
        except:
            file_content = {}

        return file_content


if __name__ == '__main__':
    unittest.main()
