# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
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

"""
This class will load all the json files from the yangcatalog
private. These files are then used for module compilation status
and results
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import json

from utility import log


class LoadFiles:

    def __init__(self, private_dir, log_directory):
        LOGGER = log.get_logger(__name__, log_directory + '/parseAndPopulate.log')
        LOGGER.debug('Loading compilation statuses and results')
        self.names = []
        with open(private_dir + '/json_links', 'r') as f:
            for line in f:
                self.names.append(line.replace('.json', '').replace('\n', ''))

        self.status = {}
        self.headers = {}
        for name in self.names:
            with open('{}/{}.json'.format(private_dir, name), 'r') as f:
                self.status[name] = json.load(f)
            if name == 'IETFYANGRFC':
                with open('{}/{}.html'.format(private_dir, name)) as f:
                    html = f.read()
            else:
                with open('{}/{}YANGPageCompilation.html'.format(private_dir, name)) as f:
                    html = f.read()
            ths = html.split('<TH>')
            results = []
            for th in ths:
                res = th.split('</TH>')[0]
                if 'Compilation Result' in res:
                    results.append(res)
            self.headers[name] = results
