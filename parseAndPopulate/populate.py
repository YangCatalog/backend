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
This script calls runCapabilities.py script with
option based on if we are populating sdos or vendors
and if this script was called via api or directly by
yangcatalog admin user. Once the metatadata are parsed
and json files are created it will populate the confd
with all the parsed metadata reloads api and starts to
parse metadata that needs to use complicated algorthms.
For this we use class ModulesComplicatedAlgorithms.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import errno
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import time

import requests

import utility.log as log
from parseAndPopulate.modulesComplicatedAlgorithms import ModulesComplicatedAlgorithms
from utility.util import prepare_to_indexing, send_to_indexing

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


class ScriptConfig():
    def __init__(self):
        config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(config_path)
        self.log_directory = config.get('Directory-Section', 'logs')
        self.is_uwsgi = config.get('General-Section', 'uwsgi')
        self.yang_models = config.get('Directory-Section', 'yang-models-dir')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.key = config.get('Secrets-Section', 'update-signature')
        credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
        self.__confd_protocol = config.get('General-Section', 'protocol-confd')
        self.__confd_port = config.get('Web-Section', 'confd-port')
        self.__confd_host = config.get('Web-Section', 'confd-ip')
        self.__api_protocol = config.get('General-Section', 'protocol-api')
        self.__api_port = config.get('Web-Section', 'api-port')
        self.__api_host = config.get('Web-Section', 'ip')
        self.__save_file_dir = config.get('Directory-Section', 'save-file-dir')
        self.__result_dir = config.get('Web-Section', 'result-html-dir')
        self.help = 'Parse hello messages and YANG files to JSON dictionary. These' \
        ' dictionaries are used for populating a yangcatalog. This script runs' \
        ' first a runCapabilities.py script to create a JSON files which are' \
        ' used to populate database.'

        parser = argparse.ArgumentParser(description=self.help)
        parser.add_argument('--ip', default=self.__confd_host, type=str,
                            help='Set host address where the Confd is started. Default: ' + self.__confd_host)
        parser.add_argument('--port', default=self.__confd_port, type=int,
                            help='Set port where the Confd is started. Default: ' + self.__confd_port)
        parser.add_argument('--protocol', type=str, default=self.__confd_protocol, help='Whether Confd runs on http or https.'
                                                                                 ' Default: ' + self.__confd_protocol)
        parser.add_argument('--api-ip', default=self.__api_host, type=str,
                            help='Set host address where the API is started. Default: ' + self.__api_host)
        parser.add_argument('--api-port', default=self.__api_port, type=int,
                            help='Set port where the API is started. Default: ' + self.__api_port)
        parser.add_argument('--api-protocol', type=str, default=self.__api_protocol,
                            help='Whether API runs on http or https (This will be ignored if we are using uwsgi).'
                                 ' Default: ' + self.__api_protocol)
        parser.add_argument('--credentials', help='Set authorization parameters username password respectively.'
                                                  ' Default parameters are ' + str(credentials), nargs=2,
                            default=credentials, type=str)
        parser.add_argument('--dir', default='/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC', type=str,
                            help='Set dir where to look for hello message xml files')
        parser.add_argument('--api', action='store_true', default=False, help='If request came from api')
        parser.add_argument('--sdo', action='store_true', default=False,
                            help='If we are processing sdo or vendor yang modules')
        parser.add_argument('--notify-indexing', action='store_true', default=False, help='Whether to send files for'
                                                                                          ' indexing')
        parser.add_argument('--result-html-dir', default=self.__result_dir, type=str,
                            help='Set dir where to write HTML compilation result files. Default: ' + self.__result_dir)
        parser.add_argument('--force-indexing', action='store_true', default=False,
                            help='Force to index files. Works only in notify-indexint is True')
        parser.add_argument('--save-file-dir', default=self.__save_file_dir,
                            type=str, help='Directory where the yang file will be saved. Default: ' + self.__save_file_dir)
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

    def get_help(self):
        ret = {}
        ret['help'] = self.help
        ret['options'] = {}
        ret['options']['dir'] = 'Set dir where to look for hello message xml files or yang files if using "sdo" option'
        ret['options']['ip'] = 'Set host address where the Confd is started. Default: ' + self.__confd_host
        ret['options']['port'] = 'Set port where the Confd is started. Default: ' + self.__confd_port
        ret['options']['protocol'] = 'Whether Confd runs on http or https. Default: ' + self.__confd_protocol

        ret['options']['api'] = 'If request came from api'
        ret['options']['sdo'] = 'If we are processing sdo or vendor yang modules'
        ret['options']['notify_indexing'] = 'Whether to send files for indexing'
        ret['options']['force_indexing'] = 'Force to index files. Works only in notify-indexing is True'
        ret['options']['result_html_dir'] = 'Set dir where to write HTML compilation result files. Default: '\
                                            + self.__result_dir
        ret['options']['save_file_dir'] = 'Directory where the yang file will be saved. Default: ' + self.__save_file_dir
        ret['options']['api_protocol'] = 'Whether API runs on http or https. Default: ' + self.__api_protocol
        ret['options']['api_port'] = 'Whether API runs on http or https (This will be ignored if we are using uwsgi).' \
                                     ' Default: ' + self.__api_protocol
        ret['options']['api_ip'] = 'Set host address where the API is started. Default: ' + self.__api_host
        return ret


