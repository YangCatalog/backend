"""
This script is run by a cronjob and it
finds all the modules that have expiration
metadata and updates them based on a date to
expired if it is necessary
"""
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
import sys

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import json

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
    update = False
    if reference is not None and 'datatracker.ietf.org' in reference:
        ref = reference.split('/')[-1]
        url = ('https://datatracker.ietf.org/api/v1/doc/document/'
               + ref + '/?format=json')
        try:
            response = requests.get(url)
        except Exception as e:
            LOGGER.warning("Failed to get json from datatracker {} with error {}".format(url, e))
            return
        if response.status_code == 200:
            data = response.json()
            if '/api/v1/doc/state/2/' in data['states']:
                expired = module.get('expired')
                if expired is None or not expired:
                    update = True
                    module['expired'] = True
                if module.get('expires') is not None:
                    if module['expires'] != data['expires']:
                        update = True
                        module['expires'] = data['expires']
            else:
                expired = module.get('expired')
                if expired is None or expired:
                    update = True
                    module['expires'] = data['expires']
                    module['expired'] = False
        else:
            if module.get('expired') is None:
                update = True
                module['expired'] = 'not-applicable'
                module['expires'] = None
    elif module.get('expired') is None:
        update = True
        module['expired'] = 'not-applicable'
        module['expires'] = None
    if update:
        url = 'http://yangcatalog.org:8008/api/config/catalog/modules/module/{},{},{}' \
            .format(module['name'], module['revision'],
                    module['organization'])
        body = json.dumps({'yang-catalog:module': {
                'name': module['name'],
                'revision': module['revision'],
                'organization': module['organization'],
                'expires': module.get('expires'),
                'expired': module['expired']
            }
        })
        try:
            response = requests.patch(url, body,
                                      auth=(args.credentials[0],
                                            args.credentials[1]),
                                      headers={
                                          'Accept': 'application/vnd.yang.data+json',
                                          'Content-type': 'application/vnd.yang.data+json'}
                                      )
        except Exception as e:
            LOGGER.warning("Failed to push json to confd {} with error {}".format(url, e))
            return
        LOGGER.info('Updating module {}@{} with confd response {} - {}'
                    .format(module['name'], module['revision'],
                            repr(response.status_code), response.text))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials',
                        help='Set authorization parameters username password respectively.'
                             ' Default parameters are admin admin', nargs=2,
                        default=['admin', 'admin'], type=str)
    parser.add_argument('--api-protocol', type=str, default='https',
                        help='Whether api runs on http or https.'
                             ' Default is set to http')
    parser.add_argument('--api-ip', default='new.yangcatalog.org', type=str,
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

    modules = requests.get('{}://{}/api/search/modules'.format(args.api_protocol,
                                                              args.api_ip),
                           auth=(args.credentials[0], args.credentials[1]))
    modules = modules.json()['module']
    for mod in modules:
        ref = mod.get('reference')
        __resolve_expiration(ref, mod, args)
    url = (args.api_protocol + '://' + args.api_ip + '/api/load-cache')
    response = requests.post(url, None, auth=(args.credentials[0],
                                              args.credentials[1]))
