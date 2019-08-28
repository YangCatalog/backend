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


class ParseException(Exception):

    def __init__(self, path):
        #TODO absolute path to json file should be received from yangcatalog.conf config file
        self.msg = "Failed to parse module on path {}".format(path)
        with open('/var/yang/unparsable-modules.json', 'r') as f:
            modules = json.load(f)
        module = path.split('/')[-1]
        if module not in modules:
            modules.append(module)
        with open('/var/yang/unparsable-modules.json', 'w') as f:
            json.dump(modules, f)
