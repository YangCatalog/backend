"""
This script calls runCapabilities.py script with
option based on if we are populating sdos or vendors
and if this script was called via api or directly by
yangcatalog admin user. Once the metatadata are parsed
and json files are created it will populate the confd
with all the parsed metadata reloads api and starts to
parse metadata that needs to use complicated algorthms.
For this we use class ModulesComplicatedAlgorithms.
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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import errno
import fnmatch
import json
import os
import shutil
import subprocess
import threading
import unicodedata
import sys

import requests
from api.receiver import prepare_to_indexing, send_to_indexing

import utility.log as log
from parseAndPopulate.modulesComplicatedAlgorithms import ModulesComplicatedAlgorithms

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

def run_complicated_algorithms():
    complicatedAlgorithms = ModulesComplicatedAlgorithms(yangcatalog_api_prefix, args.credentials,
                                                         args.protocol, args.ip, args.port, args.save_file_dir,
                                                         direc, None)
    complicatedAlgorithms.parse()
    complicatedAlgorithms.populate()


def find_files(directory, pattern):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename


# Unicode to string
def unicode_normalize(variable):
    return unicodedata.normalize('NFKD', variable).encode('ascii', 'ignore')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse hello messages and yang files to json dictionary. These"
                                                 " dictionaries are used for populating a yangcatalog. This script runs"
                                                 " first a runCapabilities.py script to create a Json files which are "
                                                 "used to populate database.")
    parser.add_argument('--port', default=8008, type=int,
                        help='Set port where the confd is started. Default -> 8008')
    parser.add_argument('--ip', default='localhost', type=str,
                        help='Set ip address where the confd is started. Default -> localhost')
    parser.add_argument('--api-port', default=8443, type=int,
                        help='Set port where the api is started. Default -> 8443')
    parser.add_argument('--api-ip', default='yangcatalog.org', type=str,
                        help='Set ip address where the api is started. Default -> yangcatalog.org')
    parser.add_argument('--credentials', help='Set authorization parameters username password respectively.'
                                              ' Default parameters are admin admin', nargs=2
                        , type=str)
    parser.add_argument('--dir', default='../../vendor', type=str,
                        help='Set dir where to look for hello message xml files.Default -> ../../vendor')
    parser.add_argument('--api', action='store_true', default=False, help='If we are doing apis')
    parser.add_argument('--sdo', action='store_true', default=False, help='If we are sneding SDOs only')
    parser.add_argument('--notify-indexing', action='store_true', default=False, help='Weather to send files for'
                                                                                      ' indexing')
    parser.add_argument('--protocol', type=str, default='http', help='Whether confd-6.4 runs on http or https.'
                                                                     ' Default is set to http')
    parser.add_argument('--api-protocol', type=str, default='https', help='Whether api runs on http or https.'
                                                                          ' Default is set to http')
    parser.add_argument('--result-html-dir', default='/home/miroslav/results/', type=str,
                        help='Set dir where to write html result files. Default -> /home/miroslav/results/')
    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')
    parser.add_argument('--force-indexing', action='store_true', default=False, help='Force to index files')
    parser.add_argument('--save-file-dir', default='/home/miroslav/results/',
                        type=str, help='Directory where the file will be saved')
    args = parser.parse_args()
    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    LOGGER = log.get_logger(__name__, log_directory + '/parseAndPopulate.log')
    is_uwsgi = config.get('General-Section', 'uwsgi')
    separator = ':'
    suffix = args.api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(args.api_protocol,
                                                   args.api_ip, separator,
                                                   suffix)
    key = config.get('Receiver-Section', 'key')
    LOGGER.info('Starting the populate script')
    if args.api:
        direc = '/'.join(args.dir.split('/')[0:3])
    else:
        direc = 0
        while True:
            try:
                os.makedirs('../parseAndPopulate/' + repr(direc))
                break
            except OSError as e:
                direc += 1
                if e.errno != errno.EEXIST:
                    raise
        direc = repr(direc)
    prefix = '{}://{}:{}'.format(args.protocol, args.ip, args.port)
    LOGGER.info('Calling runcapabilities script')
    if args.api:
        if args.sdo:
            with open("log_api_sdo.txt", "wr") as f:
                arguments = ["python", "../parseAndPopulate/runCapabilities.py",
                             "--api", "--sdo", "--dir",args.dir, "--json-dir",
                             direc, "--result-html-dir", args.result_html_dir,
                             '--save-file-dir', args.save_file_dir, '--api-ip',
                             args.api_ip, '--api-port', repr(args.api_port),
                             '--api-protocol', args.api_protocol]
                subprocess.check_call(arguments, stderr=f)
        else:
            with open("log_api.txt", "wr") as f:
                arguments = ["python", "../parseAndPopulate/runCapabilities.py",
                             "--api", "--dir", args.dir,"--json-dir", direc,
                             "--result-html-dir", args.result_html_dir,
                             '--save-file-dir', args.save_file_dir, '--api-ip',
                             args.api_ip, '--api-port', repr(args.api_port),
                             '--api-protocol', args.api_protocol]
                subprocess.check_call(arguments, stderr=f)
    else:
        if args.sdo:
            with open("log_sdo.txt", "wr") as f:
                arguments = ["python", "../parseAndPopulate/runCapabilities.py",
                             "--sdo", "--dir", args.dir, "--json-dir", direc,
                             "--result-html-dir", args.result_html_dir,
                             '--save-file-dir', args.save_file_dir, '--api-ip',
                             args.api_ip, '--api-port', repr(args.api_port),
                             '--api-protocol', args.api_protocol]
                subprocess.check_call(arguments, stderr=f)
        else:
            with open("log_no_sdo_api.txt", "wr") as f:
                arguments = ["python", "../parseAndPopulate/runCapabilities.py",
                             "--dir", args.dir, "--json-dir", direc,
                             "--result-html-dir", args.result_html_dir,
                             '--save-file-dir', args.save_file_dir,  '--api-ip',
                             args.api_ip, '--api-port', repr(args.api_port),
                             '--api-protocol', args.api_protocol]
                subprocess.check_call(arguments, stderr=f)

    body_to_send = ''
    if args.notify_indexing:
        LOGGER.info('Sending files for indexing')
        prepare_to_indexing(yangcatalog_api_prefix,
                         '../parseAndPopulate/{}/prepare.json'.format(direc),
                            args.credentials, apiIp=args.api_ip, sdo_type=args.sdo,
                            from_api=args.api, force_indexing=args.force_indexing)

    LOGGER.info('Populating yang catalog with data. Starting to add modules')
    with open('../parseAndPopulate/{}/prepare.json'.format(direc)) as data_file:
        read = data_file.read()
        modules_json = json.loads(read)['module']
        mod = len(modules_json) % 1000
        for x in range(0, int(len(modules_json) / 1000)):
            json_modules_data = json.dumps({
                'modules':
                    {
                        'module': modules_json[x*1000: (x*1000)+1000]
                    }
            })

            if '{"module": []}' not in read:
                url = prefix + '/api/config/catalog/modules/'
                response = requests.patch(url, json_modules_data,
                                          auth=(args.credentials[0],
                                                args.credentials[1]),
                                          headers={
                                              'Accept': 'application/vnd.yang.data+json',
                                              'Content-type': 'application/vnd.yang.data+json'})
                if response.status_code < 200 or response.status_code > 299:
                    LOGGER.error('Request with body {} on path {} failed with {}'
                                 .format(json_modules_data, url,
                                        response.content))
    rest = (len(modules_json) / 1000) * 1000
    json_modules_data = json.dumps({
        'modules':
            {
                'module': modules_json[rest: rest + mod]
            }
    })
    url = prefix + '/api/config/catalog/modules/'
    response = requests.patch(url, json_modules_data,
                              auth=(args.credentials[0],
                                    args.credentials[1]),
                              headers={
                                  'Accept': 'application/vnd.yang.data+json',
                                  'Content-type': 'application/vnd.yang.data+json'})
    if response.status_code < 200 or response.status_code > 299:
        LOGGER.error('Request with body {} on path {} failed with {}'
                     .format(json_modules_data, url,
                             response.content))

    # In each json
    LOGGER.info('Starting to add vendors')
    if os.path.exists('../parseAndPopulate/{}/normal.json'.format(direc)):
        with open('../parseAndPopulate/{}/normal.json'.format(direc)) as data:
            vendors = json.loads(data.read())['vendors']['vendor']

            mod = len(vendors) % 1000
            for x in range(0, int(len(vendors) / 1000)):
                json_implementations_data = json.dumps({
                    'vendors':
                        {
                            'vendor': vendors[x * 1000: (x * 1000) + 1000]
                        }
                })

                # Make a PATCH request to create a root for each file
                url = prefix + '/api/config/catalog/vendors/'
                response = requests.patch(url, json_implementations_data,
                                          auth=(args.credentials[0],
                                                args.credentials[1]),
                                          headers={
                                              'Accept': 'application/vnd.yang.data+json',
                                              'Content-type': 'application/vnd.yang.data+json'})
                if response.status_code < 200 or response.status_code > 299:
                    LOGGER.error('Request with body on path {} failed with {}'.
                                 format(json_implementations_data, url,
                                        response.content))
            rest = (len(vendors) / 1000) * 1000
            json_implementations_data = json.dumps({
                'vendors':
                    {
                        'vendor': vendors[rest: rest + mod]
                    }
            })
            url = prefix + '/api/config/catalog/vendors/'
            response = requests.patch(url, json_implementations_data,
                                      auth=(args.credentials[0],
                                            args.credentials[1]),
                                      headers={
                                          'Accept': 'application/vnd.yang.data+json',
                                          'Content-type': 'application/vnd.yang.data+json'})
            if response.status_code < 200 or response.status_code > 299:
                LOGGER.error('Request with body on path {} failed with {}'
                             .format(json_implementations_data, url,
                                     response.content))
    if body_to_send != '':
        LOGGER.info('Sending files for indexing')
        send_to_indexing(body_to_send, args.credentails, set_key=key, apiIp=args.api_ip)
    if not args.api:
        thread = None
        if not args.force_indexing:
            LOGGER.info('Sending request to reload cache')
            url = (yangcatalog_api_prefix + 'load-cache')
            response = requests.post(url, None,
                                     auth=(args.credentials[0],
                                            args.credentials[1]),
                                     headers={
                                         'Accept': 'application/vnd.yang.data+json',
                                         'Content-type': 'application/vnd.yang.data+json'})
            if response.status_code != 201:
                LOGGER.warning('Could not send a load-cache request')

            thread = threading.Thread(target=run_complicated_algorithms())
            thread.start()

        else:
            url = (yangcatalog_api_prefix + 'load-cache')
            LOGGER.info('{}'.format(url))
            response = requests.post(url, None,
                                     auth=(args.credentials[0],
                                           args.credentials[1]))
            if response.status_code != 201:
                LOGGER.warning('Could not send a load-cache request')
            try:
                shutil.rmtree('../api/cache')
            except OSError:
                # Be happy if deleted
                pass
        if thread is not None:
            thread.join()
        try:
            shutil.rmtree('../parseAndPopulate/' + direc)
            shutil.rmtree('../api/cache')
        except OSError:
            # Be happy if deleted
            pass

