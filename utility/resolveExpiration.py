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
from utility.util import job_log


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'Resolve expiration metadata for each module and set it to Redis if changed. ' \
            'This runs as a daily cronjob'

        super().__init__(help, None, None if __name__ == '__main__' else [])


def __expired_change(expired_from_module: t.Optional[str], expired_from_datatracker: t.Union[str, bool]) -> bool:
    return expired_from_module != expired_from_datatracker


def __expires_change(expires_from_module: t.Optional[str], expires_from_datatracker: t.Optional[str]) -> bool:
    expires_changed = expires_from_module != expires_from_datatracker

    if expires_changed:
        if expires_from_module is None or expires_from_datatracker is None:
            return expires_changed
        # If both values are represented by datetime, compare datetime objets
        elif len(expires_from_module) > 0 and len(expires_from_datatracker) > 0:
            date_format = '%Y-%m-%dT%H:%M:%S'
            return datetime.strptime(expires_from_module[0:19], date_format) != datetime.strptime(expires_from_datatracker[0:19], date_format)

    return expires_changed


def resolve_expiration(module: dict, LOGGER: logging.Logger, datatracker_failures: list,
                       redis_connection: RedisConnection):
    """Walks through all the modules and updates them if necessary

    Arguments:
        :param module               (dict) Module with all the metadata
        :param LOGGER               (logging.Logger) formated logger with the specified name
        :param datatracker_failures (list) list of url that failed to get data from Datatracker
        :param redis_connection     (RedisConnection) Connection used to communication with Redis
    """
    reference = module.get('reference')
    expired = 'not-applicable'
    expires = None
    if module.get('maturity-level') == 'ratified':
        expired = False
        expires = None
    if reference is not None and 'datatracker.ietf.org' in reference:
        ref = reference.split('/')[-1]
        rev = None
        if ref.isdigit():
            ref = reference.split('/')[-2]
            rev = reference.split('/')[-1]
        url = ('https://datatracker.ietf.org/api/v1/doc/document/?name={}&states__type=draft&states__slug__in=active,RFC&format=json'.format(ref))
        retry = 6
        while True:
            try:
                response = requests.get(url)
                break
            except Exception as e:
                retry -= 1
                LOGGER.warning('Failed to fetch file content of {}'.format(ref))
                time.sleep(10)
                if retry == 0:
                    LOGGER.error('Failed to fetch file content of {} for 6 times in a row - SKIPPING.'.format(ref))
                    LOGGER.error(e)
                    datatracker_failures.append(url)
                    return None

        if response.status_code == 200:
            data = response.json()
            objs = data.get('objects', [])
            if len(objs) == 1:
                if rev == objs[0].get('rev'):
                    rfc = objs[0].get('rfc')
                    if rfc is None:
                        expires = objs[0]['expires']
                        expired = False
                    else:
                        expired = True
                        expires = None
                else:
                    expired = True
                    expires = None
            else:
                expired = True
                expires = None

    expired_changed = __expired_change(module.get('expired'), expired)
    expires_changed = __expires_change(module.get('expires'), expires)

    if expires_changed or expired_changed:
        yang_name_rev = '{}@{}'.format(module['name'], module['revision'])
        LOGGER.info('Module {} changing expiration\nFROM: expires: {} expired: {}\nTO: expires: {} expired: {}'
                    .format(yang_name_rev, module.get('expires'), module.get('expired'), expires, expired))

        if expires is not None:
            module['expires'] = expires
        module['expired'] = expired

        if expires is None and module.get('expires') is not None:
            # If the 'expires' property no longer contains a value,
            # delete request need to be done to the Redis to the 'expires' property
            result = redis_connection.delete_expires(module)
            module.pop('expires', None)

            if result:
                LOGGER.info('expires property removed from {}'.format(yang_name_rev))
            else:
                LOGGER.error('Error while removing expires property from {}'.format(yang_name_rev))
        return True
    else:
        return False


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()

    config = create_config()
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='user password').strip('"').split()
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    LOGGER = log.get_logger('resolveExpiration', '{}/jobs/resolveExpiration.log'.format(log_directory))

    revision_updated_modules = 0
    datatracker_failures = []

    redis_connection = RedisConnection()
    LOGGER.info('Starting Cron job resolve modules expiration')
    try:
        LOGGER.info('Requesting all the modules from {}'.format(yangcatalog_api_prefix))
        updated = False

        response = requests.get('{}/search/modules'.format(yangcatalog_api_prefix))
        if response.status_code < 200 or response.status_code > 299:
            LOGGER.error('Request on path {} failed with {}'
                         .format(yangcatalog_api_prefix, response.text))
        else:
            LOGGER.debug('{} modules fetched from {} successfully'
                         .format(len(response.json().get('module', [])), yangcatalog_api_prefix))
        modules = response.json().get('module', [])
        i = 1
        for module in modules:
            LOGGER.debug('{} out of {}'.format(i, len(modules)))
            i += 1
            ret = resolve_expiration(module, LOGGER, datatracker_failures, redis_connection)
            if ret:
                revision_updated_modules += 1
            if not updated:
                updated = ret
        if updated:
            redis_connection.populate_modules(modules)
            url = ('{}/load-cache'.format(yangcatalog_api_prefix))
            response = requests.post(url, None, auth=(credentials[0], credentials[1]))
            LOGGER.info('Cache loaded with status {}'.format(response.status_code))
    except Exception as e:
        LOGGER.exception('Exception found while running resolveExpiration script')
        job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
        raise e
    if len(datatracker_failures) > 0:
        LOGGER.debug('Following references failed to get from the datatracker:\n {}'
                     .format('\n'.join(datatracker_failures)))
    messages = [
        {'label': 'Modules with changed revison', 'message': revision_updated_modules},
        {'label': 'Datatracker modules failures', 'message': len(datatracker_failures)}
    ]
    job_log(start_time, temp_dir, messages=messages, status='Success', filename=os.path.basename(__file__))
    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
