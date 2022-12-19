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

import utility.log as log
from parseAndPopulate.modulesComplicatedAlgorithms import ModulesComplicatedAlgorithms
from utility.create_config import create_config
from utility.fetch_modules import fetch_modules
from utility.scriptConfig import BaseScriptConfig
from utility.staticVariables import JobLogStatuses
from utility.util import job_log

current_file_basename = os.path.basename(__file__)


class ScriptConfig(BaseScriptConfig):
    def __init__(self):
        help = 'Resolve the tree-type for modules that are no longer the latest revision. Runs as a daily cronjob.'
        super().__init__(help, None, [])


def main(script_conf: BaseScriptConfig = ScriptConfig()):
    start_time = int(time.time())

    config = create_config()
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    yang_models = config.get('Directory-Section', 'yang-models-dir', fallback='/var/yang/nonietf/yangmodels/yang')
    credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
    json_ytree = config.get('Directory-Section', 'json-ytree', fallback='/var/yang/ytrees')
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    logger = log.get_logger('revise_tree_type', f'{log_directory}/parseAndPopulate.log')
    logger.info('Starting Cron job for revise_tree_type')
    job_log(start_time, temp_dir, status=JobLogStatuses.IN_PROGRESS, filename=current_file_basename)
    direc = '/var/yang/tmp'

    complicated_algorithms = ModulesComplicatedAlgorithms(
        log_directory,
        yangcatalog_api_prefix,
        credentials,
        save_file_dir,
        direc,
        {},
        yang_models,
        temp_dir,
        json_ytree,
    )

    modules_revise = []
    logger.info('Fetching all of the modules from API.')
    try:
        modules = fetch_modules(logger, config=config)
    except RuntimeError:
        job_log(
            start_time,
            temp_dir,
            current_file_basename,
            error='Failed to fetch modules from API.',
            status=JobLogStatuses.FAIL,
        )
        return

    for module in modules:
        if module.get('tree-type') != 'nmda-compatible':
            continue
        if not complicated_algorithms.check_if_latest_revision(module):
            modules_revise.append(module)
    logger.info(f'Resolving tree-types for {len(modules_revise)} modules')
    complicated_algorithms.resolve_tree_type(modules_revise)
    complicated_algorithms.populate()
    logger.info('Job finished successfully')
    job_log(start_time, temp_dir, current_file_basename, status=JobLogStatuses.SUCCESS)


if __name__ == '__main__':
    main()
