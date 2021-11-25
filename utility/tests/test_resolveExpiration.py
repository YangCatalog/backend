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

"""
TEST CASES for resolveExpiration.py:
I. Expiration of the module is 'not-applicable' - vendor module
II. This revision of the module is ratified - RFC
III. Module is already expired - older revision of draft
IV. Module is already expired - only initial draft
V. Active draft - not expired with expiration date in the future
VI. Module is already expired - last draft revision before RFC
VII. Module set to expired - new version of draft available
VIII. Datatracker unavailable - exception raised after GET request
"""


__author__ = "Slavomir Mazur"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "slavomir.mazur@pantheon.tech"

import json
import os
import unittest
from unittest import mock

import utility.log as log
from utility.confdService import ConfdService
from redisConnections.redisConnection import RedisConnection
from utility.resolveExpiration import resolve_expiration


class TestResolveExpirationClass(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestResolveExpirationClass, self).__init__(*args, **kwargs)
        self.module_name = 'utility'
        self.script_name = 'resolveExpiration'
        self.resources_path = '{}/resources'.format(os.path.dirname(os.path.abspath(__file__)))
        self.datatracker_failures = []
        self.LOGGER = self.get_logger()
        self.confdService = ConfdService()
        self.redisConnection = RedisConnection()

    #########################
    ### TESTS DEFINITIONS ###
    #########################

    def test_resolveExpiration_not_applicable(self):
        """ Check result of the resolveExpiration method for the module
        where expiration is not-applicable (= e.g. vendor module). Also check values of module properties,
        which are requested in the method.
        """
        module = self.load_from_json('dhcp-client@2014-12-18-simplified')
        result = resolve_expiration(module, self.LOGGER, self.datatracker_failures, self.confdService, self.redisConnection)

        self.assertEqual(result, False)
        # Check the relevant properties values
        self.assertEqual(module.get('maturity-level'), 'not-applicable')
        self.assertEqual(module.get('reference'), None)
        self.assertEqual(module.get('expired'), 'not-applicable')
        self.assertEqual(module.get('expires'), None)

    def test_resolveExpiration_ratified(self):
        """ Check result of the resolveExpiration method for the module
        which was ratified.
        Also check values of module properties, which are requested in the method.
        """
        module = self.load_from_json('iana-if-type@2014-05-08-simplified')
        result = resolve_expiration(module, self.LOGGER, self.datatracker_failures, self.confdService, self.redisConnection)

        self.assertEqual(result, False)
        # Check the relevant properties values
        self.assertEqual(module.get('maturity-level'), 'ratified')
        self.assertEqual(module.get('reference'), 'https://tools.ietf.org/html/rfc7224')
        self.assertEqual(module.get('expired'), False)
        self.assertEqual(module.get('expires'), None)

    @mock.patch('utility.resolveExpiration.requests.get')
    def test_resolveExpiration_expired_draft(self, mock_requests_get: mock.MagicMock):
        """ Check result of the resolveExpiration method for the module
        draft that has already expired. Also check values of module properties,
        which are requested in the method.

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return expected value from datatracker
        """
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.json.return_value = self.load_from_json('datatracker_expired_draft_response')

        module = self.load_from_json('iana-if-type@2011-03-30-simplified')
        result = resolve_expiration(module, self.LOGGER, self.datatracker_failures, self.confdService, self.redisConnection)

        self.assertEqual(result, False)
        # Check the relevant properties values
        self.assertEqual(module.get('maturity-level'), 'adopted')
        self.assertEqual(module.get('reference'), 'https://datatracker.ietf.org/doc/draft-ietf-netmod-iana-if-type/00')
        self.assertEqual(module.get('expired'), True)
        self.assertEqual(module.get('expires'), None)

    @mock.patch('utility.resolveExpiration.requests.get')
    def test_resolveExpiration_expired_initial_draft(self, mock_requests_get: mock.MagicMock):
        """ Check result of the resolveExpiration method for the module
        draft that has only initial draft. Also check values of module properties,
        which are requested in the method.

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return expected value from datatracker
        """
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.json.return_value = self.load_from_json('datatracker_empty_response')

        module = self.load_from_json('ietf-alarms@2015-05-04-simplified')
        result = resolve_expiration(module, self.LOGGER, self.datatracker_failures, self.confdService, self.redisConnection)

        self.assertEqual(result, False)
        # Check the relevant properties values
        self.assertEqual(module.get('maturity-level'), 'initial')
        self.assertEqual(module.get('reference'), 'https://datatracker.ietf.org/doc/draft-vallin-alarm-yang-module/00')
        self.assertEqual(module.get('expired'), True)
        self.assertEqual(module.get('expires'), None)

    @mock.patch('utility.resolveExpiration.requests.get')
    def test_resolveExpiration_active_draft(self, mock_requests_get: mock.MagicMock):
        """ Check result of the resolveExpiration method for the module
        draft that is active.
        Also check values of module properties, which are requested in the method.

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return expected value from datatracker
        """
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.json.return_value = self.load_from_json('datatracker_active_draft_response')

        module = self.load_from_json('ietf-inet-types@2021-02-22-simplified')
        result = resolve_expiration(module, self.LOGGER, self.datatracker_failures, self.confdService, self.redisConnection)

        self.assertEqual(result, False)
        # Check the relevant properties values
        self.assertEqual(module.get('maturity-level'), 'adopted')
        self.assertEqual(module.get('reference'), 'https://datatracker.ietf.org/doc/draft-ietf-netmod-rfc6991-bis/05')
        self.assertEqual(module.get('expired'), False)
        self.assertEqual(module.get('expires'), '2021-08-26T06:36:43-00:00')

    @mock.patch('utility.resolveExpiration.requests.get')
    def test_resolveExpiration_draft_expired_last_rev(self, mock_requests_get: mock.MagicMock):
        """ Check result of the resolveExpiration method for the module
        draft that expired and next revision is RFC (= this revision is last rev of draft).
        Also check values of module properties, which are requested in the method.

        Arguments:
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to return expected value from datatracker
        """
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.json.return_value = self.load_from_json('datatracker_expired_draft_response')

        module = self.load_from_json('iana-if-type@2014-01-15-simplified')
        result = resolve_expiration(module, self.LOGGER, self.datatracker_failures, self.confdService, self.redisConnection)

        self.assertEqual(result, False)
        # Check the relevant properties values
        self.assertEqual(module.get('maturity-level'), 'adopted')
        self.assertEqual(module.get('reference'), 'https://datatracker.ietf.org/doc/draft-ietf-netmod-iana-if-type/10')
        self.assertEqual(module.get('expired'), True)
        self.assertEqual(module.get('expires'), None)

    @mock.patch('utility.resolveExpiration.requests.get')
    @mock.patch('utility.resolveExpiration.requests.patch')
    @mock.patch('utility.resolveExpiration.requests.delete')
    def test_resolveExpiration_draft_expire(self, mock_requests_delete: mock.MagicMock, mock_requests_patch: mock.MagicMock, mock_requests_get: mock.MagicMock):
        """ Check result of the resolveExpiration method for the module
        draft that will expire now. Module should expire and expiraton date should be removed.
        Also check values of module properties, which are requested in the method.

        Arguments:
        :param mock_requests_delete     (mock.MagicMock) requests.delete() method is patched - no real request to Redis
        :param mock_requests_patch      (mock.MagicMock) requests.patch() method is patched - no real request to Redis
        :param mock_requests_get        (mock.MagicMock) requests.get() method is patched to return expected value from datatracker
        """
        mock_requests_get.return_value.status_code = 200
        mock_requests_get.return_value.json.return_value = self.load_from_json('datatracker_draft_expire_now_response')

        mock_requests_patch.return_value.status_code = 200
        mock_requests_patch.return_value.text = ''

        mock_requests_delete.return_value.status_code = 204
        mock_requests_delete.return_value.text = ''

        module = self.load_from_json('ietf-inet-types@2020-07-06-simplified')
        result = resolve_expiration(module, self.LOGGER, self.datatracker_failures, self.confdService, self.redisConnection)

        self.assertEqual(result, True)
        # Check the relevant properties values
        self.assertEqual(module.get('maturity-level'), 'adopted')
        self.assertEqual(module.get('reference'), 'https://datatracker.ietf.org/doc/draft-ietf-netmod-rfc6991-bis/04')
        self.assertEqual(module.get('expired'), True)
        self.assertEqual(len(self.datatracker_failures), 0)

    @mock.patch('utility.resolveExpiration.requests.get')
    @mock.patch('utility.resolveExpiration.time.sleep')
    def test_resolveExpiration_datatracker_raise_exception(self, mock_time_sleep: mock.MagicMock, mock_requests_get: mock.MagicMock):
        """ Check result of the resolveExpiration method if the datatracker is unavailable
        and raising exception while trying to make GET request. Method should return 'None'
        and the 'datatracker_failures' variable should contain problematic datatracker url

        Arguments:
        :param mock_time_sleep      (mock.MagicMock) time.sleep() method is patched so no need to wait during tests run
        :param mock_requests_get    (mock.MagicMock) requests.get() method is patched to raise exception
        """
        # Load submodule and its config
        mock_requests_get.side_effect = Exception()
        mock_time_sleep.return_value = None

        module = self.load_from_json('ietf-inet-types@2020-07-06-simplified')
        result = resolve_expiration(module, self.LOGGER, self.datatracker_failures, self.confdService, self.redisConnection)

        self.assertEqual(result, None)
        self.assertNotEqual(len(self.datatracker_failures), 0)

    def test_resolveExpiration_get_help(self):
        """ Test whether script help has the correct structure (check only structure not content).
        """
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()

        script_help = script_conf.get_help()

        self.assertIn('help', script_help)
        self.assertIn('options', script_help)
        self.assertNotEqual(script_help.get('options'), {})

    def test_resolveExpiration_get_args_list(self):
        """ Test whether script default arguments has the correct structure (check only structure not content).
        """
        # Load submodule and its config
        module = __import__(self.module_name, fromlist=[self.script_name])
        submodule = getattr(module, self.script_name)
        script_conf = submodule.ScriptConfig()

        script_args_list = script_conf.get_args_list()

        self.assertNotEqual(script_args_list, {})
        for key in script_args_list:
            self.assertIn('type', script_args_list.get(key))
            self.assertIn('default', script_args_list.get(key))

    ##########################
    ### HELPER DEFINITIONS ###
    ##########################

    def get_logger(self):
        """ Init the logger and modify the handlers to avoid duplicate messages.
        """
        LOGGER = log.get_logger('resolveExpiration', '/var/yang/logs/jobs/resolveExpiration.log')
        if len(LOGGER.handlers) > 1:
            LOGGER.handlers[1].close()
            LOGGER.removeHandler(LOGGER.handlers[1])

        return LOGGER

    def load_from_json(self, key: str):
        with open('{}/utility_tests_data.json'.format(self.resources_path), 'r') as f:
            file_content = json.load(f)
            loaded_result = file_content.get(key, {})
        return loaded_result


if __name__ == "__main__":
    unittest.main()
