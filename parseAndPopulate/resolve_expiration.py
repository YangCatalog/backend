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


import logging
import os
import time
import typing as t
from datetime import datetime

import requests
from redisConnections.redisConnection import RedisConnection

import utility.log as log
from utility.create_config import create_config
from utility.scriptConfig import BaseScriptConfig
from utility.staticVariables import JobLogStatuses
from utility.util import job_log

from parseAndPopulate.resolvers.expiration import ExpirationResolver

current_file_basename = os.path.basename(__file__)


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'Resolve expiration metadata for each module and set it to Redis if changed. ' \
            'This runs as a daily cronjob'

        super().__init__(help, None, None if __name__ == '__main__' else [])


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()

    config = create_config()
    credentials = config.get('Secrets-Section', 'confd-credentials',
                             fallback='user password').strip('"').split()
    log_directory = config.get(
        'Directory-Section', 'logs', fallback='/var/yang/logs')
    temp_dir = config.get('Directory-Section', 'temp',
                          fallback='/var/yang/tmp')
    yangcatalog_api_prefix = config.get(
        'Web-Section', 'yangcatalog-api-prefix')

    LOGGER = log.get_logger('resolve_expiration',
                            f'{log_directory}/jobs/resolve_expiration.log')
    job_log(start_time, temp_dir, status=JobLogStatuses.IN_PROGRESS,
            filename=current_file_basename)

    revision_updated_modules = 0
    datatracker_failures = []

    redis_connection = RedisConnection()
    LOGGER.info('Starting Cron job resolve modules expiration')
    try:
        LOGGER.info(
            f'Requesting all the modules from {yangcatalog_api_prefix}')
        updated = False

        response = requests.get(f'{yangcatalog_api_prefix}/search/modules')
        if response.status_code < 200 or response.status_code > 299:
            LOGGER.error(
                f'Request on path {yangcatalog_api_prefix} failed with {response.text}')
        else:
            LOGGER.debug(
                f'{len(response.json().get("module", []))} modules fetched from {yangcatalog_api_prefix} successfully')
        modules = response.json().get('module', [])
        for i, module in enumerate(modules, 1):
            LOGGER.debug(f'{i} out of {len(modules)}')
            exp_res = ExpirationResolver(
                module, LOGGER, datatracker_failures, redis_connection)
            ret = exp_res.resolve()
            if ret:
                revision_updated_modules += 1
            if not updated:
                updated = ret
        if updated:
            redis_connection.populate_modules(modules)
            url = f'{yangcatalog_api_prefix}/load-cache'
            response = requests.post(url, None, auth=(
                credentials[0], credentials[1]))
            LOGGER.info(f'Cache loaded with status {response.status_code}')
    except Exception as e:
        LOGGER.exception(
            'Exception found while running resolve_expiration script')
        job_log(start_time, temp_dir, error=str(e),
                status=JobLogStatuses.FAIL, filename=current_file_basename)
        raise e
    if len(datatracker_failures) > 0:
        datatracker_failures_to_write = '\n'.join(datatracker_failures)
        LOGGER.debug(
            f'Following references failed to get from the datatracker:\n{datatracker_failures_to_write}')
    messages = [
        {'label': 'Modules with changed revison',
            'message': revision_updated_modules},
        {'label': 'Datatracker modules failures',
            'message': len(datatracker_failures)}
    ]
    job_log(start_time, temp_dir, messages=messages,
            status=JobLogStatuses.SUCCESS, filename=current_file_basename)
    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
