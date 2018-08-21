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

import fnmatch
import os

import utility.log as lo
from utility import yangParser

LOGGER = lo.get_logger('util')


def get_curr_dir(f):
    """Get current working directory

            :return path to current directory
    """
    LOGGER.debug('{}'.format(os.getcwd()))
    return os.getcwd()


def find_first_file(directory, pattern, pattern_with_revision):
    """Find first yang file based on name or name and revision

            :param directory: (str) directory where to look
                for a file
            :param pattern: (str) name of the yang file
            :param pattern_with_revision: name and revision
                of the in format <name>@<revision>
            :return path to current directory
    """
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern_with_revision):
                filename = os.path.join(root, basename)
                return filename
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                try:
                    revision = yangParser.parse(filename).search('revision')[0]\
                        .arg
                except:
                    revision = '1970-01-01'
                if '*' not in pattern_with_revision:
                    if revision in pattern_with_revision:
                        return filename
                else:
                    return filename
