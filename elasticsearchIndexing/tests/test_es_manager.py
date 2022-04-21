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

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

import unittest
from unittest import mock

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices


class MockESManager(ESManager):
    def __init__(self) -> None:
        self.es = mock.MagicMock()


class TestESManagerClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestESManagerClass, self).__init__(*args, **kwargs)

    def setUp(self):
        self.es_manager = MockESManager()
        self.es_manager = ESManager()

    # @mock.patch('elasticsearchIndexing.es_manager.ESManager.create_index')
    # def test_create_index(self, mock_create_index: mock.MagicMock):
    #     mock_create_index.return_value = {'todo'}
    #     result = self.es_manager.create_index(ESIndices.MODULES)

    def test_create_index(self):
        result = self.es_manager.create_index(ESIndices.MODULES)


if __name__ == '__main__':
    unittest.main()
