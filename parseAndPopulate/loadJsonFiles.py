"""
This class will load all the json files from the yangcatalog
private. These files are then used for module compilation status
and results
"""
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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import requests

from utility import log


class LoadFiles:

    def __init__(self, credentials, log_directory, private_url):
        LOGGER = log.get_logger(__name__, log_directory + '/parseAndPopulate.log')
        LOGGER.debug('Loading Benoit\'s compilation statuses and results')
        response = requests.get(private_url + '/json_links', auth=(credentials[0], credentials[1]))
        self.names = []
        if response.status_code == 200:
            self.names = response.text.replace('.json', '').split('\n')
            if self.names.count(''):
                self.names.remove('')
        self.status = {}
        self.headers = {}
        for name in self.names:
            self.status[name] = requests.get('{}{}.json'.format(private_url, name)
                                             , auth=(credentials[0], credentials[1])).json()
            html = requests.get('{}{}YANGPageCompilation.html'.format(private_url, name)
                                , auth=(credentials[0], credentials[1])).text

            ths = html.split('<TH>')
            results = []
            for th in ths:
                res = th.split('</TH>')[0]
                if 'Compilation Result' in res:
                    results.append(res)
            self.headers[name] = results
