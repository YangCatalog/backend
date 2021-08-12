# Copyright The IETF Trust 2019, All Rights Reserved
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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import json
import sys
from utility.create_config import create_config


class ParseException(Exception):

    def __init__(self, path):
        config = create_config()
        var_path = config.get('Directory-Section', 'var', fallback='/var/yang')
        self.msg = 'Failed to parse module on path {}'.format(path)
        try:
            with open('{}/unparsable-modules.json'.format(var_path), 'r') as f:
                modules = json.load(f)
        except:
            modules = []
        module = path.split('/')[-1]
        if module not in modules:
            modules.append(module)
        with open('{}/unparsable-modules.json'.format(var_path), 'w') as f:
            json.dump(modules, f)
