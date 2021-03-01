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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import datetime
import json
import os
import sys
import time

import dateutil.parser
import requests
from dateutil.relativedelta import relativedelta
from urllib3.exceptions import NewConnectionError

import utility.log as log
from utility.util import job_log

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


class ScriptConfig:

    def __init__(self):
        config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(config_path)
        self.log_directory = config.get('Directory-Section', 'logs')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        self.__confd_protocol = config.get('General-Section', 'protocol-confd')
        self.__confd_port = config.get('Web-Section', 'confd-port')
        self.__confd_host = config.get('Web-Section', 'confd-ip')
        self.__api_protocol = config.get('General-Section', 'protocol-api')
        self.__api_port = config.get('Web-Section', 'api-port')
        self.__api_host = config.get('Web-Section', 'ip')
        credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
        self.help = 'Resolve expiration metadata for each module and set it to confd if changed. This runs as a daily' \
                    ' cronjob'
        parser = argparse.ArgumentParser()
        parser.add_argument('--credentials',
                            help='Set authorization parameters username password respectively.'
                                 ' Default parameters are {}'.format(str(credentials)), nargs=2,
                            default=credentials, type=str)
        parser.add_argument('--ip', default=self.__confd_host, type=str,
                            help='Set host address where the Confd is started. Default: ' + self.__confd_host)
        parser.add_argument('--port', default=self.__confd_port, type=int,
                            help='Set port where the Confd is started. Default: ' + self.__confd_port)
        parser.add_argument('--protocol', type=str, default=self.__confd_protocol,
                            help='Whether Confd runs on http or https. Default: ' + self.__confd_protocol)
        parser.add_argument('--api-ip', default=self.__api_host, type=str,
                            help='Set host address where the API is started. Default: ' + self.__api_host)
        parser.add_argument('--api-port', default=self.__api_port, type=int,
                            help='Set port where the API is started. Default: ' + self.__api_port)
        parser.add_argument('--api-protocol', type=str, default=self.__api_protocol,
                            help='Whether API runs on http or https. Default: ' + self.__api_protocol)
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
        ret['options']['ip'] = 'Set host address where the Confd is started. Default: ' + self.__confd_host
        ret['options']['port'] = 'Set port where the Confd is started. Default: ' + self.__confd_port
        ret['options']['protocol'] = 'Whether Confd runs on http or https. Default: ' + self.__confd_protocol
        ret['options']['api_ip'] = 'Set host address where the API is started. Default: ' + self.__api_host
        ret['options']['api_port'] = 'Set port where the API is started. Default: ' + self.__api_port
        ret['options']['api_protocol'] = 'Whether API runs on http or https. Default: ' + self.__api_protocol
        return ret


