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

__author__ = "Slavomir Mazur"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "slavomir.mazur@pantheon.tech"

import os
import unittest
from unittest import mock

from api.globalConfig import yc_gc
from parseAndPopulate.loadJsonFiles import LoadFiles


class TestLoadFilesClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestLoadFilesClass, self).__init__(*args, **kwargs)
        self.test_private_dir = os.path.join(os.environ['BACKEND'], 'tests/resources/html/private')

    def test_loadJsonFiles(self):
        """
        Test if 'parsed_jsons' object has the individual attributes set correctly.
        Excluded file names should no be present in 'parsed_json' dict as keys.
        """
        parsed_jsons = LoadFiles('IETFYANGRFC', self.test_private_dir, yc_gc.logs_dir)

        names = ['IETFDraft', 'IETFDraftExample', 'IETFYANGRFC', 'IETFYANGRFC']

        # Object should containt following attributes
        self.assertTrue(hasattr(parsed_jsons, 'headers'))
        self.assertTrue(hasattr(parsed_jsons, 'names'))
        self.assertTrue(hasattr(parsed_jsons, 'status'))

        self.assertEqual(names, parsed_jsons.names)

        # Property should be set for each name found in json_links file
        for name in names:
            self.assertIn(name, parsed_jsons.headers)
            self.assertIn(name, parsed_jsons.status)


    def test_loadJsonFiles_non_existing_json_file(self):
        """
        Test if 'parsed_jsons' object has the individual attributes set correctly.
        FileNotFound exceptions will be raised while trying to load content of json/html files
        - headers and status properties should be empty for this name.

        Arguments:
        :param mock_load_names  (mock.MagicMock) load_names() method is patched, to return name of non-exisiting json
        """
        parsed_jsons = LoadFiles('SuperRandom', self.test_private_dir, yc_gc.logs_dir)

        # Object should containt following attributes
        self.assertTrue(hasattr(parsed_jsons, 'headers'))
        self.assertTrue(hasattr(parsed_jsons, 'names'))
        self.assertTrue(hasattr(parsed_jsons, 'status'))

        # Status and headers should be empty for non-existing json/html files
        print(parsed_jsons.headers)
        self.assertEqual(parsed_jsons.headers['SuperRandom'], [])
        self.assertEqual(parsed_jsons.status['SuperRandom'], {})


if __name__ == '__main__':
    unittest.main()
