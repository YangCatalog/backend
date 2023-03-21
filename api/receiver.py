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
This script is part of a messaging system which works together
with sender.py. Some API endpoints that take too long to process
request so sender.py will send a request to process data to this Receiver.
Once the receiver is done with processing data it will send back the
response using the message id.

The receiver is used to add, update or remove yang modules and vendors.
This process take a long time depending on the number
of the yang modules. This script is also used to automatically
add or update new IETF and Openconfig modules or run other scripts as subprocesses.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import argparse
import functools
import json
import logging
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
import typing as t
from datetime import datetime
from distutils.dir_util import copy_tree

import pika
import requests

import utility.log as log
from api.status_message import StatusMessage
from redisConnections.redisConnection import RedisConnection, key_quote
from utility import message_factory
from utility.create_config import create_config
from utility.elasticsearch_util import ESIndexingPaths, prepare_for_es_removal, send_for_es_indexing
from utility.staticVariables import json_headers


class Receiver:
    def __init__(self, config_path: str):
        self._config_path = config_path
        self.load_config()
        self.channel = None
        self.connection = None
        self.redisConnection = RedisConnection()
        self.LOGGER.info('Receiver started')

    def copytree(self, src: str, dst: str):
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                copy_tree(s, d)
            else:
                shutil.copy2(s, d)

    def process(self, arguments: t.List[str]) -> t.Tuple[StatusMessage, str]:
        """Process modules. Calls populate.py script which will parse the modules
        on the given path given by "dir" param. Populate script will also send the
        request to populate Redis running on given IP and port. It will also copy all the modules to
        parent directory of this project /api/sdo and finally also call indexing script to update searching.

        Arguments:
            :param arguments    (list) list of arguments sent from API sender
            :return (__response_type) one of the response types which is either
                'Failed' or 'Finished successfully'
        """
        sdo = '--sdo' in arguments
        api = '--api' in arguments
        i = arguments.index('--dir')
        direc = arguments[i + 1]

        script_name = 'populate'
        module = __import__('parseAndPopulate', fromlist=[script_name])
        submodule = getattr(module, script_name)
        script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()
        # Set populate script arguments
        script_conf.args.__setattr__('sdo', sdo)
        script_conf.args.__setattr__('api', api)
        script_conf.args.__setattr__('dir', direc)
        if self._notify_indexing:
            script_conf.args.__setattr__('notify_indexing', True)
            script_conf.args.__setattr__('force_indexing', True)

        self.LOGGER.info(
            'Runnning populate.py script with following configuration:\n{}'.format(script_conf.args.__dict__),
        )
        try:
            submodule.main(script_conf=script_conf)
        except Exception:
            self.LOGGER.exception('Problem while running populate script')
            return StatusMessage.FAIL, 'Server error while running populate script'

        return StatusMessage.SUCCESS, ''

    def process_vendor_deletion(self, arguments: t.List[str]) -> StatusMessage:
        """Deleting vendors metadata. It deletes all the module in vendor branch of the yang-catalog.yang
        module on given path. If the module was added by vendor and it doesn't contain any other implementations
        it will delete the whole module in modules branch of the yang-catalog.yang module.
        It will also call indexing script to update Elasticsearch searching.

        Argument:
            :param arguments    (list) list of arguments sent from API sender
            :return (__response_type) one of the response types which
                is either 'Finished successfully' or 'In progress'
        """
        vendor, platform, software_version, software_flavor = arguments[3:]

        redis_vendor_key = ''
        data_key = 'vendor'
        if vendor != 'None':
            redis_vendor_key += key_quote(vendor)
            data_key = 'yang-catalog:vendor'
        if platform != 'None':
            redis_vendor_key += '/{}'.format(key_quote(platform))
            data_key = 'yang-catalog:platform'
        if software_version != 'None':
            redis_vendor_key += '/{}'.format(key_quote(software_version))
            data_key = 'yang-catalog:software-version'
        if software_flavor != 'None':
            redis_vendor_key += '/{}'.format(key_quote(software_flavor))
            data_key = 'yang-catalog:software-flavor'

        redis_vendor_data = self.redisConnection.create_vendors_data_dict(redis_vendor_key)
        vendor_data = {data_key: redis_vendor_data}

        modules_keys = set()
        deleted_modules = []
        self.iterate_in_depth(vendor_data, modules_keys)

        # Delete implementation
        for mod_key in modules_keys:
            try:
                name, revision, organization = mod_key.split(',')
                redis_key = '{}@{}/{}'.format(name, revision, organization)
                raw_data = self.redisConnection.get_module(redis_key)
                modules_data = json.loads(raw_data)
                implementations = modules_data.get('implementations', {}).get('implementation', [])

                count_of_implementations = len(implementations)
                count_deleted = 0
                for implementation in implementations:
                    imp_key = ''
                    if vendor and vendor != implementation['vendor']:
                        continue
                    else:
                        imp_key += implementation['vendor']
                    if platform != 'None' and platform != implementation['platform']:
                        continue
                    else:
                        imp_key += ',{}'.format(implementation['platform'])
                    if software_version != 'None' and software_version != implementation['software-version']:
                        continue
                    else:
                        imp_key += ',{}'.format(implementation['software-version'])
                    if software_flavor != 'None' and software_flavor != implementation['software-flavor']:
                        continue
                    else:
                        imp_key += ',{}'.format(implementation['software-flavor'])

                    # Delete module implementation from Redis
                    response = self.redisConnection.delete_implementation(redis_key, imp_key)
                    if response:
                        self.LOGGER.info(
                            'Implementation {} deleted from module {} successfully'.format(imp_key, mod_key),
                        )
                    elif response == 0:
                        self.LOGGER.debug('Implementation {} already deleted from module {}'.format(imp_key, mod_key))
                    count_deleted += 1

                if count_deleted == count_of_implementations and count_of_implementations != 0:
                    if organization == vendor:
                        deletion_problem = False

                        # Delete module from Redis
                        response = self.redisConnection.delete_modules([redis_key])
                        if response == 1:
                            self.LOGGER.info('Module {} deleted successfully'.format(redis_key))
                        elif response == 0:
                            self.LOGGER.debug('Module {} already deleted'.format(redis_key))

                        if not deletion_problem:
                            deleted_modules.append(redis_key)
            except Exception:
                self.LOGGER.exception('YANG file {} doesn\'t exist although it should exist'.format(mod_key))
        raw_all_modules = self.redisConnection.get_all_modules()
        all_modules = json.loads(raw_all_modules)

        # Delete dependets
        for module_key in modules_keys:
            name, revision, organization = module_key.split(',')
            redis_key = '{}@{}/{}'.format(name, revision, organization)
            for existing_module in all_modules.values():
                if existing_module.get('dependents') is not None:
                    dependents = existing_module['dependents']
                    for dependent in dependents:
                        if dependent['name'] == name and dependent.get('revision') == revision:
                            mod_key_redis = '{}@{}/{}'.format(
                                existing_module['name'],
                                existing_module['revision'],
                                existing_module['organization'],
                            )
                            # Delete module's dependent from Redis
                            self.redisConnection.delete_dependent(mod_key_redis, dependent['name'])

        # Delete vendor branch from Redis
        response = self.redisConnection.delete_vendor(redis_vendor_key)

        if self._notify_indexing:
            body_to_send = prepare_for_es_removal(
                self._yangcatalog_api_prefix,
                deleted_modules,
                self._save_file_dir,
                self.LOGGER,
            )
            if body_to_send.get('modules-to-delete'):
                send_for_es_indexing(body_to_send, self.LOGGER, self.indexing_paths)
        return StatusMessage.SUCCESS

    def iterate_in_depth(self, value: dict, modules_keys: t.Set[str]):
        """Iterates through the branch to get to the level with modules.

        Arguments:
            :param value            (dict) data through which we will need to iterate
            :param modules_keys     (set) set that will contain all the modules that need to be deleted
        """
        for key, val in value.items():
            if key == 'protocols':
                continue
            if isinstance(val, list):
                for v in val:
                    self.iterate_in_depth(v, modules_keys)
            if isinstance(val, dict):
                if key == 'modules':
                    for mod in val['module']:
                        mod_key = '{},{},{}'.format(mod['name'], mod['revision'], mod['organization'])
                        modules_keys.add(mod_key)
                else:
                    self.iterate_in_depth(val, modules_keys)

    def make_cache(self, credentials: t.List[str]) -> requests.Response:
        """After we delete or add modules we need to reload all the modules to the file
        for quicker search. This module is then loaded to the memory.

        Argument:
            :param credentials      (list) Basic authorization credentials - username and password
            :return 'work' string if everything went through fine otherwise send back the reason why
                it failed.
        """
        path = '{}/load-cache'.format(self._yangcatalog_api_prefix)
        response = requests.post(path, auth=(credentials[0], credentials[1]), headers=json_headers)
        code = response.status_code

        if code != 200 and code != 201 and code != 204:
            self.LOGGER.error('Could not load json to memory-cache. Error: {} {}'.format(response.text, code))
        return response

    def process_module_deletion(self, arguments: t.List[str]) -> t.Tuple[StatusMessage, str]:
        """Deleting one or more modules. It deletes modules of given path from Redis.
        This will delete whole module in modules branch of the yang-catalog:yang module.
        It will also call indexing script to update searching.

        Argument:
            :param arguments    (list) list of arguments sent from API sender
            :return (__response_type) one of the response types which
                is either 'Finished successfully' or 'Partially done'
        """
        try:
            path_to_delete = arguments[3]
            modules = json.loads(path_to_delete)['modules']
            all_modules_raw = self.redisConnection.get_all_modules()
            all_modules = json.loads(all_modules_raw)
        except Exception:
            self.LOGGER.exception('Problem while processing arguments')
            return StatusMessage.FAIL, 'Server error -> Unable to parse arguments'

        def module_in(name: str, revision: str, modules: list) -> bool:
            for module in modules:
                if module['name'] == name and module.get('revision') == revision:
                    return True
            return False

        @functools.lru_cache(maxsize=None)
        def can_delete(name: str, revision: str) -> bool:
            """Check whether module with given 'name' and 'revison' which should be removed
            is or is not depedency/submodule of some other existing module.
            If module-to-be-deleted has reference in another existing module, it cannot be deleted.
            However, it can be deleted if also referenced existing module will be deleted too.
            """
            for redis_key, existing_module in all_modules.items():
                for dep_type in ['dependencies', 'submodule']:
                    is_dep = module_in(name, revision, existing_module.get(dep_type, []))
                    if is_dep:
                        if module_in(existing_module['name'], existing_module['revision'], modules):
                            if can_delete(existing_module['name'], existing_module['revision']):
                                continue
                        else:
                            self.LOGGER.error(
                                '{}@{} module has reference in another module\'s {}: {}'.format(
                                    name,
                                    revision,
                                    dep_type,
                                    redis_key,
                                ),
                            )
                            return False
            return True

        modules_not_deleted = []
        modules_to_delete = []
        mod_keys_to_delete = []
        redis_keys_to_delete = []
        for module in modules:
            mod_key = '{},{},{}'.format(module['name'], module['revision'], module['organization'])
            redis_key = '{}@{}/{}'.format(module['name'], module['revision'], module['organization'])
            if can_delete(module.get('name'), module.get('revision')):
                mod_keys_to_delete.append(mod_key)
                redis_keys_to_delete.append(redis_key)
                modules_to_delete.append(module)
            else:
                modules_not_deleted.append(mod_key)

        for mod in modules_to_delete:
            for redis_key, existing_module in all_modules.items():
                if existing_module.get('dependents') is not None:
                    dependents = existing_module['dependents']
                    dependents_dict = ['{}@{}'.format(m['name'], m.get('revision', '')) for m in dependents]
                    searched_dependent = '{}@{}'.format(mod['name'], mod.get('revision', ''))
                    if searched_dependent in dependents_dict:
                        self.redisConnection.delete_dependent(redis_key, mod['name'])
        modules_to_index = []
        for mod_key, redis_key in zip(mod_keys_to_delete, redis_keys_to_delete):
            response = self.redisConnection.delete_modules([redis_key])
            if response == 1:
                self.LOGGER.info('Module {} deleted successfully'.format(redis_key))
            elif response == 0:
                self.LOGGER.debug('Module {} already deleted'.format(redis_key))
            modules_to_index.append(redis_key)

        if self._notify_indexing:
            body_to_send = prepare_for_es_removal(
                self._yangcatalog_api_prefix,
                modules_to_index,
                self._save_file_dir,
                self.LOGGER,
            )

            if len(body_to_send) > 0:
                send_for_es_indexing(body_to_send, self.LOGGER, self.indexing_paths)
        if len(modules_not_deleted) == 0:
            return StatusMessage.SUCCESS, ''
        else:
            reason = 'modules-not-deleted:{}'.format(':'.join(modules_not_deleted))
            return StatusMessage.IN_PROGRESS, reason

    def run_ietf(self) -> t.Tuple[StatusMessage, str]:
        """
        Runs ietf and openconfig scripts that should update all the new ietf
        and openconfig modules
        :return: response success or failed
        """
        try:
            # Run pull_local.py script
            script_name = 'pull_local'
            module = __import__('ietfYangDraftPull', fromlist=[script_name])
            submodule = getattr(module, script_name)
            script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()

            self.LOGGER.info('Runnning pull_local.py script')
            try:
                submodule.main(script_conf=script_conf)
            except Exception:
                self.LOGGER.exception('Problem while running pull_local script')
                return StatusMessage.FAIL, 'Server error while running pull_local script'
            # Run openconfigPullLocal.py script
            script_name = 'openconfigPullLocal'
            module = __import__('ietfYangDraftPull', fromlist=[script_name])
            submodule = getattr(module, script_name)
            script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()

            self.LOGGER.info('Runnning openconfigPullLocal.py script')
            try:
                submodule.main(script_conf=script_conf)
            except Exception:
                self.LOGGER.exception('Problem while running openconfigPullLocal script')
                return StatusMessage.FAIL, 'Server error while running openconfigPullLocal script'

            return StatusMessage.SUCCESS, ''
        except Exception:
            self.LOGGER.exception('Server error while running scripts')
            return StatusMessage.FAIL, ''

    def load_config(self) -> StatusMessage:
        config = create_config(self._config_path)
        self._log_directory = config.get('Directory-Section', 'logs')
        self.LOGGER = log.get_logger('receiver', os.path.join(self._log_directory, 'receiver.log'))
        self.LOGGER.info('Loading config')
        logging.getLogger('pika').setLevel(logging.INFO)
        self._notify_indexing = config.get('General-Section', 'notify-index')
        self._save_file_dir = config.get('Directory-Section', 'save-file-dir')
        self._yang_models = config.get('Directory-Section', 'yang-models-dir')
        self._is_uwsgi = config.get('General-Section', 'uwsgi')
        self._rabbitmq_host = config.get('RabbitMQ-Section', 'host', fallback='127.0.0.1')
        self._rabbitmq_port = int(config.get('RabbitMQ-Section', 'port', fallback='5672'))
        self._changes_cache_path = config.get('Directory-Section', 'changes-cache')
        self._delete_cache_path = config.get('Directory-Section', 'delete-cache')
        self._failed_changes_cache_path = config.get('Directory-Section', 'changes-cache-failed')
        self._lock_file = config.get('Directory-Section', 'lock')
        rabbitmq_username = config.get('RabbitMQ-Section', 'username', fallback='guest')
        rabbitmq_password = config.get('Secrets-Section', 'rabbitmq-password', fallback='guest')
        self.temp_dir = config.get('Directory-Section', 'temp')
        self.json_ytree = config.get('Directory-Section', 'json-ytree')
        self._yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

        self.indexing_paths = ESIndexingPaths(
            cache_path=self._changes_cache_path,
            deletes_path=self._delete_cache_path,
            failed_path=self._failed_changes_cache_path,
            lock_path=self._lock_file,
        )

        self._notify_indexing = self._notify_indexing == 'True'
        self._rabbitmq_credentials = pika.PlainCredentials(username=rabbitmq_username, password=rabbitmq_password)
        self.LOGGER.info('Config loaded succesfully')
        return StatusMessage.SUCCESS

    def on_request(self, channel, method, properties, body):
        process_reload_cache = multiprocessing.Process(target=self.on_request_thread_safe, args=(properties, body))
        process_reload_cache.start()

    def on_request_thread_safe(self, properties, body_raw: bytes):
        """Function called when something was sent from API sender. This function
        will process all the requests that would take too long to process for API.
        When the processing is done we will sent back the result of the request
        which can be either 'Failed' or 'Finished successfully' with corespondent
        correlation ID. If the request 'Failed' it will sent back also a reason why
        it failed.

        Arguments:
            :param body: (str) String of arguments that need to be processed
                separated by '#'.
        """
        config_reloaded = False
        status: StatusMessage
        details: str = ''

        try:
            body = body_raw.decode()
            arguments = body.split('#')
            if body == 'run_ietf':
                self.LOGGER.info('Running all ietf and openconfig modules')
                status, details = self.run_ietf()
            elif body == 'reload_config':
                status = self.load_config()
                config_reloaded = True
            elif 'run_ping' == arguments[0]:
                status = self.run_ping(arguments[1])
            elif 'run_script' == arguments[0]:
                status = self.run_script(arguments[1:])
            elif 'github' == arguments[-1]:
                self.LOGGER.info('Github automated message starting to populate')
                paths_plus = arguments[arguments.index('repoLocalDir') :]
                self.LOGGER.info('paths plus {}'.format(paths_plus))
                arguments = arguments[: arguments.index('repoLocalDir')]
                self.LOGGER.info('arguments {}'.format(arguments))
                paths = paths_plus[1:-2]
                self.LOGGER.info('paths {}'.format(paths))
                try:
                    for path in paths:
                        with open(self.temp_dir + '/log_trigger.txt', 'w') as f:
                            local_dir = paths_plus[-2]
                            arguments = arguments + ['--dir', local_dir + '/' + path]
                            if self._notify_indexing:
                                arguments.append('--notify-indexing')
                            subprocess.check_call(arguments, stderr=f)
                    status = StatusMessage.SUCCESS
                except subprocess.CalledProcessError as e:
                    status = StatusMessage.FAIL
                    mf = message_factory.MessageFactory()
                    mf.send_automated_procedure_failed(arguments, self.temp_dir + '/log_no_sdo_api.txt')
                    self.LOGGER.error(
                        'check log_trigger.txt Error calling process populate.py because {}\n\n with error {}'.format(
                            e.output,
                            e.stderr,
                        ),
                    )
                except Exception:
                    status = StatusMessage.FAIL
                    self.LOGGER.error(
                        f'check log_trigger.txt failed to process github message with error {sys.exc_info()[0]}',
                    )
            else:
                if arguments[0] == 'DELETE-VENDORS':
                    status = self.process_vendor_deletion(arguments)
                    credentials = arguments[1:3]
                elif arguments[0] == 'DELETE-MODULES':
                    status, details = self.process_module_deletion(arguments)
                    credentials = arguments[1:3]
                elif arguments[0] in ('POPULATE-MODULES', 'POPULATE-VENDORS'):
                    status, details = self.process(arguments)
                    i = arguments.index('--credentials')
                    credentials = arguments[i + 1 : i + 3]
                    i = arguments.index('--dir')
                    directory = arguments[i + 1]
                    shutil.rmtree(directory)
                else:
                    assert False, 'Invalid request type'

                if status == StatusMessage.SUCCESS:
                    response = self.make_cache(credentials)
                    code = response.status_code
                    if code != 200 and code != 201 and code != 204:
                        status = StatusMessage.FAIL
                        details = 'Server error-> could not reload cache'
        except Exception:
            status = StatusMessage.FAIL
            self.LOGGER.exception('receiver.py failed')
        final_response = status.value if not details else '{}#split#{}'.format(status.value, details)
        self.LOGGER.info(
            'Receiver is done with id - {} and message = {}'.format(properties.correlation_id, final_response),
        )

        f = open('{}/correlation_ids'.format(self.temp_dir), 'r')
        lines = f.readlines()
        f.close()
        with open('{}/correlation_ids'.format(self.temp_dir), 'w') as f:
            for line in lines:
                if properties.correlation_id in line:
                    new_line = '{} -- {} - {}\n'.format(
                        datetime.now().ctime(),
                        properties.correlation_id,
                        str(final_response),
                    )
                    f.write(new_line)
                else:
                    f.write(line)
        if config_reloaded:
            assert self.channel, 'Should only be called from self.channel.start_consuming()'
            self.channel.stop_consuming()

    def start_receiving(self):
        while True:
            try:
                self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=self._rabbitmq_host,
                        port=self._rabbitmq_port,
                        heartbeat=10,
                        credentials=self._rabbitmq_credentials,
                    ),
                )
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue='module_queue')

                self.channel.basic_qos(prefetch_count=1)
                self.channel.basic_consume('module_queue', self.on_request, auto_ack=True)

                self.LOGGER.info('Awaiting RPC request')

                self.channel.start_consuming()
            except Exception as e:
                self.LOGGER.exception('Exception: {}'.format(str(e)))
            else:
                self.LOGGER.info('Restarting connection after config reload')
            finally:
                time.sleep(10)
                try:
                    if self.channel:
                        self.channel.stop_consuming()
                except Exception:
                    pass
                try:
                    if self.connection:
                        self.connection.close()
                except Exception:
                    pass

    def run_script(self, arguments: t.List[str]) -> StatusMessage:
        module_name = arguments[0]
        script_name = arguments[1]
        body_input = json.loads(arguments[2])
        try:
            # Load submodule and its config
            module = __import__(module_name, fromlist=[script_name])
            submodule = getattr(module, script_name)
            script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()
            script_args_list = script_conf.get_args_list()

            for key in body_input:
                if key != 'credentials' and body_input[key] != script_args_list[key]['default']:
                    script_conf.args.__setattr__(key, body_input[key])

            clean = script_conf.args.__dict__.copy()
            try:
                username, _ = clean.pop('credentials')
                clean['username'] = username
            except KeyError:
                pass
            self.LOGGER.info(
                f'Runnning {script_name}.py script with following configuration:\n{clean}',
            )
            submodule.main(script_conf=script_conf)
            return StatusMessage.SUCCESS
        except Exception:
            self.LOGGER.exception('Server error while running {} script'.format(script_name))
            return StatusMessage.FAIL

    def run_ping(self, message: str) -> StatusMessage:
        if message == 'ping':
            return StatusMessage.SUCCESS
        return StatusMessage.FAIL


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--config-path',
        type=str,
        default=os.environ['YANGCATALOG_CONFIG_PATH'],
        help='Set path to config file',
    )
    args, extra_args = parser.parse_known_args()
    config_path = args.config_path
    receiver = Receiver(config_path)
    receiver.start_receiving()
