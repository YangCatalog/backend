# Copyright The IETF Trust 2020, All Rights Reserved
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
__copyright__ = 'Copyright The IETF Trust 2020, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'dmytro.kyrychenko@pantheon.tech'

import json
import os
import unittest

from api.globalConfig import yc_gc
from parseAndPopulate.dir_paths import DirPaths
from parseAndPopulate.models.schema_parts import SchemaParts

from parseAndPopulate.resolvers.basic import BasicResolver

from pyang.statements import Statement, new_statement


class TestResolversClass(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestResolversClass, self).__init__(*args, **kwargs)

        # Declare variables
        self.schema_parts = SchemaParts(repo_owner='YangModels', repo_name='yang', commit_hash='master')
        self.tmp_dir = '{}/'.format(yc_gc.temp_dir)
        self.resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')
        self.test_private_dir = os.path.join(self.resources_path, 'html/private')
        self.dir_paths: DirPaths = {
            'cache': '',
            'json': '',
            'log': yc_gc.logs_dir,
            'private': '',
            'result': yc_gc.result_dir,
            'save': yc_gc.save_file_dir,
            'yang_models': yc_gc.yang_models
        }
        self.test_repo = os.path.join(yc_gc.temp_dir, 'test/YangModels/yang')


    def test_basic_resolver_simple_resolve(self):
        stmt = new_statement(None, None, 0, 'output', 'test_output')
        br = BasicResolver(parsed_yang=stmt, property_name="test")
        res = br.resolve()
        self.assertEqual(res, "test_arg")


if __name__ == "__main__":
    unittest.main()