def reload_cache_in_parallel(credentials, yangcatalog_api_prefix):
    LOGGER.info('Sending request to reload cache in different thread')
    url = (yangcatalog_api_prefix + 'load-cache')
    response = requests.post(url, None,
                             auth=(credentials[0],
                                   credentials[1]),
                             headers={
                                 'Accept': 'application/json',
                                 'Content-type': 'application/json'})
    if response.status_code != 201:
        LOGGER.warning('Could not send a load-cache request. Status code {}. message {}'
                       .format(response.status_code, response.text))
    LOGGER.info("cache reloaded")


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    log_directory = scriptConf.log_directory
    is_uwsgi = scriptConf.is_uwsgi
    yang_models = scriptConf.yang_models
    temp_dir = scriptConf.temp_dir
    key = scriptConf.key
    global LOGGER
    LOGGER = log.get_logger('populate', log_directory + '/parseAndPopulate.log')

    separator = ':'
    suffix = args.api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(args.api_protocol,
                                                   args.api_ip, separator,
                                                   suffix)
    LOGGER.info('Starting the populate script')
    start = time.time()
    if args.api:
        direc = args.dir
        args.dir += '/temp'
    else:
        direc = 0
        while True:
            try:
                os.makedirs('{}/{}'.format(temp_dir, repr(direc)))
                break
            except OSError as e:
                direc += 1
                if e.errno != errno.EEXIST:
                    raise
        direc = '{}/{}'.format(temp_dir, repr(direc))
    prefix = '{}://{}:{}'.format(args.protocol, args.ip, args.port)
    LOGGER.info('Calling runcapabilities script')
    run_capabilities = os.path.dirname(os.path.realpath(__file__)) + '/runCapabilities.py'
    run_capabilities_args = ["python", run_capabilities, "--json-dir", direc, "--result-html-dir",
                             args.result_html_dir, "--dir", args.dir, '--save-file-dir',
                             args.save_file_dir, '--api-ip', args.api_ip, '--api-port',
                             repr(args.api_port), '--api-protocol', args.api_protocol]
    if args.api:
        run_capabilities_args.append("--api")
    if args.sdo:
        run_capabilities_args.append("--sdo")
    with open("{}/log_runCapabilities_temp.txt".format(temp_dir), "w") as f:
        subprocess.check_call(run_capabilities_args, stderr=f)
    with open("{}/log_runCapabilities_temp.txt".format(temp_dir), "r") as f:
        error = f.read()
        if error != "":
            LOGGER.error("run capabilities error:\n{}".format(error))

    body_to_send = ''
    if args.notify_indexing:
        LOGGER.info('Sending files for indexing')
        body_to_send = prepare_to_indexing(yangcatalog_api_prefix, '{}/prepare.json'.format(direc), args.credentials,
                                           LOGGER, args.save_file_dir, temp_dir, args.protocol, args.ip, args.port,
                                           sdo_type=args.sdo, from_api=args.api, force_indexing=args.force_indexing)

    LOGGER.info('Populating yang catalog with data. Starting to add modules')
    x = -1
    with open('{}/prepare.json'.format(direc)) as data_file:
        read = data_file.read()
        modules_json = json.loads(read)['module']
        for x in range(0, int(len(modules_json) / 1000)):
            json_modules_data = json.dumps({
                'modules':
                    {
                        'module': modules_json[x * 1000: (x * 1000) + 1000]
                    }
            })

            if '{"module": []}' not in read:
                url = prefix + '/restconf/data/yang-catalog:catalog/modules/'
                response = requests.patch(url, json_modules_data,
                                          auth=(args.credentials[0],
                                                args.credentials[1]),
                                          headers={
                                              'Accept': 'application/yang-data+json',
                                              'Content-type': 'application/yang-data+json'})
                if response.status_code < 200 or response.status_code > 299:
                    path_to_file = '{}/modules-confd-data-{}'.format(direc, x)
                    with open(path_to_file, 'w') as f:
                        json.dump(json_modules_data, f)
                    LOGGER.error('Request with body {} on path {} failed with {}'
                                 .format(path_to_file, url,
                                         response.text))
    json_modules_data = json.dumps({
        'modules':
            {
                'module': modules_json[(x * 1000) + 1000:]
            }
    })
    url = prefix + '/restconf/data/yang-catalog:catalog/modules/'
    response = requests.patch(url, json_modules_data,
                              auth=(args.credentials[0],
                                    args.credentials[1]),
                              headers={
                                  'Accept': 'application/yang-data+json',
                                  'Content-type': 'application/yang-data+json'})

    if response.status_code < 200 or response.status_code > 299:
        path_to_file = '{}/modules-confd-data-rest'.format(direc)
        with open(path_to_file, 'w') as f:
            json.dump(json_modules_data, f)
        LOGGER.error('Request with body {} on path {} failed with {}'
                     .format(path_to_file, url,
                             response.text))

    # In each json
    LOGGER.info('Starting to add vendors')
    if os.path.exists('{}/normal.json'.format(direc)):
        x = -1
        with open('{}/normal.json'.format(direc)) as data:
            vendors = json.loads(data.read())['vendors']['vendor']
            for x in range(0, int(len(vendors) / 1000)):
                json_implementations_data = json.dumps({
                    'vendors':
                        {
                            'vendor': vendors[x * 1000: (x * 1000) + 1000]
                        }
                })

                # Make a PATCH request to create a root for each file
                url = prefix + '/restconf/data/yang-catalog:catalog/vendors/'
                response = requests.patch(url, json_implementations_data,
                                          auth=(args.credentials[0],
                                                args.credentials[1]),
                                          headers={
                                              'Accept': 'application/yang-data+json',
                                              'Content-type': 'application/yang-data+json'})
                if response.status_code < 200 or response.status_code > 299:
                    path_to_file = '{}/vendors-confd-data-{}'.format(direc, x)
                    with open(path_to_file, 'w') as f:
                        json.dump(json_modules_data, f)
                    LOGGER.error('Request with body {} on path {} failed with {}'.
                                 format(path_to_file, url,
                                        response.text))
            json_implementations_data = json.dumps({
                'vendors':
                    {
                        'vendor': vendors[(x * 1000) + 1000:]
                    }
            })
            url = prefix + '/restconf/data/yang-catalog:catalog/vendors/'
            response = requests.patch(url, json_implementations_data,
                                      auth=(args.credentials[0],
                                            args.credentials[1]),
                                      headers={
                                          'Accept': 'application/yang-data+json',
                                          'Content-type': 'application/yang-data+json'})
            if response.status_code < 200 or response.status_code > 299:
                path_to_file = '{}/vendors-confd-data-rest'.format(direc)
                with open(path_to_file, 'w') as f:
                    json.dump(json_modules_data, f)
                LOGGER.error('Request with body {} on path {} failed with {}'
                             .format(json_implementations_data, url,
                                     response.text))
    if body_to_send != '':
        LOGGER.info('Sending files for indexing')
        send_to_indexing(body_to_send, args.credentials, args.api_protocol, LOGGER, key, args.api_ip)
    if not args.api:
        if not args.force_indexing:
            process_reload_cache = multiprocessing.Process(target=reload_cache_in_parallel,
                                                           args=(args.credentials, yangcatalog_api_prefix,))
            process_reload_cache.start()
            LOGGER.info('Run complicated algorithms')
            recursion_limit = sys.getrecursionlimit()
            sys.setrecursionlimit(50000)
            complicatedAlgorithms = ModulesComplicatedAlgorithms(log_directory, yangcatalog_api_prefix,
                                                                 args.credentials,
                                                                 args.protocol, args.ip, args.port, args.save_file_dir,
                                                                 direc, None, yang_models, temp_dir)
            complicatedAlgorithms.parse_non_requests()
            LOGGER.info('Waiting for cache reload to finish')
            process_reload_cache.join()
            complicatedAlgorithms.parse_requests()
            sys.setrecursionlimit(recursion_limit)
            LOGGER.info('Populating with new data of complicated algorithms')
            complicatedAlgorithms.populate()
            end = time.time()
            LOGGER.info('Populate took {} seconds with the main and complicated algorithm'.format(end - start))
        else:
            url = (yangcatalog_api_prefix + 'load-cache')
            LOGGER.info('{}'.format(url))
            response = requests.post(url, None,
                                     auth=(args.credentials[0],
                                           args.credentials[1]))
            if response.status_code != 201:
                LOGGER.warning('Could not send a load-cache request')

        try:
            shutil.rmtree('{}'.format(direc))
        except OSError:
            # Be happy if deleted
            pass
    LOGGER.info('Populate script finished successfully')

if __name__ == "__main__":
    main()
