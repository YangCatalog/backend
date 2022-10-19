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
import unittest

from api.globalConfig import yc_gc
from utility.yangParser import ParseException


class TestParseExceptionClass(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestParseExceptionClass, self).__init__(*args, **kwargs)
        self.test_private_dir = os.path.join(os.environ['BACKEND'], 'tests/resources/html/private')

    def test_parse_exception(self):
        """Test if ParseException is raised when non-existing path is passed as 'path' argument.
        Load content of unparsable-modules.json file and check whether name of the module is stored in file.
        """
        ParseException('module.yang')

        with open(os.path.join(yc_gc.var_yang, 'unparsable-modules.json'), 'r') as f:
            modules = json.load(f)

        self.assertNotEqual(modules, [])
        self.assertIn('module.yang', modules)


if __name__ == '__main__':
    unittest.main()
