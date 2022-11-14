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
Python script which will try out GET, PATCH and DELETE requests
to ConfD database. Result of the script run will be logged into
cronjob.json. This result then may be viewed in Admin UI.
"""

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

import json
import os
import random
import string
import time

import utility.log as log
from redisConnections.redisConnection import RedisConnection
from utility import confdService
from utility.create_config import create_config
from utility.staticVariables import JobLogStatuses
from utility.util import job_log

current_file_basename = os.path.basename(__file__)

if __name__ == '__main__':
    start_time = int(time.time())
    config = create_config()
    credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
    logs_dir = config.get('Directory-Section', 'logs')
    temp_dir = config.get('Directory-Section', 'temp')

    LOGGER = log.get_logger('healthcheck', os.path.join(logs_dir, 'healthcheck.log'))
    messages = []
    letters = string.ascii_letters
    suffix = ''.join(random.choice(letters) for _ in range(6))
    check_module_name = f'confd-full-check-{suffix}'
    confdService = confdService.ConfdService()
    confdService.delete_modules()
    confdService.delete_vendors()

    LOGGER.info('Running confdFullCheck')
    job_log(start_time, temp_dir, status=JobLogStatuses.IN_PROGRESS, filename=current_file_basename)
    try:
        redisConnection = RedisConnection()
        yang_catalog_module = redisConnection.get_module('yang-catalog@2018-04-03/ietf')
        module = json.loads(yang_catalog_module)
        error = confdService.patch_modules([module])

        if error:
            LOGGER.error('Error occurred while patching yang-catalog@2018-04-03/ietf module')
        else:
            LOGGER.info('yang-catalog@2018-04-03/ietf patched successfully')

        # Change module name to be used only for this check - to not affect real module
        module['name'] = check_module_name

        # PATCH
        result = {'label': f'PATCH {check_module_name}@2018-04-03'}
        errors = confdService.patch_modules([module])

        if not errors:
            result['message'] = 'OK'
        else:
            LOGGER.info(f'Cannot add {check_module_name}@2018-04-03 module to ConfD')
            result['message'] = 'NOT OK'
        messages.append(result)

        # GET 2
        result = {'label': f'GET {check_module_name}@2018-04-03'}
        new_module_key = f'{check_module_name},2018-04-03,ietf'
        response = confdService.get_module(new_module_key)

        if response.status_code == 200:
            result['message'] = f'{response.status_code} OK'
        else:
            LOGGER.info(f'Cannot get {check_module_name}@2018-04-03 module from ConfD')
            result['message'] = f'{response.status_code} NOT OK'
        messages.append(result)

        # DELETE
        result = {'label': f'DELETE {response.status_code}@2018-04-03'}
        response = confdService.delete_module(new_module_key)

        if response.status_code == 204:
            result['message'] = f'{response.status_code} OK'
        else:
            LOGGER.info(f'Cannot delete {check_module_name}@2018-04-03 module from ConfD')
            result['message'] = f'{response.status_code} NOT OK'
        messages.append(result)

        # GET 3
        # NOTE: Module should already be removed - 404 status code is expected
        result = {'label': f'GET 2 {check_module_name}@2018-04-03'}
        response = confdService.get_module(new_module_key)

        if response.status_code == 404:
            result['message'] = f'{response.status_code} OK'
        else:
            LOGGER.info(f'Module {check_module_name}@2018-04-03 already in ConfD')
            result['message'] = f'{response.status_code} NOT OK'
        messages.append(result)

        job_log(start_time, temp_dir, messages=messages, status=JobLogStatuses.SUCCESS, filename=current_file_basename)

    except Exception as e:
        LOGGER.exception(e)
        job_log(start_time, temp_dir, error=str(e), status=JobLogStatuses.FAIL, filename=current_file_basename)
