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
This script is run by a cronjob. It searches for modules that
are no longer the latest revision and have tree-type nmda-compatible.
The tree-type for these modules is reevaluated.
"""

__author__ = "Richard Zilincik"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "richard.zilincik@pantheon.tech"

import configparser as ConfigParser
import os
import time

import requests
from parseAndPopulate.modulesComplicatedAlgorithms import \
    ModulesComplicatedAlgorithms

import utility.log as log
from utility.util import job_log


class ScriptConfig:

    def __init__(self):
        self.help = 'Resolve the tree-type for modules that are no longer the latest revision. ' \
                    'Runs as a daily cronjob.'
        config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(config_path)
        self.api_protocol = config.get('General-Section', 'protocol-api', fallback='http')
        self.ip = config.get('Web-Section', 'ip', fallback='localhost')
        self.api_port = int(config.get('Web-Section', 'api-port', fallback=5000))
        self.confd_protocol = config.get('Web-Section', 'protocol', fallback='http')
        self.confd_ip = config.get('Web-Section', 'confd-ip', fallback='localhost')
        self.confd_port = int(config.get('Web-Section', 'confd-port', fallback=8008))
        self.is_uwsgi = config.get('General-Section', 'uwsgi', fallback=True)
        self.temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
        self.log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
        self.save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
        self.yang_models = config.get('Directory-Section', 'yang-models-dir',
                                      fallback='/var/yang/nonietf/yangmodels/yang')
        self.credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
        self.json_ytree = config.get('Directory-Section', 'json-ytree', fallback='/var/yang/ytrees')

    def get_args_list(self):
        args_dict = {}
        return args_dict

    def get_help(self):
        ret = {}
        ret['help'] = self.help
        ret['options'] = {}
        return ret


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    log_directory = scriptConf.log_directory
    LOGGER = log.get_logger('reviseTreeType', '{}/parseAndPopulate.log'.format(log_directory))
    LOGGER.info('Starting Cron job for reviseTreeType')
    api_protocol = scriptConf.api_protocol
    ip = scriptConf.ip
    api_port = scriptConf.api_port
    is_uwsgi = scriptConf.is_uwsgi
    separator = ':'
    suffix = api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(api_protocol, ip, separator, suffix)
    credentials = scriptConf.credentials
    confd_protocol = scriptConf.confd_protocol
    confd_ip = scriptConf.confd_ip
    confd_port = scriptConf.confd_port
    confd_prefix = '{}://{}:{}'.format(confd_protocol, confd_ip, repr(confd_port))
    save_file_dir = scriptConf.save_file_dir
    direc = '/var/yang/tmp'
    yang_models = scriptConf.yang_models
    temp_dir = scriptConf.temp_dir
    json_ytree = scriptConf.json_ytree
    complicatedAlgorithms = ModulesComplicatedAlgorithms(log_directory, yangcatalog_api_prefix,
                                                         credentials, confd_prefix, save_file_dir,
                                                         direc, {}, yang_models, temp_dir,
                                                         json_ytree)
    response = requests.get('{}search/modules'.format(yangcatalog_api_prefix))
    if response.status_code != 200:
        LOGGER.error('Failed to fetch list of modules')
        job_log(start_time, temp_dir, os.path.basename(__file__), error=response.text, status='Fail')
        return
    modules_revise = []
    modules = response.json()['module']
    for module in modules:
        if module.get('tree-type') == 'nmda-compatible':
            if not complicatedAlgorithms.check_if_latest_revision(module):
                modules_revise.append(module)
    LOGGER.info('Resolving tree-types for {} modules'.format(len(modules_revise)))
    complicatedAlgorithms.resolve_tree_type({'module': modules_revise})
    complicatedAlgorithms.populate()
    LOGGER.info('Job finished successfully')
    job_log(start_time, temp_dir, os.path.basename(__file__), status='Success')


if __name__ == '__main__':
    main()
