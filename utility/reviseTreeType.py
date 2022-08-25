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

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'


import os
import time

import requests
from parseAndPopulate.modulesComplicatedAlgorithms import ModulesComplicatedAlgorithms

import utility.log as log
from utility.create_config import create_config
from utility.scriptConfig import BaseScriptConfig
from utility.staticVariables import JobLogStatuses
from utility.util import job_log

current_file_basename = os.path.basename(__file__)


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'Resolve the tree-type for modules that are no longer the latest revision. Runs as a daily cronjob.'
        super().__init__(help, None, [])


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    
    config = create_config()
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    yang_models = config.get('Directory-Section', 'yang-models-dir',
                             fallback='/var/yang/nonietf/yangmodels/yang')
    credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
    json_ytree = config.get('Directory-Section', 'json-ytree', fallback='/var/yang/ytrees')
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    LOGGER = log.get_logger('reviseTreeType', f'{log_directory}/parseAndPopulate.log')
    LOGGER.info('Starting Cron job for reviseTreeType')
    job_log(start_time, temp_dir, status=JobLogStatuses.IN_PROGRESS, filename=current_file_basename)
    direc = '/var/yang/tmp'

    complicated_algorithms = ModulesComplicatedAlgorithms(log_directory, yangcatalog_api_prefix,
                                                          credentials, save_file_dir,
                                                          direc, {}, yang_models, temp_dir,
                                                          json_ytree)
    response = requests.get(f'{yangcatalog_api_prefix}/search/modules')
    if response.status_code != 200:
        LOGGER.error('Failed to fetch list of modules')
        job_log(start_time, temp_dir, current_file_basename, error=response.text, status=JobLogStatuses.FAIL)
        return
    modules_revise = []
    modules = response.json()['module']
    for module in modules:
        if module.get('tree-type') != 'nmda-compatible':
            continue
        if not complicated_algorithms.check_if_latest_revision(module):
            modules_revise.append(module)
    LOGGER.info(f'Resolving tree-types for {len(modules_revise)} modules')
    complicated_algorithms.resolve_tree_type({'module': modules_revise})
    complicated_algorithms.populate()
    LOGGER.info('Job finished successfully')
    job_log(start_time, temp_dir, current_file_basename, status=JobLogStatuses.SUCCESS)


if __name__ == '__main__':
    main()
