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
import sys
import os
import time

import dateutil.parser
import requests
from dateutil.relativedelta import relativedelta

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


def __resolve_expiration(reference, module, args, LOGGER):
    """Walks through all the modules and updates them if necessary

        Arguments:
            :param reference: (str) reference metadata from yangcatalog.yang
            :param module: (json) all the module metadata
            :param args: (obj) arguments received at the start of this script
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
        response = requests.get(url)
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
        LOGGER.info('Module {}@{} changing expiration from expires {} expired {} to expires {} expired {}'
                    .format(module['name'], module['revision'], module.get('expires'), module.get('expired'),
                            expires, expired))
        prefix = '{}://{}:{}'.format(args.protocol, args.ip, args.port)

        if expires != '' and expires is not None:
            module['expires'] = expires
        module['expired'] = expired
        url = '{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}' \
            .format(prefix, module['name'], module['revision'], module['organization'])
        response = requests.patch(url, json.dumps({'yang-catalog:module': module}),
                                  auth=(args.credentials[0],
                                        args.credentials[1]),
                                  headers={
                                      'Accept': 'application/yang-data+json',
                                      'Content-type': 'application/yang-data+json'}
                                  )
        LOGGER.info('module {}@{} updated with code {} and text {}'.format(module['name'], module['revision'],
                                                                           response.status_code, response.text))
        if expires == '' and module.get('expires') is not None:
            url = '{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}/expires' \
                .format(prefix, module['name'], module['revision'], module['organization'])
            response = requests.delete(url, auth=(args.credentials[0], args.credentials[1]),
                                       headers={
                                           'Accept': 'application/yang-data+json',
                                           'Content-type': 'application/yang-data+json'}
                                       )
            LOGGER.info('module {}@{} expiration date deleted with code {} and text {}'
                        .format(module['name'], module['revision'], response.status_code, response.text))
        return True
    else:
        return False


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    log_directory = scriptConf.log_directory
    temp_dir = scriptConf.temp_dir
    is_uwsgi = scriptConf.is_uwsgi
    LOGGER = log.get_logger('resolveExpiration', log_directory + '/jobs/resolveExpiration.log')
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
        LOGGER.info('requesting {}'.format(yangcatalog_api_prefix))
        updated = False

        modules = requests.get('{}search/modules'.format(yangcatalog_api_prefix),
                            auth=(args.credentials[0], args.credentials[1]))
        if modules.status_code < 200 or modules.status_code > 299:
            LOGGER.error('Request on path {} failed with {}'
                        .format(yangcatalog_api_prefix,
                                modules.text))
        modules = modules.json()['module']
        i = 1
        for mod in modules:
            LOGGER.info('{} out of {}'.format(i, len(modules)))
            i += 1
            ref = mod.get('reference')
            ret = __resolve_expiration(ref, mod, args, LOGGER)
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
    job_log(start_time, temp_dir, status='Success', filename=os.path.basename(__file__))
    LOGGER.info('Job finished successfully')


if __name__ == "__main__":
    main()
