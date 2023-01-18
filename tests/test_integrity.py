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

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'

import json
import os
import unittest

from parseAndPopulate import integrity as itg
from utility.create_config import create_config
from utility.yangParser import parse


class TestIntegrityClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = create_config()
        cls.module_dir = os.path.join(os.environ['BACKEND'], 'tests/resources/integrity')
        cls.yang_models = config.get('Directory-Section', 'yang-models-dir')

    def module_path(self, name: str) -> str:
        return os.path.join(self.module_dir, f'{name}.yang')

    def test_check_revision(self):
        good = parse(self.module_path('good'))
        assert good
        self.assertTrue(itg.check_revision(good))

        missing_revision = parse(self.module_path('missing-revision'))
        assert missing_revision
        self.assertFalse(itg.check_revision(missing_revision))

        invalid_revision = parse(self.module_path('invalid-revision'))
        assert invalid_revision
        self.assertFalse(itg.check_revision(invalid_revision))

    def test_check_namespace(self):
        good = parse(self.module_path('good'))
        assert good
        self.assertTrue(itg.check_namespace(good))

        missing_namespace = parse(self.module_path('missing-namespace'))
        assert missing_namespace
        self.assertFalse(itg.check_namespace(missing_namespace))

        invalid_namespace = parse(self.module_path('invalid-namespace'))
        assert invalid_namespace
        self.assertFalse(itg.check_namespace(invalid_namespace))

    def test_check_depencendies(self):
        good = parse(self.module_path('good'))
        assert good

        all_imports, missing_imports = itg.check_dependencies('import', good, self.module_dir)
        self.assertSetEqual(all_imports, {'invalid-revision'})
        self.assertFalse(missing_imports)

        all_includes, missing_includes = itg.check_dependencies('include', good, self.module_dir)
        self.assertSetEqual(all_includes, {'invalid-namespace', 'l1-dependency'})
        self.assertFalse(missing_includes)

        missing_import = parse(self.module_path('missing-import'))
        assert missing_import

        all_imports, missing_imports = itg.check_dependencies('import', missing_import, self.module_dir)
        self.assertSetEqual(all_imports, {'nonexistent'})
        self.assertSetEqual(missing_imports, {'nonexistent'})

        missing_include = parse(self.module_path('missing-include'))
        assert missing_include

        all_includes, missing_includes = itg.check_dependencies('include', missing_include, self.module_dir)
        self.assertSetEqual(all_includes, {'nonexistent'})
        self.assertSetEqual(missing_includes, {'nonexistent'})

    def test_sdo(self):
        script_conf = itg.DEFAULT_SCRIPT_CONFIG.copy()
        setattr(script_conf.args, 'dir', self.module_dir)
        setattr(script_conf.args, 'sdo', True)
        itg.main(script_conf)

        expected = {
            'missing-revisions': [self.module_path('invalid-revision'), self.module_path('missing-revision')],
            'missing-namespaces': [self.module_path('invalid-namespace'), self.module_path('missing-namespace')],
            'missing-modules': {self.module_path('missing-import'): ['nonexistent']},
            'missing-submodules': {self.module_path('missing-include'): ['nonexistent']},
            'unused-modules': {},
        }

        with open('integrity.json') as f:
            result = json.load(f)

        self.assertDictEqual(result, expected)

    def test_capabilities_to_modules(self):
        result = set(itg.capabilities_to_modules(os.path.join(self.module_dir, 'capabilities.xml')))
        expected = {
            'good',
            'deviation',
            'missing-revision',
            'invalid-revision',
            'missing-namespace',
            'invalid-namespace',
            'missing-import',
            'missing-include',
            'nonexistent',
        }
        self.assertSetEqual(result, expected)

    def test_vendor(self):
        script_conf = itg.DEFAULT_SCRIPT_CONFIG.copy()
        setattr(script_conf.args, 'dir', self.module_dir)
        itg.main(script_conf)

        expected = {
            'missing-revisions': [self.module_path('invalid-revision'), self.module_path('missing-revision')],
            'missing-namespaces': [self.module_path('invalid-namespace'), self.module_path('missing-namespace')],
            'missing-modules': {
                os.path.join(self.module_dir, 'capabilities.xml'): ['nonexistent'],
                self.module_path('missing-import'): ['nonexistent'],
            },
            'missing-submodules': {self.module_path('missing-include'): ['nonexistent']},
            'unused-modules': {self.module_dir: ['unused']},
        }

        with open('integrity.json') as f:
            result = json.load(f)

        self.assertDictEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
