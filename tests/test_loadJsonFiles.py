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
        self.excluded_names = ['private', 'IETFCiscoAuthorsYANGPageCompilation']
        self.test_private_dir = os.path.join(os.environ['BACKEND'], 'tests/resources/html/private')

    def test_loadJsonFiles(self):
        """
        Test if 'parsed_jsons' object has the individual attributes set correctly.
        Excluded file names should no be present in 'parsed_json' dict as keys.
        """
        parsed_jsons = LoadFiles(self.test_private_dir, yc_gc.logs_dir)

        names = []
        with open('{}/json_links'.format(self.test_private_dir), 'r') as f:
            for line in f:
                names.append(line.replace('.json', '').replace('\n', ''))
        names = [name for name in names if name not in self.excluded_names]

        # Object should containt following attributes
        self.assertTrue(hasattr(parsed_jsons, 'headers'))
        self.assertTrue(hasattr(parsed_jsons, 'names'))
        self.assertTrue(hasattr(parsed_jsons, 'status'))

        self.assertEqual(names, parsed_jsons.names)

        # Property should be set for each name found in json_links file
        for name in names:
            self.assertIn(name, parsed_jsons.headers)
            self.assertIn(name, parsed_jsons.status)

        # Property should NOT be set for excluded names
        for name in self.excluded_names:
            self.assertNotIn(name, parsed_jsons.headers)
            self.assertNotIn(name, parsed_jsons.status)

    def test_loadJsonFiles_json_links_not_found(self):
        """
        Test if 'parsed_jsons' object has the individual attributes set correctly.
        Incorrect path is passed as argument resulting no json_link file is found there.
        All attributes should be empty as the file was not found.
        """
        parsed_jsons = LoadFiles('path/to/random/dir', yc_gc.logs_dir)

        # Object should containt following attributes
        self.assertTrue(hasattr(parsed_jsons, 'headers'))
        self.assertTrue(hasattr(parsed_jsons, 'names'))
        self.assertTrue(hasattr(parsed_jsons, 'status'))

        # Attributes should be empty as the file was not found
        self.assertEqual(parsed_jsons.names, [])
        self.assertEqual(parsed_jsons.headers, {})
        self.assertEqual(parsed_jsons.status, {})

    @mock.patch('parseAndPopulate.loadJsonFiles.LoadFiles.load_names')
    def test_loadJsonFiles_non_existing_json_file(self, mock_load_names: mock.MagicMock):
        """
        Test if 'parsed_jsons' object has the individual attributes set correctly.
        load_names() method will return non-exisiting name of json file, so FileNotFound exceptions will be raised
        while trying to load content of json/html files - headers and status properties should be empty for this name.

        Arguments:
        :param mock_load_names  (mock.MagicMock) load_names() method is patched, to return name of non-exisiting json
        """
        non_existing_json_name = 'SuperRandom'
        mock_load_names.return_value = [non_existing_json_name]

        parsed_jsons = LoadFiles(self.test_private_dir, yc_gc.logs_dir)

        # Object should containt following attributes
        self.assertTrue(hasattr(parsed_jsons, 'headers'))
        self.assertTrue(hasattr(parsed_jsons, 'names'))
        self.assertTrue(hasattr(parsed_jsons, 'status'))

        # Status and headers should be empty for non-existing json/html files
        self.assertEqual(parsed_jsons.headers[non_existing_json_name], [])
        self.assertEqual(parsed_jsons.status[non_existing_json_name], {})


if __name__ == "__main__":
    unittest.main()
