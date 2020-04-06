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
This script is run by a cronjob every day and it
automatically removes unused diff files, yangsuite
users and correlation ids.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import datetime
import glob
import hashlib
import os
import shutil
import sys
import time
from operator import itemgetter
from os import unlink

import utility.log as lo
from dateutil.parser import parse

from elasticsearch import Elasticsearch

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


def create_register_elk_repo(name, is_compress, elk):
    body = {}
    body['type'] = 'fs'
    body['settings'] = {}
    body['settings']['location'] = name
    body['settings']['compress'] = is_compress
    elk.snapshot.create_repository(name, body)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')
    parser.add_argument('--compress', action='store_true', default=True,
                        help='Set weather to compress snapshot files. Default is True')
    args = parser.parse_args()
    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    temp_dir = config.get('Directory-Section', 'temp')
    ys_users = config.get('Directory-Section', 'ys_users')
    cache_directory = config.get('Directory-Section', 'cache')
    LOGGER = lo.get_logger('removeUnused', log_directory + '/jobs/removeUnused.log')
    LOGGER.info('Removing unused files')
    current_time = time.time()
    cutoff = current_time - 86400
    LOGGER.info('Removing old tmp directory representing int files')
    for dir in next(os.walk(temp_dir))[1]:
        if represents_int(dir):
            creation_time = os.path.getctime('{}/{}'.format(temp_dir, dir))
            if creation_time < cutoff:
                shutil.rmtree('{}/{}'.format(temp_dir, dir))

    LOGGER.info('Removing old ys temporary users')
    dirs = os.listdir(ys_users)
    for dir in dirs:
        abs = os.path.abspath('{}/{}'.format(ys_users, dir))
        if not abs.endswith('yangcat') and not abs.endswith('yang'):
            try:
                shutil.rmtree(abs)
            except:
                pass

    LOGGER.info('Removing old correlation ids')
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
    create_register_elk_repo(repo_name, args.compress, es)
    snapshots = es.snapshot.get(repository=repo_name, snapshot='_all')['snapshots']
    sorted_snapshots = sorted(snapshots, key=itemgetter('start_time_in_millis'))

    for snapshot in sorted_snapshots[:-5]:
        es.snapshot.delete(repository=repo_name, snapshot=snapshot['snapshot'])

    # remove  all files that are same keep the latest one only. Last two months keep all different content json files
    # other 4 months (6 in total) keep only latest, remove all other files
    LOGGER.info('Removing old cache json files')
    list_of_files = glob.glob(cache_directory + '/*')
    list_of_files = [i.split('/')[-1][:-5].replace('_', ' ')[:-4] for i in list_of_files]
    list_of_dates = []
    for f in list_of_files:
        try:
            datetime_parsed = parse(f)
            file_name = '{}/{}-UTC.json'.format(cache_directory, f.replace(' ', '_'))
            if os.stat(file_name).st_size == 0:
                continue
            list_of_dates.append(datetime_parsed)
        except ValueError as e:
            pass
    list_of_dates = sorted(list_of_dates)
    file_name_latest = '{}/{}-UTC.json'.format(cache_directory, str(list_of_dates[-1]).replace(' ', '_'))

    def diff_month(later_datetime, earlier_datetime):
        return (later_datetime.year - earlier_datetime.year) * 12 + later_datetime.month - earlier_datetime.month

    def hash_file(date_time):
        json_file = '{}/{}-UTC.json'.format(cache_directory, str(date_time).replace(' ', '_'))

        buf_size = 65536  # lets read stuff in 64kb chunks!

        sha1 = hashlib.sha1()

        with open(json_file, 'rb') as f2:
            while True:
                data = f2.read(buf_size)
                if not data:
                    break
                sha1.update(data)

        return sha1.hexdigest()


    to_remove = []
    last_six_months = {}
    last_two_months = {}

    for date_file in list_of_dates:
        today = datetime.datetime.now()
        month_difference = diff_month(today, date_file)
        if month_difference > 6:
            to_remove.append(date_file)
        elif month_difference > 2:
            month = date_file.month
            if last_six_months.get(month) is not None:
                if last_six_months.get(month) > date_file:
                    to_remove.append(date_file)
                else:
                    to_remove.append(last_six_months.get(month))
                    last_six_months[month] = date_file
            else:
                last_six_months[month] = date_file
        else:
            currently_processed_file_hash = hash_file(date_file)
            if last_two_months.get(currently_processed_file_hash) is not None:
                if last_two_months.get(currently_processed_file_hash) > date_file:
                    to_remove.append(date_file)
                else:
                    to_remove.append(last_two_months.get(currently_processed_file_hash))
            last_two_months[currently_processed_file_hash] = date_file
    for remove in to_remove:
        json_file_to_remove = '{}/{}-UTC.json'.format(cache_directory, str(remove).replace(' ', '_'))
        if json_file_to_remove != file_name_latest:
            unlink(json_file_to_remove)
    LOGGER.info('Finished with script removeUnused.py')

