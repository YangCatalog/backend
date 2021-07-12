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
import sys
import datetime
from subprocess import run

import utility.log as log

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


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
        parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                            help='Set path to config file')

        self.args, extra_args = parser.parse_known_args()
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
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(args.config_path)
    log_directory = config.get('Directory-Section', 'logs')
    cache_dir = config.get('Directory-Section', 'cache')
    db_host = config.get('DB-Section', 'host')
    db_name = config.get('DB-Section', 'name-users')
    db_user = config.get('DB-Section', 'user')
    db_pass = config.get('Secrets-Section', 'mysql-password')
    LOGGER = log.get_logger('mariadbRecovery', '{}/yang.log'.format(log_directory))
    backup_directory = '{}/{}'.format(cache_dir, 'mariadb')
    if not args.load:
        if not args.dir:
            args.dir = str(datetime.datetime.utcnow()).split('.')[0].replace(' ', '_') + '-UTC'
        run(['mydumper', '--database', db_name, '--outputdir', '{}/{}'.format(backup_directory, args.dir),
             '--host', db_host, '--user', db_user, '--password', db_pass, '--lock-all-tables'])
    else:
        if not args.dir:
            LOGGER.error('Load directory must be specified')
            return
        cmd = ['myloader', '--database', db_name, '--directory', '{}/{}'.format(backup_directory, args.dir),
               '--host', db_host, '--user', db_user, '--password', db_pass]
        if args.overwrite_tables:
            cmd.append('--overwrite-tables')
        run(cmd)
            


if __name__ == '__main__':
    main()