def __resolve_expiration(reference: str, module, args, LOGGER, datatracker_failures: list):
    """Walks through all the modules and updates them if necessary

        Arguments:
            :param reference:           (str) reference metadata from yangcatalog.yang
            :param module:              (json) all the module metadata
            :param args:                (obj) arguments received at the start of this script
            :param LOGGER               (obj) formated logger with the specified name
            :param datatracker_failures (list) list of url that failed to get data from Datatracker
    """
    expired = 'not-applicable'
    expires = None
    if module.get('maturity-level') == 'ratified':
        expired = False
        expires = ''
    if reference is not None and 'datatracker.ietf.org' in reference:
        ref = module.get('reference').split('/')[-1]
        rev = None
        if ref.isdigit():
            ref = module.get('reference').split('/')[-2]
            rev = module.get('reference').split('/')[-1]
        url = ('https://datatracker.ietf.org/api/v1/doc/document/?name={}&states__type=draft&states__slug__in=active,RFC&format=json'.format(ref))
        retry = 6
        while True:
            try:
                response = requests.get(url)
                break
            except NewConnectionError as nce:
                retry -= 1
                LOGGER.warning('Failed to fetch file content of {}'.format(ref))
                time.sleep(10)
                if retry == 0:
                    LOGGER.error('Failed to fetch file content of {} for 6 times in a row - SKIPPING.'.format(ref))
                    LOGGER.error(nce)
                    datatracker_failures.append(url)
                    return None

        if response.status_code == 200:
            data = response.json()
            objs = data['objects']
            if len(objs) == 1:
                if rev == objs[0].get('rev'):
                    rfc = objs[0].get('rfc')
                    if rfc is None:
                        expires = objs[0]['expires']
                        expired = False
                    else:
                        expired = True
                        expires = ''
                else:
                    expired = True
                    expires = ''
            else:
                expired = True
                expires = ''

    if module.get('expires') != expires or module.get('expired') != expired:
        if module.get('expires') is None and (expires == '' or expires is None) and module.get('expired') == expired:
            return False
        yang_name_rev = '{}@{}'.format(module['name'], module['revision'])
        LOGGER.info('Module {} changing expiration FROM expires: {} expired: {} TO expires: {} expired: {}'
                    .format(yang_name_rev, module.get('expires'), module.get('expired'), expires, expired))
        confd_prefix = '{}://{}:{}'.format(args.protocol, args.ip, args.port)

        if expires != '' and expires is not None:
            module['expires'] = expires
        module['expired'] = expired
        url = '{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}' \
            .format(confd_prefix, module['name'], module['revision'], module['organization'])
        response = requests.patch(url, json.dumps({'yang-catalog:module': module}),
                                  auth=(args.credentials[0],
                                        args.credentials[1]),
                                  headers={
                                      'Accept': 'application/yang-data+json',
                                      'Content-type': 'application/yang-data+json'}
                                  )
        message = 'Module {} updated with code {}'.format(yang_name_rev, response.status_code)
        if response.text != '':
            message = '{} and text {}'.format(message, response.text)
        LOGGER.info(message)
        if expires == '' and module.get('expires') is not None:
            url = '{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}/expires' \
                .format(confd_prefix, module['name'], module['revision'], module['organization'])
            response = requests.delete(url, auth=(args.credentials[0], args.credentials[1]),
                                       headers={
                                           'Accept': 'application/yang-data+json',
                                           'Content-type': 'application/yang-data+json'}
                                       )
        message = 'Module {} expiration date deleted with code {}'.format(yang_name_rev, response.status_code)
        if response.text != '':
            message = '{} and text {}'.format(message, response.text)
        LOGGER.info(message)
        return True
    else:
        return False


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    revision_updated_modules = 0
    datatracker_failures = []
    args = scriptConf.args
    log_directory = scriptConf.log_directory
    temp_dir = scriptConf.temp_dir
    is_uwsgi = scriptConf.is_uwsgi
    LOGGER = log.get_logger('resolveExpiration', '{}/jobs/resolveExpiration.log'.format(log_directory))
    LOGGER.info('Starting Cron job resolve modules expiration')

    separator = ':'
    suffix = args.api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(args.api_protocol,
                                                   args.api_ip, separator,
                                                   suffix)
    try:
        LOGGER.info('Requesting all the modules from {}'.format(yangcatalog_api_prefix))
        updated = False

        modules = requests.get('{}search/modules'.format(yangcatalog_api_prefix),
                               auth=(args.credentials[0], args.credentials[1]))
        if modules.status_code < 200 or modules.status_code > 299:
            LOGGER.error('Request on path {} failed with {}'
                         .format(yangcatalog_api_prefix, modules.text))
        else:
            LOGGER.debug('{} modules fetched from {} successfully'
                         .format(len(modules.json()['module']), yangcatalog_api_prefix))
        modules = modules.json()['module']
        i = 1
        for module in modules:
            LOGGER.info('{} out of {}'.format(i, len(modules)))
            i += 1
            ref = module.get('reference')
            ret = __resolve_expiration(ref, module, args, LOGGER, datatracker_failures)
            if ret:
                revision_updated_modules += 1
            if not updated:
                updated = ret
        if updated:
            url = ('{}load-cache'.format(yangcatalog_api_prefix))
            response = requests.post(url, None, auth=(args.credentials[0],
                                                      args.credentials[1]))
            LOGGER.info('Cache loaded with status {}'.format(response.status_code))
    except Exception as e:
        LOGGER.error('Exception found while running resolveExpiration script')
        job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
        raise e
    if len(datatracker_failures) > 0:
        LOGGER.debug('Following references failed to get from the datatracker:\n {}'.format('\n'.join(datatracker_failures)))
    messages = [
        {'label': 'Modules with changed revison', 'message': revision_updated_modules},
        {'label': 'Datatracker modules failures', 'message': len(datatracker_failures)}
    ]
    job_log(start_time, temp_dir, messages=messages, status='Success', filename=os.path.basename(__file__))
    LOGGER.info('Job finished successfully')


if __name__ == "__main__":
    main()
