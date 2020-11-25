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
Rabbitmq is needed to be installed for this script to work.
This script is part of messaging algorithm works together
with sender.py. Api endpoints that take too long time to
process will send a request to process data to this Receiver
with some message id. Once receiver is done processing data
it will send back the response using the message id.

Receiver is used to add, update or remove yang modules.
This process take a long time depending on the number
of the yang modules. This script is also used to automatically
add or update new IETF and Openconfig modules.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import errno
import json
import logging
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from distutils.dir_util import copy_tree

import pika
import requests
import utility.log as log
from parseAndPopulate.modulesComplicatedAlgorithms import ModulesComplicatedAlgorithms
from utility import messageFactory
from utility.util import prepare_to_indexing, send_to_indexing

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


class Receiver:

    def __init__(self, config_path):
        self.__config_path = config_path
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(self.__config_path)
        self.__confd_ip = config.get('Web-Section', 'confd-ip')
        self.__confdPort = int(config.get('Web-Section', 'confd-port'))
        self.__protocol = config.get('General-Section', 'protocol-api')
        self.__api_ip = config.get('Web-Section', 'ip')
        self.__api_port = int(config.get('Web-Section', 'api-port'))
        self.__api_protocol = config.get('General-Section', 'protocol-api')
        self.__confd_protocol = config.get('General-Section', 'protocol-confd')
        self.__key = config.get('Secrets-Section', 'update-signature')
        self.__notify_indexing = config.get('General-Section', 'notify-index')
        self.__result_dir = config.get('Web-Section', 'result-html-dir')
        self.__save_file_dir = config.get('Directory-Section', 'save-file-dir')
        self.__yang_models = config.get('Directory-Section', 'yang-models-dir')
        self.__is_uwsgi = config.get('General-Section', 'uwsgi')
        self.__rabbitmq_host = config.get('RabbitMQ-Section', 'host', fallback='127.0.0.1')
        self.__rabbitmq_port = int(config.get('RabbitMQ-Section', 'port', fallback='5672'))
        self.__rabbitmq_virtual_host = config.get('RabbitMQ-Section', 'virtual-host', fallback='/')
        rabbitmq_username = config.get('RabbitMQ-Section', 'username', fallback='guest')
        rabbitmq_password = config.get('Secrets-Section', 'rabbitMq-password', fallback='guest')
        self.__log_directory = config.get('Directory-Section', 'logs')
        self.LOGGER = log.get_logger('receiver', self.__log_directory + '/yang.log')
        logging.getLogger('pika').setLevel(logging.INFO)
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.__confd_credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()

        self.LOGGER.info('Starting receiver')

        if self.__notify_indexing == 'True':
            self.__notify_indexing = True
        else:
            self.__notify_indexing = False
        separator = ':'
        suffix = self.__api_port
        if self.__is_uwsgi == 'True':
            separator = '/'
            suffix = 'api'
        self.__yangcatalog_api_prefix = '{}://{}{}{}/'.format(self.__api_protocol, self.__api_ip,
                                                              separator, suffix)
        self.__response_type = ['Failed', 'Finished successfully']
        self.__rabbitmq_credentials = pika.PlainCredentials(
            username=rabbitmq_username,
            password=rabbitmq_password)
        self.channel = None
        self.connection = None

    def copytree(self, src, dst):
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                copy_tree(s, d)
            else:
                shutil.copy2(s, d)

    def process_sdo(self, arguments, all_modules):
        """Processes SDOs. Calls populate script which calls script to parse all the modules
        on the given path which is one of the params. Populate script will also send the
        request to populate confd on given ip and port. It will also copy all the modules to
        parent directory of this project /api/sdo. It will also call indexing script to
        update searching.
                Arguments:
                    :param arguments: (list) list of arguments sent from api sender
                    :return (__response_type) one of the response types which is either
                        'Failed' or 'Finished successfully'
        """
        self.LOGGER.info('Processing sdo')
        tree_created = True if arguments[-4] == 'True' else False
        arguments = arguments[:-4]
        direc = arguments[6]
        arguments.append('--api-ip')
        arguments.append(self.__api_ip)
        arguments.append("--result-html-dir")
        arguments.append(self.__result_dir)
        arguments.append('--api-port')
        arguments.append(repr(self.__api_port))
        arguments.append('--api-protocol')
        arguments.append(self.__api_protocol)
        arguments.append('--save-file-dir')
        arguments.append(self.__save_file_dir)
        if self.__notify_indexing:
            arguments.append('--notify-indexing')

        with open(self.temp_dir + "/process-sdo-api-stderr.txt", "w") as f:
            try:
                self.LOGGER.info('processing arguments {}'.format(arguments))
                subprocess.check_call(arguments, stderr=f)
            except subprocess.CalledProcessError as e:
                shutil.rmtree(direc)
                self.LOGGER.error('Server error: {}'.format(e))
                return self.__response_type[0] + '#split#Server error while parsing or populating data'

        try:
            os.makedirs(self.temp_dir + '/sdo/')
        except OSError as e:
            # be happy if someone already created the path
            if e.errno != errno.EEXIST:
                return self.__response_type[0] + '#split#Server error - could not create directory'

        if tree_created:
            self.copytree(direc + "/temp/", self.temp_dir + "/sdo")
            with open(direc + '/prepare.json', 'r') as f:
                all_modules.update(json.load(f))

        return self.__response_type[1]

    def process_vendor(self, arguments, all_modules):
        """Processes vendors. Calls populate script which calls script to parse all
        the modules that are contained in the given hello message xml file or in
        ietf-yang-module xml file which is one of the params. Populate script will
        also send the request to populate confd on given ip and port. It will also
        copy all the modules to parent directory of this project /api/sdo.
        It will also call indexing script to update searching.
                Arguments:
                    :param arguments: (list) list of arguments sent from api sender
                    :return (__response_type) one of the response types which is
                     either 'Failed' or 'Finished successfully'
        """
        self.LOGGER.debug('Processing vendor')
        tree_created = True if arguments[-5] == 'True' else False
        integrity_file_location = arguments[-4]

        arguments = arguments[:-5]
        direc = arguments[5]
        arguments.append('--api-ip')
        arguments.append(self.__api_ip)
        arguments.append("--result-html-dir")
        arguments.append(self.__result_dir)
        arguments.append('--save-file-dir')
        arguments.append(self.__save_file_dir)
        if self.__notify_indexing:
            arguments.append('--notify-indexing')

        with open(self.temp_dir + "/process-vendor-api-stderr.txt", "w") as f:
            try:
                subprocess.check_call(arguments, stderr=f)
            except subprocess.CalledProcessError as e:
                shutil.rmtree(direc)
                self.LOGGER.error('Server error: {}'.format(e))
                return self.__response_type[0] + '#split#Server error while parsing or populating data'
        try:
            os.makedirs(self.temp_dir + '/vendor/')
        except OSError as e:
            # be happy if someone already created the path
            if e.errno != errno.EEXIST:
                self.LOGGER.error('Server error: {}'.format(e))
                return self.__response_type[0] + '#split#Server error - could not create directory'

        self.copytree(direc + "/temp/", self.temp_dir + "/vendor")
        #    subprocess.call(["cp", "-r", direc + "/temp/.", temp_dir + "/vendor/"])

        if tree_created:
            with open(direc + '/prepare.json',
                      'r') as f:
                all_modules.update(json.load(f))

        integrity_file_name = datetime.utcnow().strftime("%Y-%m-%dT%H:%m:%S.%f")[:-3] + 'Z'

        if integrity_file_location != './':
            shutil.move('./integrity.html', integrity_file_location + 'integrity' + integrity_file_name + '.html')
        return self.__response_type[1]

    def process_vendor_deletion(self, arguments):
        """Deletes vendors. It calls the delete request to confd to delete all the module
        in vendor branch of the yang-catalog.yang module on given path. If the module was
        added by vendor and it doesn't contain any other implementations it will delete the
        whole module in modules branch of the yang-catalog.yang module. It will also call
        indexing script to update searching.
                Arguments:
                    :param arguments: (list) list of arguments sent from api sender
                    :return (__response_type) one of the response types which is either
                        'Failed' or 'Finished successfully'
        """
        vendor, platform, software_version, software_flavor = arguments[0:4]
        credentials = arguments[7:9]
        path_to_delete = arguments[9]

        try:
            with open('./cache/catalog.json', 'r') as catalog:
                vendors_data = json.load(catalog)['yang-catalog:catalog']['vendors']
        except IOError:
            self.LOGGER.warning('Cache file does not exist')
            # Try to create a cache if not created yet and load data again
            response = self.make_cache(credentials)
            if response.status_code != 201:
                return self.__response_type[0] + '#split#Server error-> could not reload cache'
            else:
                try:
                    with open('./cache/catalog.json', 'r') as catalog:
                        vendors_data = json.load(catalog)['yang-catalog:catalog']['vendors']
                except:
                    self.LOGGER.error('Unexpected error: {}'.format(sys.exc_info()[0]))
                    return self.__response_type[0] + '#split#' + sys.exc_info()[0]

        modules = set()
        modules_that_succeeded = []
        self.iterate_in_depth(vendors_data, modules)

        response = requests.delete(path_to_delete, auth=(credentials[0], credentials[1]))
        if response.status_code == 404:
            pass
            # return __response_type[0] + '#split#not found'

        for mod in modules:
            try:
                path = self.__confd_protocol + '://' + self.__confd_ip + ':' + repr(
                    self.__confdPort) + '/restconf/data/yang-catalog:catalog/modules/module=' \
                       + mod
                modules_data = requests.get(path, auth=(credentials[0], credentials[1]),
                                            headers={'Content-Type': 'application/yang-data+json',
                                                     'Accept': 'application/yang-data+json'}).json()
                implementations = modules_data['yang-catalog:module']['implementations']['implementation']
                count_of_implementations = len(implementations)
                count_deleted = 0
                for imp in implementations:
                    imp_key = ''
                    if vendor and vendor != imp['vendor']:
                        continue
                    else:
                        imp_key += imp['vendor']
                    if platform != 'None' and platform != imp['platform']:
                        continue
                    else:
                        imp_key += ',' + imp['platform']
                    if software_version != 'None' and software_version != imp['software-version']:
                        continue
                    else:
                        imp_key += ',' + imp['software-version']
                    if software_flavor != 'None' and software_flavor != imp['software-flavor']:
                        continue
                    else:
                        imp_key += ',' + imp['software-flavor']

                    url = path + '/implementations/implementation=' + imp_key
                    response = requests.delete(url, auth=(credentials[0], credentials[1]))

                    if response.status_code != 204:
                        self.LOGGER.error('Couldn\'t delete implementation of module on path {} because of error: {}'
                                          .format(path + '/implementations/implementation=' + imp_key, response.text))
                        continue
                    count_deleted += 1

                if (count_deleted == count_of_implementations and
                        count_of_implementations != 0):
                    name, revision, organization = mod.split(',')
                    if organization == vendor:
                        response = requests.delete(path, auth=(credentials[0], credentials[1]))
                        to_add = '{}@{}/{}'.format(name, revision, organization)
                        modules_that_succeeded.append(to_add)
                        if response.status_code != 204:
                            self.LOGGER.error(
                                'Could not delete module on path {} because of error: {}'.format(path, response.text))
                            continue
            except:
                self.LOGGER.error('Yang file {} doesn\'t exist although it should exist'.format(mod))
        all_mods = requests.get('{}search/modules'.format(self.__yangcatalog_api_prefix)).json()

        for mod in modules:
            name_rev_org_with_commas = mod.split('/')[-1]
            name, rev, org = name_rev_org_with_commas.split(',')
            for existing_module in all_mods['module']:
                if existing_module.get('dependents') is not None:
                    dependents = existing_module['dependents']
                    for dep in dependents:
                        if dep['name'] == name and dep['revision'] == rev:
                            path = '{}://{}:{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}/dependents={}'
                            response = requests.delete(path.format(self.__confd_protocol, self.__confd_ip, self.__confdPort,
                                                                   existing_module['name'], existing_module['revision'],
                                                                   existing_module['organization'], dep['name']))
                            if response.status_code != 204:
                                self.LOGGER.error('Couldn\'t delete module on path {}. Error : {}'
                                                  .format(path, response.text))
                                return self.__response_type[0] + '#split#' + response.text
        if self.__notify_indexing:
            body_to_send = prepare_to_indexing(self.__yangcatalog_api_prefix, modules_that_succeeded,
                                               credentials, self.LOGGER, self.__save_file_dir, self.temp_dir,
                                               self.__confd_protocol, self.__confd_ip, self.__confdPort, delete=True)
            if body_to_send != '':
                send_to_indexing(body_to_send, credentials, self.__api_protocol, self.LOGGER, self.__key, self.__api_ip)
        return self.__response_type[1]

    def iterate_in_depth(self, value, modules):
        """Iterates through the branch to get to the level with modules
                Arguments:
                    :param value: (dict) data through which we will need to iterate
                    :param modules: (set) set that will contain all the modules that
                     need to be deleted
        """
        if sys.version_info >= (3, 4):
            items = value.items()
        else:
            items = value.iteritems()
        for key, val in items:
            if key == 'protocols':
                continue
            if isinstance(val, list):
                for v in val:
                    self.iterate_in_depth(v, modules)
            if isinstance(val, dict):
                if key == 'modules':
                    for mod in val['module']:
                        name = mod['name']
                        revision = mod['revision']
                        organization = mod['organization']
                        modules.add(name + ',' + revision + ',' + organization)
                else:
                    self.iterate_in_depth(val, modules)

    def make_cache(self, credentials):
        """After we delete or add modules we need to reload all the modules to the file
        for qucker search. This module is then loaded to the memory.
                Arguments:
                    :param response: (str) Contains string 'work' which will be sent back if
                        everything went through fine
                    :param credentials: (list) Basic authorization credentials - username, password
                        respectively
                    :return 'work' if everything went through fine otherwise send back the reason why
                        it failed.
        """
        path = self.__yangcatalog_api_prefix + 'load-cache'
        response = requests.post(path, auth=(credentials[0], credentials[1]),
                                 headers={'Content-Type': 'application/json',
                                          'Accept': 'application/json'}
                                 )
        code = response.status_code

        if code != 200 and code != 201 and code != 204:
            self.LOGGER.error('Could not load json to memory-cache. Error: {} {}'.format(response.text, code))
        return response

    def process_module_deletion(self, arguments, multiple=False):
        """Deletes module. It calls the delete request to confd to delete module on
        given path. This will delete whole module in modules branch of the
        yang-catalog.yang module. It will also call indexing script to update
        searching.
                    Arguments:
                        :param multiple: (boolean) removing multiple modules at once
                        :param arguments: (list) list of arguments sent from api
                         sender
                        :return (__response_type) one of the response types which
                         is either 'Failed' or 'Finished successfully'
        """
        credentials = arguments[3:5]
        path_to_delete = arguments[5]
        if multiple:
            paths = []
            modules = json.loads(path_to_delete)['modules']
            for mod in modules:
                paths.append(self.__confd_protocol + '://' + self.__confd_ip + ':' + repr(
                    self.__confdPort) + '/restconf/data/yang-catalog:catalog/modules/module/' \
                             + mod['name'] + ',' + mod['revision'] + ',' + mod[
                                 'organization'])
        else:
            name_rev_org_with_commas = path_to_delete.split('/')[-1]
            name, rev, org = name_rev_org_with_commas.split(',')
            modules = [{'name': name, 'revision': rev, 'organization': org}]
            paths = [path_to_delete]
        all_mods = requests.get('{}search/modules'.format(self.__yangcatalog_api_prefix)).json()

        for mod in modules:
            for existing_module in all_mods['module']:
                if existing_module.get('dependents') is not None:
                    dependents = existing_module['dependents']
                    for dep in dependents:
                        if dep['name'] == mod['name'] and dep['revision'] == mod['revision']:
                            path = '{}://{}:{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}/dependents={}'
                            response = requests.delete(path.format(self.__confd_protocol, self.__confd_ip, self.__confdPort,
                                                                   existing_module['name'], existing_module['revision'],
                                                                   existing_module['organization'], dep['name']))
                            if response.status_code != 204:
                                self.LOGGER.error('Couldn\'t delete module on path {}. Error : {}'
                                                  .format(path, response.text))
                                return self.__response_type[0] + '#split#' + response.text
        modules_to_index = []
        for path in paths:
            response = requests.delete(path, auth=(credentials[0], credentials[1]))
            if response.status_code != 204:
                self.LOGGER.error('Couldn\'t delete module on path {}. Error : {}'
                                  .format(path, response.text))
                return self.__response_type[0] + '#split#' + response.text
            name, revision, organization = path.split('/')[-1].split(',')
            modules_to_index.append('{}@{}/{}'.format(name, revision, organization))
        if self.__notify_indexing:
            body_to_send = prepare_to_indexing(self.__yangcatalog_api_prefix, modules_to_index,credentials,
                                               self.LOGGER, self.__save_file_dir, self.temp_dir,
                                               self.__confd_protocol, self.__confd_ip, self.__confdPort,
                                               delete=True)
            if body_to_send != '':
                send_to_indexing(body_to_send, credentials, self.__api_protocol, self.LOGGER, self.__key, self.__api_ip)
        return self.__response_type[1]

    def run_ietf(self):
        """
        Runs ietf and openconfig scripts that should update all the new ietf
        and openconfig modules
        :return: response success or failed
        """
        try:
            with open(self.temp_dir + "/run-ietf-api-stderr.txt", "w") as f:
                draft_pull_local = os.path.dirname(
                    os.path.realpath(__file__)) + '/../ietfYangDraftPull/draftPullLocal.py'
                arguments = ['python', draft_pull_local]
                subprocess.check_call(arguments, stderr=f)
            with open(self.temp_dir + "/run-openconfig-api-stderr.txt", "w") as f:
                openconfig_pull_local = os.path.dirname(
                    os.path.realpath(__file__)) + '/../ietfYangDraftPull/openconfigPullLocal.py'
                arguments = ['python', openconfig_pull_local]
                subprocess.check_call(arguments, stderr=f)
            return self.__response_type[1]
        except subprocess.CalledProcessError as e:
            self.LOGGER.error('Server error: {}'.format(e))
            return self.__response_type[0]

    def load_config(self):
        self.LOGGER.info('reloading config')
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(self.__config_path)
        self.__confd_ip = config.get('Web-Section', 'confd-ip')
        self.__confdPort = int(config.get('Web-Section', 'confd-port'))
        self.__protocol = config.get('General-Section', 'protocol-api')
        self.__api_ip = config.get('Web-Section', 'ip')
        self.__api_port = int(config.get('Web-Section', 'api-port'))
        self.__api_protocol = config.get('General-Section', 'protocol-api')
        self.__confd_protocol = config.get('General-Section', 'protocol-confd')
        self.__key = config.get('Secrets-Section', 'update-signature')
        self.__notify_indexing = config.get('General-Section', 'notify-index')
        self.__result_dir = config.get('Web-Section', 'result-html-dir')
        self.__save_file_dir = config.get('Directory-Section', 'save-file-dir')
        self.__yang_models = config.get('Directory-Section', 'yang-models-dir')
        self.__is_uwsgi = config.get('General-Section', 'uwsgi')
        self.__rabbitmq_host = config.get('RabbitMQ-Section', 'host', fallback='127.0.0.1')
        self.__rabbitmq_port = int(config.get('RabbitMQ-Section', 'port', fallback='5672'))
        self.__rabbitmq_virtual_host = config.get('RabbitMQ-Section', 'virtual-host', fallback='/')
        rabbitmq_username = config.get('RabbitMQ-Section', 'username', fallback='guest')
        rabbitmq_password = config.get('Secrets-Section', 'rabbitMq-password', fallback='guest')
        self.__log_directory = config.get('Directory-Section', 'logs')
        self.LOGGER = log.get_logger('receiver', self.__log_directory + '/yang.log')
        logging.getLogger('pika').setLevel(logging.INFO)
        self.temp_dir = config.get('Directory-Section', 'temp')

        if self.__notify_indexing == 'True':
            self.__notify_indexing = True
        else:
            self.__notify_indexing = False
        separator = ':'
        suffix = self.__api_port
        if self.__is_uwsgi == 'True':
            separator = '/'
            suffix = 'api'
        self.__yangcatalog_api_prefix = '{}://{}{}{}/'.format(self.__api_protocol, self.__api_ip,
                                                              separator, suffix)
        self.__response_type = ['Failed', 'Finished successfully']
        self.__rabbitmq_credentials = pika.PlainCredentials(
            username=rabbitmq_username,
            password=rabbitmq_password)
        try:
            self.channel.close()
        except Exception:
            pass
        try:
            self.connection.close()
        except Exception:
            pass
        self.LOGGER.info('config reloaded succesfully')

    def on_request(self, ch, method, props, body):
        process_reload_cache = multiprocessing.Process(target=self.on_request_thread_safe, args=(ch, method, props, body,))
        process_reload_cache.start()

    def on_request_thread_safe(self, ch, method, props, body):
        """Function called when something was sent from API sender. This function
        will process all the requests that would take too long to process for API.
        When the processing is done we will sent back the result of the request
        which can be either 'Failed' or 'Finished successfully' with corespondent
        correlation id. If the request 'Failed' it will sent back also a reason why
        it failed.
                Arguments:
                    :param body: (str) String of arguments that need to be processed
                    separated by '#'.
        """
        try:
            if sys.version_info >= (3, 4):
                body = body.decode(encoding='utf-8', errors='strict')
            self.LOGGER.info('Received request with body {}'.format(body))
            arguments = body.split('#')
            if body == 'run_ietf':
                self.LOGGER.info('Running all ietf and openconfig modules')
                final_response = self.run_ietf()
            elif body == 'reload_config':
                self.load_config()
            elif 'run_ping' == arguments[0]:
                final_response = self.run_ping(arguments[1])
            elif 'run_script' == arguments[0]:
                final_response = self.run_script(arguments[1:])
            elif 'github' == arguments[-1]:
                self.LOGGER.info('Github automated message starting to populate')
                paths_plus = arguments[arguments.index('repoLocalDir'):]
                self.LOGGER.info('paths plus {}'.format(paths_plus))
                arguments = arguments[:arguments.index('repoLocalDir')]
                self.LOGGER.info('arguments {}'.format(arguments))
                paths = paths_plus[1:-2]
                self.LOGGER.info('paths {}'.format(paths))
                try:
                    for path in paths:
                        with open(self.temp_dir + "/log_trigger.txt", "w") as f:
                            local_dir = paths_plus[-2]
                            arguments = arguments + ["--dir", local_dir + "/" + path]
                            if self.__notify_indexing:
                                arguments.append('--notify-indexing')
                            subprocess.check_call(arguments, stderr=f)
                    final_response = self.__response_type[1]
                except subprocess.CalledProcessError as e:
                    final_response = self.__response_type[0]
                    mf = messageFactory.MessageFactory()
                    mf.send_automated_procedure_failed(arguments, self.temp_dir + "/log_no_sdo_api.txt")
                    self.LOGGER.error(
                        'check log_trigger.txt Error calling process populate.py because {}\n\n with error {}'.format(
                            e.output, e.stderr))
                except:
                    final_response = self.__response_type[0]
                    self.LOGGER.error("check log_trigger.txt failed to process github message with error {}".format(
                        sys.exc_info()[0]))
            else:
                all_modules = {}
                if arguments[-3] == 'DELETE':
                    self.LOGGER.info('Deleting single module')
                    if 'http' in arguments[0]:
                        final_response = self.process_module_deletion(arguments)
                        credentials = arguments[3:5]
                    else:
                        final_response = self.process_vendor_deletion(arguments)
                        credentials = arguments[7:9]
                elif arguments[-3] == 'DELETE_MULTIPLE':
                    self.LOGGER.info('Deleting multiple modules')
                    final_response = self.process_module_deletion(arguments, True)
                    credentials = arguments[3:5]
                elif '--sdo' in arguments[2]:
                    final_response = self.process_sdo(arguments, all_modules)
                    credentials = arguments[11:13]
                    direc = arguments[6]
                    shutil.rmtree(direc)
                else:
                    final_response = self.process_vendor(arguments, all_modules)
                    credentials = arguments[10:12]
                    direc = arguments[5]
                    shutil.rmtree(direc)
                if final_response.split('#split#')[0] == self.__response_type[1]:
                    res = self.make_cache(credentials)
                    if res.status_code != 201:
                        final_response = self.__response_type[0] + '#split#Server error-> could not reload cache'

                    if all_modules:
                        complicated_algorithms = ModulesComplicatedAlgorithms(self.__log_directory,
                                                                              self.__yangcatalog_api_prefix,
                                                                              self.__confd_credentials, self.__confd_protocol,
                                                                              self.__confd_ip, self.__confdPort,
                                                                              self.__save_file_dir, direc,
                                                                              all_modules, self.__yang_models,
                                                                              self.temp_dir)
                        complicated_algorithms.parse_non_requests()
                        complicated_algorithms.parse_requests()
                        complicated_algorithms.populate()
        except Exception as e:
            final_response = self.__response_type[0]
            self.LOGGER.error("receiver failed with message {}".format(e))
        self.LOGGER.info('Receiver is done with id - {} and message = {}'
                         .format(props.correlation_id, str(final_response)))

        f = open('{}/correlation_ids'.format(self.temp_dir), 'r')
        lines = f.readlines()
        f.close()
        with open('{}/correlation_ids'.format(self.temp_dir), 'w') as f:
            for line in lines:
                if props.correlation_id in line:
                    new_line = '{} -- {} - {}\n'.format(datetime.now()
                                                        .ctime(),
                                                        props.correlation_id,
                                                        str(final_response))
                    f.write(new_line)
                else:
                    f.write(line)

    def start_receiving(self):
        while True:
            try:
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                    host=self.__rabbitmq_host,
                    port=self.__rabbitmq_port,
                    heartbeat=10,
                    credentials=self.__rabbitmq_credentials))
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue='module_queue')

                self.channel.basic_qos(prefetch_count=1)
                self.channel.basic_consume('module_queue', self.on_request, auto_ack=True)

                self.LOGGER.info('Awaiting RPC request')

                self.channel.start_consuming()
            except Exception as e:
                self.LOGGER.error('Exception: {}'.format(str(e)))
                time.sleep(10)
                try:
                    self.channel.close()
                except Exception:
                    pass
                try:
                    self.connection.close()
                except Exception:
                    pass

    def run_script(self, arguments):
        module_name = arguments[0]
        script_name = arguments[1]
        body_input = json.loads(arguments[2])
        try:
            # Load submodule and its config
            module = __import__(module_name, fromlist=[script_name])
            submodule = getattr(module, script_name)
            script_conf = submodule.ScriptConfig()
            script_args_list = script_conf.get_args_list()

            for key in body_input:
                if (key != 'credentials' and body_input[key] != script_args_list[key]['default']):
                    script_conf.args.__setattr__(key, body_input[key])

            submodule.main(scriptConf=script_conf)
            return self.__response_type[1]
        except subprocess.CalledProcessError as e:
            self.LOGGER.error('Server error: {}'.format(e))
            return self.__response_type[0]

    def run_ping(self, message):
        if message == 'ping':
            return self.__response_type[1]
        else:
            return self.__response_type[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')
    args, extra_args = parser.parse_known_args()
    config_path = args.config_path
    receiver = Receiver(config_path)
    receiver.start_receiving()
