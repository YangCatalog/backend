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

import dateutil.parser
import pytz as pytz
import requests
from dateutil.relativedelta import relativedelta

import utility.log as log

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

utc = pytz.UTC


class ScriptConfig():

    def __init__(self):
        config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(config_path)
        self.log_directory = config.get('Directory-Section', 'logs')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        confd_protocol = config.get('General-Section', 'protocol-confd')
        confd_port = config.get('Web-Section', 'confd-port')
        confd_host = config.get('Web-Section', 'confd-ip')
        api_protocol = config.get('General-Section', 'protocol-api')
        api_port = config.get('Web-Section', 'api-port')
        api_host = config.get('Web-Section', 'ip')
        credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
        parser = argparse.ArgumentParser()
        parser.add_argument('--credentials',
                            help='Set authorization parameters username password respectively.'
                                ' Default parameters are {}'.format(str(credentials)), nargs=2,
                            default=credentials, type=str)
        parser.add_argument('--ip', default=confd_host, type=str,
                            help='Set host where the Confd is started. Default: ' + confd_host)
        parser.add_argument('--port', default=confd_port, type=int,
                            help='Set port where the Confd is started. Default: ' + confd_port)
        parser.add_argument('--protocol', type=str, default=confd_protocol, help='Whether Confd runs on http or https.'
                            ' Default: ' + confd_protocol)
        parser.add_argument('--api-ip', default=api_host, type=str,
                            help='Set host where the API is started. Default: ' + api_host)
        parser.add_argument('--api-port', default=api_port, type=int,
                            help='Set port where the API is started. Default: ' + api_port)
        parser.add_argument('--api-protocol', type=str, default=api_protocol, help='Whether API runs on http or https.'
                                                                            ' Default: ' + api_protocol)
        self.args = parser.parse_args()
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


def __resolve_expiration(reference, module, args, LOGGER):
    """Walks through all the modules and updates them if necessary

        Arguments:
            :param reference: (str) reference metadata from yangcatalog.yang
            :param module: (json) all the module metadata
            :param args: (obj) arguments received at the start of this script
    """
    if reference is not None and 'datatracker.ietf.org' in reference:
        LOGGER.debug('Resolving expiration of {}@{} reference {} {}'.format(module['name'], module['revision'], reference, module.get('reference')))
        expires = module.get('expires')
        expired = False
        if expires is not None:
            if dateutil.parser.parse(expires).date() < datetime.datetime.now().date():
                expired = True
        if not expired:
            expired = 'not-applicable'
            ref = module.get('reference').split('/')[-1]
            rev = None
            if ref.isdigit():
                ref = module.get('reference').split('/')[-2]
                rev = module.get('reference').split('/')[-1]
            url = ('https://datatracker.ietf.org/api/v1/doc/document/' + ref + '/?format=json')
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()

                if rev == data.get('rev'):
                    expires = data.get('expires')
                else:
                    url = 'https://datatracker.ietf.org/api/v1/doc/newrevisiondocevent/?format=json&doc__name=draft-ietf-netconf-tls-client-server&limit=1000'
                    response = requests.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        objs = data.get('objects')
                        for obj in objs:
                            if obj.get('rev') == rev:
                                str_length = len(obj['rev'])
                                next_rev = str(int(obj['rev']) + 1)
                                while len(next_rev) < str_length:
                                    next_rev = '0{}'.format(next_rev)
                                created_at = obj.get('time')
                                expires = dateutil.parser.parse(created_at) + relativedelta(months=+6)
                                LOGGER.info('next {}'.format(next_rev))
                                for obj2 in objs:
                                    if obj2.get('rev') == next_rev:
                                        created_at2 = obj2.get('time')
                                        if dateutil.parser.parse(created_at2).date() < expires.date():
                                            expires = str(dateutil.parser.parse(created_at)).replace(' ', 'T')
                                        else:
                                            expires = str(expires).replace(' ', 'T')
                                        break

                                break
                LOGGER.info('expires {} check'.format(expires))
                if expires:
                    if dateutil.parser.parse(expires).date() < datetime.datetime.now().date():
                        expired = True
                    else:
                        expired = False

        if module.get('expires') != expires or module.get('expired') != expired:
            LOGGER.info('Module {}@{} changing expiration from expires {} expired {} to expires {} expired {}'
                        .format(module['name'], module['revision'], module.get('expires'), module.get('expired'),
                                expires, expired))
            if expires is not None:
                module['expires'] = expires
            module['expired'] = expired
            prefix = '{}://{}:{}'.format(args.protocol, args.ip, args.port)
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
            return True
        else:
            return False
    else:
        return False


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    log_directory = scriptConf.log_directory
    is_uwsgi = scriptConf.is_uwsgi
    LOGGER = log.get_logger('resolveExpiration', log_directory + '/jobs/resolveExpiration.log')

    separator = ':'
    suffix = args.api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(args.api_protocol,
                                                   args.api_ip, separator,
                                                   suffix)
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
    LOGGER.info("Job finished successfully")


if __name__ == "__main__":
    main()
