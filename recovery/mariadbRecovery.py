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

"""
This script will backup or restore the entire yang_catalog database
stored in mariadb.
"""

__author__ = "Richard Zilincik"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "richard.zilincik@pantheon.tech"

import argparse
import datetime
import os
from subprocess import run
from utility.staticVariables import backup_date_format
from utility.util import get_list_of_backups
from utility.create_config import create_config

import utility.log as log


class ScriptConfig:
    def __init__(self):
        self.help = 'Backup script for the mariadb'
        parser = argparse.ArgumentParser(description=self.help)
        type = parser.add_mutually_exclusive_group()
        parser.add_argument('--dir', default='', help='Set name of the backup directory')
        type.add_argument('--save', action='store_true', default=True,
                          help='Set whether you want to create snapshot. Default is True')
        type.add_argument('--load', action='store_true', default=False,
                          help='Set whether you want to load from snapshot. Default is False')
        parser.add_argument('--overwrite-tables', default=False,
                            help='Overwrite tables when loading')
        parser.add_argument('--config-path', type=str, default=os.environ['YANGCATALOG_CONFIG_PATH'],
                            help='Set path to config file')

        self.args, _ = parser.parse_known_args()
        self.defaults = [parser.get_default(key) for key in self.args.__dict__.keys()]

    def get_args_list(self):
        args_dict = {}
        keys = [key for key in self.args.__dict__.keys()]
        types = [type(value).__name__ for value in self.args.__dict__.values()]

        i = 0
        for key in keys:
            args_dict[key] = dict(type=types[i], default=self.defaults[i])
            i += 1
        return args_dict

    def get_help(self):
        ret = {}
        ret['help'] = self.help
        ret['options'] = {}
        ret['options']['dir'] = 'Set name of the backup directory'
        ret['options']['save'] = 'Set whether you want to create directory. Default is True'
        ret['options']['load'] = 'Set whether you want to load from directory. Default is False'
        ret['options']['overwrite_tables'] = 'Overwrite tables when loading'
        ret['options']['config_path'] = 'Set path to config file'
        return ret


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    config = create_config(args.config_path)
    log_directory = config.get('Directory-Section', 'logs')
    cache_dir = config.get('Directory-Section', 'cache')
    db_host = config.get('DB-Section', 'host')
    db_name = config.get('DB-Section', 'name-users')
    db_user = config.get('DB-Section', 'user')
    db_pass = config.get('Secrets-Section', 'mysql-password')
    LOGGER = log.get_logger('mariadbRecovery', os.path.join(log_directory, 'yang.log'))
    backup_directory = os.path.join(cache_dir, 'mariadb')
    if not args.load:
        LOGGER.info('Starting backup of MariaDB')
        if not args.dir:
            args.dir = datetime.datetime.utcnow().strftime(backup_date_format)
        output_dir = '{}/{}'.format(backup_directory, args.dir)
        os.makedirs(output_dir, exist_ok=True)
        run(['mydumper', '--database', db_name, '--outputdir', output_dir,
             '--host', db_host, '--user', db_user, '--password', db_pass, '--lock-all-tables'])
    else:
        LOGGER.info('Starting load of MariaDB')
        args.dir = args.dir or '.'.join(get_list_of_backups(backup_directory)[-1])
        cmd = ['myloader', '--database', db_name, '--directory', os.path.join(backup_directory, args.dir),
               '--host', db_host, '--user', db_user, '--password', db_pass]
        if args.overwrite_tables:
            LOGGER.info('Overwriting existing tables')
            cmd.append('--overwrite-tables')
        run(cmd)
    LOGGER.info('Job completed successfully')


if __name__ == '__main__':
    main()
