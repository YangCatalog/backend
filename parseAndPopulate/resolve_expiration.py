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
This script is run by a cronjob and it
finds all the modules that have expiration
metadata and updates them based on a date to
expired if it is necessary
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import os
import time

import requests

import utility.log as log
from parseAndPopulate.resolvers.expiration import ExpirationResolver
from redisConnections.redisConnection import RedisConnection
from utility.create_config import create_config
from utility.fetch_modules import fetch_modules
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import BaseScriptConfig
from utility.staticVariables import JobLogStatuses
from utility.util import job_log

help = script_config_dict['resolve_expiration']['help']
DEFAULT_SCRIPT_CONFIG = BaseScriptConfig(help, None, None if __name__ == '__main__' else [])
current_file_basename = os.path.basename(__file__)


def main(script_conf: BaseScriptConfig = DEFAULT_SCRIPT_CONFIG):
    start_time = int(time.time())

    config = create_config()
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='user password').strip('"').split()
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    logger = log.get_logger('resolve_expiration', f'{log_directory}/jobs/resolve_expiration.log')
    job_log(start_time, temp_dir, status=JobLogStatuses.IN_PROGRESS, filename=current_file_basename)

    revision_updated_modules = 0
    datatracker_failures = []

    redis_connection = RedisConnection(config=config)
    logger.info('Starting Cron job resolve modules expiration')
    try:
        logger.info(f'Fetching all the modules from {yangcatalog_api_prefix}')
        updated = False

        modules = fetch_modules(logger, config=config)

        logger.debug('Starting to resolve modules')
        for module in modules:
            exp_res = ExpirationResolver(module, logger, datatracker_failures, redis_connection)
            ret = exp_res.resolve()
            if ret:
                revision_updated_modules += 1
            if not updated:
                updated = ret
        logger.debug('All modules resolved')
        if updated:
            redis_connection.populate_modules(modules)
            url = f'{yangcatalog_api_prefix}/load-cache'
            response = requests.post(url, None, auth=(credentials[0], credentials[1]))
            logger.info(f'Cache loaded with status {response.status_code}')
    except Exception as e:
        logger.exception('Exception found while running resolve_expiration script')
        job_log(start_time, temp_dir, error=str(e), status=JobLogStatuses.FAIL, filename=current_file_basename)
        raise e
    if len(datatracker_failures) > 0:
        datatracker_failures_to_write = '\n'.join(datatracker_failures)
        logger.debug(f'Following references failed to get from the datatracker:\n{datatracker_failures_to_write}')
    messages = [
        {'label': 'Modules with changed revison', 'message': revision_updated_modules},
        {'label': 'Datatracker modules failures', 'message': len(datatracker_failures)},
    ]
    job_log(start_time, temp_dir, messages=messages, status=JobLogStatuses.SUCCESS, filename=current_file_basename)
    logger.info('Job finished successfully')


if __name__ == '__main__':
    main()
