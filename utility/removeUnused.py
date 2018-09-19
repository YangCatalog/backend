"""
This script is run by a cronjob every day and it
automatically removes unused diff files, yangsuite
users and correlation ids.
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
import sys

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import datetime
import math
import os
import shutil
import time

import utility.log as lo
from utility import messageFactory

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--remove-dir', type=str,
                        default='.',
                        help='Set path to config file')
    parser.add_argument('--remove-dir2', type=str,
                        default='.',
                        help='Set path to yangsuite users')
    parser.add_argument('--remove-dir3', type=str,
                        default='/home/miroslav/yangsuite-users/',
                        help='Set path to yangsuite saved users')
    parser.add_argument('--logs-path', type=str,
                        default='.',
                        help='Set path to config file')
    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    LOGGER = lo.get_logger('populate', log_directory + '/parseAndPopulate.log')
    mf = messageFactory.MessageFactory()
    LOGGER.info('Removing unused files')
    to_remove = []
    for root, dirs, files in os.walk(args.remove_dir):
        for fi_name in files:
            with open(args.logs_path, 'r') as f:
                remove = True
                for line in f:
                    if fi_name in line:
                        remove = False
                        break
                if remove:
                    remove_path = '{}/{}'.format(root, fi_name)
                    st = os.stat(remove_path)
                    c_time = st.st_ctime
                    c_time = time.time() - c_time
                    c_time = c_time / 60 / 60 / 24
                    if math.floor(c_time) != 0:
                        to_remove.append(remove_path)
    mf.send_removed_temp_diff_files()
    for remove in to_remove:
        try:
            os.remove(remove)
        except OSError as e:
            mf.send_automated_procedure_failed('Remove unused diff files',
                                               e.strerror)
    dirs = os.listdir(args.remove_dir2)
    for dir in dirs:
        abs = os.path.abspath('{}/{}'.format(args.remove_dir2, dir))
        if not abs.endswith('yangcat') and not abs.endswith('miott'):
            try:
                shutil.rmtree(abs)
            except:
                pass
    dirs = os.listdir(args.remove_dir3)
    for dir in dirs:
        abs = os.path.abspath('{}/{}'.format(args.remove_dir3, dir))
        if not abs.endswith('yangcatalog'):
            try:
                shutil.rmtree(abs)
            except:
                pass

    # removing correlation ids from file that are older than a day
    f = open('./../api/correlation_ids', 'r')
    lines = f.readlines()
    f.close()
    with open('./../api/correlation_ids', 'w') as f:
        for line in lines:
            line_datetime = line.split(' -')[0]
            t = datetime.datetime.strptime(line_datetime,
                                           "%a %b %d %H:%M:%S %Y")
            diff = datetime.datetime.now() - t
            if diff.days == 0:
                f.write(line)
    LOGGER.info('Finished with script removeUnused.py')
