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

    def __init__(self, private_dir: str, log_directory: str):
        """
        Preset LoadFiles class to load all .json files from private directory.
        Filenames of json files are stored in json_links file.

        :param private_dir      (str) path to the directory with private HTML result files
        :param log_directory:   (str) directory where the log file is saved
        """
        LOGGER = log.get_logger(__name__, '{}/parseAndPopulate.log'.format(log_directory))
        LOGGER.debug('Loading compilation statuses and results')
        excluded_names = ['private', 'IETFCiscoAuthorsYANGPageCompilation']

        self.names = self.load_names(private_dir, LOGGER)
        self.names = [name for name in self.names if name not in excluded_names]
        self.status = {}
        self.headers = {}

        for name in self.names:
            try:
                with open('{}/{}.json'.format(private_dir, name), 'r') as f:
                    self.status[name] = json.load(f)
            except FileNotFoundError:
                self.status[name] = {}
                LOGGER.exception('{}/{}.json file was not found'.format(private_dir, name))
            if name == 'IETFYANGRFC':
                try:
                    with open('{}/{}.html'.format(private_dir, name), 'r') as f:
                        html = f.read()
                except FileNotFoundError:
                    html = ''
                    LOGGER.exception('{}/{}.html file was not found'.format(private_dir, name))
            else:
                try:
                    with open('{}/{}YANGPageCompilation.html'.format(private_dir, name), 'r') as f:
                        html = f.read()
                except FileNotFoundError:
                    html = ''
                    LOGGER.exception('{}/{}YANGPageCompilation.html file was not found'.format(private_dir, name))
            ths = html.split('<TH>')
            results = []
            for th in ths:
                result = th.split('</TH>')[0]
                if 'Compilation Result' in result:
                    results.append(result)
            self.headers[name] = results
        LOGGER.debug('Compilation statuses and results loaded successfully')

    def load_names(self, private_dir: str, LOGGER):
        """ Load list of names of json files from json_links file.
        """
        names = []
        try:
            with open('{}/json_links'.format(private_dir), 'r') as f:
                for line in f:
                    names.append(line.replace('.json', '').replace('\n', ''))
        except FileNotFoundError:
            LOGGER.exception('json_links file was not found')

        return names
