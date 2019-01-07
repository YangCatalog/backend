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
import time
from operator import itemgetter

from elasticsearch import Elasticsearch

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import datetime
import os
import shutil

import utility.log as lo

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


def represents_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    temp_dir = config.get('Directory-Section', 'temp')
    ys_users = config.get('Directory-Section', 'ys_users')
    LOGGER = lo.get_logger('removeUnused', log_directory + '/jobs/removeUnused.log')
    LOGGER.info('Removing unused files')
    current_time = time.time()
    cutoff = current_time - 86400
    for dir in next(os.walk(temp_dir))[1]:
        if represents_int(dir):
            creation_time = os.path.getctime('{}/{}'.format(temp_dir, dir))
            if creation_time < cutoff:
                shutil.rmtree('{}/{}'.format(temp_dir, dir))

    dirs = os.listdir(ys_users)
    for dir in dirs:
        abs = os.path.abspath('{}/{}'.format(ys_users, dir))
        if not abs.endswith('yangcat') and not abs.endswith('yang'):
            try:
                shutil.rmtree(abs)
            except:
                pass

    # removing correlation ids from file that are older than a day
    # Be lenient to missing files
    try:
        f = open('{}/correlation_ids'.format(temp_dir), 'r')
        lines = f.readlines()
        f.close()
    except IOError:
        lines = []
    with open('{}/correlation_ids'.format(temp_dir), 'w') as f:
        for line in lines:
            line_datetime = line.split(' -')[0]
            t = datetime.datetime.strptime(line_datetime,
                                           "%a %b %d %H:%M:%S %Y")
            diff = datetime.datetime.now() - t
            if diff.days == 0:
                f.write(line)
    LOGGER.info('Removing old elasticsearch snapshots')
    repo_name = config.get('General-Section', 'elk-repo-name')

    es_host = config.get('DB-Section', 'es-host')
    es_port = config.get('DB-Section', 'es-port')
    es = Elasticsearch([{'host': '{}'.format(es_host), 'port': es_port}])
    snapshots = es.snapshot.get(repository=repo_name, snapshot='_all')['snapshots']
    sorted_snapshots = sorted(snapshots, key=itemgetter('start_time_in_millis'))

    for snapshot in sorted_snapshots[:-5]:
        es.snapshot.delete(repository=repo_name, snapshot=snapshot['snapshot'])
    LOGGER.info('Finished with script removeUnused.py')

