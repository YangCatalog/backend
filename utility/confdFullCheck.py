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

__author__ = "Slavomir Mazur"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "slavomir.mazur@pantheon.tech"

import json
import os
import random
import string
import time

import requests

import utility.log as log
from utility.staticVariables import confd_headers
from utility.util import create_config, job_log

if __name__ == '__main__':
    start_time = int(time.time())
    config = create_config()
    confd_protocol = config.get('Web-Section', 'protocol', fallback='http')
    confd_ip = config.get('Web-Section', 'confd-ip', fallback='localhost')
    confd_port = int(config.get('Web-Section', 'confd-port', fallback=8008))
    credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
    logs_dir = config.get('Directory-Section', 'logs')
    temp_dir = config.get('Directory-Section', 'temp')

    LOGGER = log.get_logger('healthcheck', '{}/healthcheck.log'.format(logs_dir))
    messages = []
    letters = string.ascii_letters
    suffix = ''.join(random.choice(letters) for i in range(6))
    check_module_name = 'confd-full-check-{}'.format(suffix)
    confd_prefix = '{}://{}:{}'.format(confd_protocol, confd_ip, repr(confd_port))

    LOGGER.info('Running confdFullCheck')
    try:
        # GET
        result = {}
        result['label'] = 'GET yang-catalog@2018-04-03'
        url = '{}/restconf/data/yang-catalog:catalog/modules/module=yang-catalog,2018-04-03,ietf'.format(confd_prefix)
        response = requests.get(url, auth=(credentials[0], credentials[1]), headers=confd_headers)
        if response.status_code == 200:
            module = json.loads(response.text)
            result['message'] = '{} OK'.format(response.status_code)
        else:
            LOGGER.info('Cannot get yang-catalog@2018-04-03 module from ConfD')
            result['message'] = '{} NOT OK'.format(response.status_code)
        messages.append(result)

        # Change module name to be used only for this check - to not affect real module
        module['yang-catalog:module'][0]['name'] = check_module_name

        # PATCH
        result = {}
        result['label'] = 'PATCH {}@2018-04-03'.format(check_module_name)
        url = '{}/restconf/data/yang-catalog:catalog/modules/'.format(confd_prefix)
        json_modules_data = json.dumps({'modules': {'module': module['yang-catalog:module'][0]}})
        response = requests.patch(url, data=json_modules_data,
                                  auth=(credentials[0], credentials[1]), headers=confd_headers)
        if response.status_code == 204:
            result['message'] = '{} OK'.format(response.status_code)
        else:
            LOGGER.info('Cannot add {}@2018-04-03 module to ConfD'.format(check_module_name))
            result['message'] = '{} NOT OK'.format(response.status_code)
        messages.append(result)

        # GET 2
        result = {}
        result['label'] = 'GET {}@2018-04-03'.format(check_module_name)
        url = '{}/restconf/data/yang-catalog:catalog/modules/module={},2018-04-03,ietf'.format(confd_prefix, check_module_name)
        response = requests.get(url, auth=(credentials[0], credentials[1]), headers=confd_headers)
        if response.status_code == 200:
            result['message'] = '{} OK'.format(response.status_code)
        else:
            LOGGER.info('Cannot get {}@2018-04-03 module from ConfD'.format(check_module_name))
            result['message'] = '{} NOT OK'.format(response.status_code)
        messages.append(result)

        # DELETE
        result = {}
        result['label'] = 'DELETE {}@2018-04-03'.format(check_module_name)
        url = '{}/restconf/data/yang-catalog:catalog/modules/module={},2018-04-03,ietf'.format(confd_prefix, check_module_name)
        response = requests.delete(url, auth=(credentials[0], credentials[1]), headers=confd_headers)
        if response.status_code == 204:
            result['message'] = '{} OK'.format(response.status_code)
        else:
            LOGGER.info('Cannot delete {}@2018-04-03 module from ConfD'.format(check_module_name))
            result['message'] = '{} NOT OK'.format(response.status_code)
        messages.append(result)

        # GET 3
        # NOTE: Module should already be removed - 404 status code is expected
        result = {}
        result['label'] = 'GET 2 {}@2018-04-03'.format(check_module_name)
        url = '{}/restconf/data/yang-catalog:catalog/modules/module={},2018-04-03,ietf'.format(confd_prefix, check_module_name)
        response = requests.get(url, auth=(credentials[0], credentials[1]), headers=confd_headers)
        if response.status_code == 404:
            result['message'] = '{} OK'.format(response.status_code)
        else:
            LOGGER.info('Module {}@2018-04-03 already in ConfD'.format(check_module_name))
            result['message'] = '{} NOT OK'.format(response.status_code)
        messages.append(result)

        job_log(start_time, temp_dir, messages=messages, status='Success', filename=os.path.basename(__file__))

    except Exception as e:
        LOGGER.error(e)
        job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
