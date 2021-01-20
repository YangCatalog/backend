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

import unittest
from unittest import mock

from api.globalConfig import yc_gc
from parseAndPopulate.loadJsonFiles import LoadFiles


class TestLoadFilesClass(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestLoadFilesClass, self).__init__(*args, **kwargs)

    def test_loadJsonFiles(self):
        """
        Test if 'parsed_jsons' object has the individual attributes set correctly.
        """
        parsed_jsons = LoadFiles(yc_gc.private_dir, yc_gc.logs_dir)

        names = []
        with open('{}/json_links'.format(yc_gc.private_dir), 'r') as f:
            for line in f:
                names.append(line.replace('.json', '').replace('\n', ''))

        # Object should containt following attributes
        self.assertTrue(hasattr(parsed_jsons, 'headers'))
        self.assertTrue(hasattr(parsed_jsons, 'names'))
        self.assertTrue(hasattr(parsed_jsons, 'status'))

        self.assertEqual(names, parsed_jsons.names)

        # Property should be set for each name found in json_links file
        for name in names:
            self.assertIn(name, parsed_jsons.headers)
            self.assertIn(name, parsed_jsons.status)

    @mock.patch('parseAndPopulate.loadJsonFiles.open')
    def test_loadJsonFiles_json_links_not_found(self, mock_open: mock.MagicMock):
        """
        Test if 'parsed_jsons' object has the individual attributes set correctly.
        Mock file opening to achieve FileNotFoundError.
        All attributes should be empty as the file was not found.
        """
        mock_open.side_efect = FileNotFoundError()
        parsed_jsons = LoadFiles(yc_gc.private_dir, yc_gc.logs_dir)

        # Object should containt following attributes
        self.assertTrue(hasattr(parsed_jsons, 'headers'))
        self.assertTrue(hasattr(parsed_jsons, 'names'))
        self.assertTrue(hasattr(parsed_jsons, 'status'))

        # Attributes should be empty as the file was not found
        self.assertEqual(parsed_jsons.names, [])
        self.assertEqual(parsed_jsons.headers, {})
        self.assertEqual(parsed_jsons.status, {})


if __name__ == "__main__":
    unittest.main()
