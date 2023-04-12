# Copyright The IETF Trust 2023, All Rights Reserved
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

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'

import unittest
from unittest import mock

from werkzeug.exceptions import BadRequest

from api.views.json_checker import IncorrectShape, MissingField, Union, check, check_error


class TestJsonCheckerClass(unittest.TestCase):
    def test_check(self):
        check(
            {'string': str, 'number': int, 'nesting': {'string': str}, 'list': [str], 'union': Union(str, int)},
            {'string': 'test', 'number': 42, 'nesting': {'string': 'test'}, 'list': ['test', 'test'], 'union': 42},
        )
        check({'empty_list': [str], 'empty_dict': {}}, {'empty_list': [], 'empty_dict': {'extra_key': 'test'}})
        with self.assertRaises(MissingField):
            check({'required_field': str}, {})
        with self.assertRaises(IncorrectShape):
            check({'string': str}, {'string': 42})
        with self.assertRaises(IncorrectShape):
            check({'leaf': Union(str, int)}, {'leaf': {'node': 'real_leaf'}})

    def test_check_error(self):
        with mock.patch('api.views.json_checker.check', lambda _, __: None):
            check_error({}, {})
        with mock.patch('api.views.json_checker.check', mock.MagicMock(side_effect=MissingField('["test"]'))):
            try:
                check_error({}, {})
            except BadRequest as e:
                self.assertEqual(e.description, 'Missing field at data["test"]')
        with mock.patch(
            'api.views.json_checker.check',
            mock.MagicMock(side_effect=IncorrectShape('null', '["test"]')),
        ):
            try:
                check_error({}, {})
            except BadRequest as e:
                self.assertEqual(e.description, 'Incorrect shape at data["test"]. Expected null.')


if __name__ == '__main__':
    unittest.main()
