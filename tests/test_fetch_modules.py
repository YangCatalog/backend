# Copyright The IETF Trust 2022, All Rights Reserved
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

__author__ = 'Dmytro Kyrychenko'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'dmytro.kyrychenko@pantheon.tech'

import json
import unittest
from unittest import mock

import requests

from utility.create_config import create_config
from utility.fetch_modules import fetch_modules
from utility.log import get_logger


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)

    def json(self):
        return self.json_data


class TestFetchModules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = create_config()
        yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')
        cls.fetch_url = f'{yangcatalog_api_prefix}/search/modules'
        cls.logger = get_logger('test_fetch_modules', './test_fetch_modules.log')

        cls.test_modules = {
            'module': [
                {
                    'author-email': 'jd@jd.org',
                    'contact': 'Jane Doe <jane@doe.com>',
                    'document-name': 'draft-for-test.txt',
                    'name': 'draft-for-test',
                    'organization': 'ietf',
                },
                {
                    'author-email': 'jhd@jd.org',
                    'contact': 'John Doe <john@doe.com>',
                    'document-name': 'draft-for-another-test.txt',
                    'name': 'draft-for-another-test',
                    'organization': 'cisco',
                },
            ],
        }

    def test_simple_request(self):
        def mocked_requests_get(*args, **kwargs):
            if args[0] == self.fetch_url:
                return MockResponse(json_data=self.test_modules, status_code=200)
            else:
                return requests.get(*args, **kwargs)

        with mock.patch('requests.get', mocked_requests_get):
            modules = fetch_modules(self.logger)

        self.assertIsNotNone(modules)
        self.assertEqual(modules, self.test_modules['module'])

    @mock.patch('utility.fetch_modules.SLEEP_TIME', 1)
    def test_failed_request_less_200(self):
        def mocked_requests_get(*args, **kwargs):
            if args[0] == self.fetch_url:
                return MockResponse(json_data={}, status_code=199)
            else:
                return requests.get(*args, **kwargs)

        with mock.patch('requests.get', mocked_requests_get):
            with self.assertRaises(RuntimeError):
                fetch_modules(self.logger)

    @mock.patch('utility.fetch_modules.SLEEP_TIME', 1)
    def test_failed_request_more_299(self):
        def mocked_requests_get(*args, **kwargs):
            if args[0] == self.fetch_url:
                return MockResponse(json_data={}, status_code=300)
            else:
                return requests.get(*args, **kwargs)

        with mock.patch('requests.get', mocked_requests_get):
            with self.assertRaises(RuntimeError):
                fetch_modules(self.logger)

    @mock.patch('utility.fetch_modules.SLEEP_TIME', 1)
    def test_failed_request_more_299_then_success(self):
        with mock.patch(
            'requests.get',
            side_effect=[
                MockResponse(json_data={}, status_code=300),
                MockResponse(json_data=self.test_modules, status_code=200),
            ],
        ):
            modules = fetch_modules(self.logger)

        self.assertIsNotNone(modules)
        self.assertEqual(modules, self.test_modules['module'])

    @mock.patch('utility.fetch_modules.SLEEP_TIME', 1)
    @mock.patch('utility.fetch_modules.N_RETRIES', 2)
    def test_success_on_last_attempt(self):
        with mock.patch(
            'requests.get',
            side_effect=[
                MockResponse(json_data={}, status_code=300),
                MockResponse(json_data=self.test_modules, status_code=200),
            ],
        ):
            modules = fetch_modules(self.logger)

        self.assertIsNotNone(modules)
        self.assertEqual(modules, self.test_modules['module'])
