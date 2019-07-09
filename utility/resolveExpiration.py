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
import requests

import utility.log as log

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


def __resolve_expiration(reference, module, args):
    """Walks through all the modules and updates them if necessary

        Arguments:
            :param reference: (str) reference metadata from yangcatalog.yang
            :param module: (json) all the module metadata
            :param args: (obj) arguments received at the start of this script
    """
    if reference is not None and 'datatracker.ietf.org' in reference:
        expires = module.get('expires')
        if expires is not None:
            if dateutil.parser.parse(expires).date() < datetime.datetime.now().date():
                expired = True
            else:
                expired = False
        else:
            expired = 'not-applicable'
            ref = mod.get('reference').split('/')[-1]
            url = ('https://datatracker.ietf.org/api/v1/doc/document/'
                   + ref + '/?format=json')
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                expires = data.get('expires')
                if expires:
                    if dateutil.parser.parse(expires).date() < datetime.datetime.now().date():
                        expired = True
                    else:
                        expired = False

        if module.get('expires') != expires or module.get('expired') != expired:
            module['expires'] = expires
            module['expired'] = expired
            url = 'https://yangcatalog.org:8888/api/config/catalog/modules/module/{},{},{}' \
                .format(module['name'], module['revision'],
                        module['organization'])
            response = requests.patch(url, json.dumps({'yang-catalog:module': module}),
                                      auth=(args.credentials[0],
                                            args.credentials[1]),
                                      headers={
                                          'Accept': 'application/vnd.yang.data+json',
                                          'Content-type': 'application/vnd.yang.data+json'}
                                      )
            LOGGER.info('module {}@{} updated with code {}'.format(module['name'], module['revision'],
                                                                   response.status_code))
            return True
        else:
            return False
    else:
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials',
                        help='Set authorization parameters username password respectively.'
                             ' Default parameters are admin admin', nargs=2,
                        default=['admin', 'admin'], type=str)
    parser.add_argument('--api-protocol', type=str, default='https',
                        help='Whether api runs on http or https.'
                             ' Default is set to http')
    parser.add_argument('--api-ip', default='yangcatalog.org', type=str,
                        help='Set ip address where the api is started. Default -> yangcatalog.org')
    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    LOGGER = log.get_logger('resolveExpiration', log_directory + '/jobs/resolveExpiration.log')
    updated = False

    modules = requests.get('{}://{}/api/search/modules'.format(args.api_protocol,
                                                               args.api_ip),
                           auth=(args.credentials[0], args.credentials[1]))
    modules = modules.json()['module']
    for mod in modules:
        ref = mod.get('reference')
        ret = __resolve_expiration(ref, mod, args)
        if not updated:
            updated = ret
    if updated:
        url = (args.api_protocol + '://' + args.api_ip + '/api/load-cache')
        response = requests.post(url, None, auth=(args.credentials[0],
                                                  args.credentials[1]))
        LOGGER.info('Cache loaded with status {}'.format(response.status_code))

