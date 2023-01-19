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
This script calls parse_directory.py script with option based on whether we are populating SDOs or vendors
and also whether this script was called via API or directly by yangcatalog admin user.
Once the metadata is parsed and json files are created it will populate the ConfD with all the parsed metadata,
reload API and start to parse metadata that needs to use complicated algorithms.
For this we use class ModulesComplicatedAlgorithms.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import json
import multiprocessing
import os
import shutil
import sys
import time
import typing as t
import uuid
from argparse import Namespace
from configparser import ConfigParser

import requests

import utility.log as log
from parseAndPopulate import parse_directory
from parseAndPopulate.file_hasher import FileHasher
from parseAndPopulate.modulesComplicatedAlgorithms import ModulesComplicatedAlgorithms
from redisConnections.redisConnection import RedisConnection
from utility.confdService import ConfdService
from utility.create_config import create_config
from utility.message_factory import MessageFactory
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.staticVariables import json_headers
from utility.util import prepare_for_es_indexing, send_for_es_indexing

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME]['args'],
    arglist=None if __name__ == '__main__' else [],
)


class Populate:
    def __init__(
        self,
        args: Namespace,
        config: ConfigParser = create_config(),
        redis_connection: RedisConnection = RedisConnection(),
        confd_service: ConfdService = ConfdService(),
        message_factory: t.Optional[MessageFactory] = None,
    ):
        self.start_time = None
        self.args = args
        self.config = config
        self.json_dir = ''
        self.errors = False

        self.log_directory = self.config.get('Directory-Section', 'logs')
        self.yang_models = self.config.get('Directory-Section', 'yang-models-dir')
        self.temp_dir = self.config.get('Directory-Section', 'temp')
        self.changes_cache_path = self.config.get('Directory-Section', 'changes-cache')
        self.cache_dir = self.config.get('Directory-Section', 'cache')
        self.delete_cache_path = self.config.get('Directory-Section', 'delete-cache')
        self.lock_file = self.config.get('Directory-Section', 'lock')
        self.failed_changes_cache_path = self.config.get('Directory-Section', 'changes-cache-failed')
        self.json_ytree = self.config.get('Directory-Section', 'json-ytree')
        self.yangcatalog_api_prefix = self.config.get('Web-Section', 'yangcatalog-api-prefix')

        self.redis_connection = redis_connection
        self.confd_service = confd_service
        self.message_factory = message_factory

        self.logger = log.get_logger('populate', os.path.join(self.log_directory, 'parseAndPopulate.log'))

    @property
    def message_factory(self):
        if not self._message_factory:
            self._message_factory = MessageFactory()
        return self._message_factory

    @message_factory.setter
    def message_factory(self, value: t.Optional[MessageFactory]):
        self._message_factory = value

    def start_populating(self):
        self.start_time = time.time()
        self.logger.info('Starting the populate script')
        if self.args.api:
            self._send_notification_about_running_script_by_api()
        self._initialize_json_dir()
        parsed, skipped = self._run_parse_directory_script()
        modules = self._populate_modules_in_db()
        if not (parsed or skipped):
            self.logger.error(
                'No files were parsed. This probably means the directory is missing capability xml files.',
            )
        elif skipped and not parsed:
            self.logger.info('No new modules were parsed.')
        self._prepare_and_send_modules_for_es_indexing()
        if modules:
            self.process_reload_cache = multiprocessing.Process(target=self._reload_cache_in_parallel)
            self.process_reload_cache.start()
            if self.args.simple:
                self.logger.info('Waiting for cache reload to finish')
                self.process_reload_cache.join()
            else:
                self._run_complicated_algorithms()
            self.logger.info(
                (
                    f'Populate took {int(time.time() - self.start_time)} seconds with the main and '
                    f'{"without" if self.args.simple else "with"} complicated algorithm'
                ),
            )
            # Keep new hashes only if the ConfD was patched successfully
            if not self.errors:
                self._update_files_hashes()
        try:
            uuid.UUID(self.json_dir)
            shutil.rmtree(self.json_dir)
        except ValueError:
            pass
        self.logger.info('Populate script finished successfully')

    def _send_notification_about_running_script_by_api(self):
        args_dict = dict(self.args.__dict__)
        # Hide password from credentials argument
        args_dict['credentials'] = args_dict['credentials'][0]
        self.message_factory.send_populate_script_triggered_by_api(args_dict.items())

    def _initialize_json_dir(self):
        if self.args.api:
            self.json_dir = self.args.dir
        else:
            self.json_dir = os.path.join(self.temp_dir, uuid.uuid4().hex)
            os.makedirs(self.json_dir, exist_ok=True)

    def _run_parse_directory_script(self) -> tuple[int, int]:
        self.logger.info('Calling parse_directory script')
        try:
            script_conf = parse_directory.DEFAULT_SCRIPT_CONFIG.copy()
            options = (
                ('json_dir', self.json_dir),
                ('result_html_dir', self.args.result_html_dir),
                ('dir', self.args.dir),
                ('save_file_dir', self.args.save_file_dir),
                ('api', self.args.api),
                ('sdo', self.args.sdo),
                ('save_file_hash', not self.args.force_parsing),
            )
            for attr, value in options:
                setattr(script_conf.args, attr, value)
            stats = parse_directory.main(script_conf=script_conf)
        except Exception as e:
            self.logger.exception(f'parse_directory error:\n{e}')
            raise e
        return stats

    def _populate_modules_in_db(self) -> list:
        self.logger.info('Populating yang catalog with data. Starting to add modules')
        with open(os.path.join(self.json_dir, 'prepare.json')) as data_file:
            data = data_file.read()
        modules = json.loads(data).get('module', [])
        self.errors = self.confd_service.patch_modules(modules)
        self.redis_connection.populate_modules(modules)
        if not self.args.sdo and os.path.exists(os.path.join(self.json_dir, 'normal.json')):
            self.logger.info('Starting to add vendors')
            with open(os.path.join(self.json_dir, 'normal.json')) as data:
                vendors = json.loads(data.read()).get('vendors', {}).get('vendor')
            if not vendors:
                return modules
            self.errors = self.errors or self.confd_service.patch_vendors(vendors)
            self.redis_connection.populate_implementation(vendors)
        return modules

    def _prepare_and_send_modules_for_es_indexing(self):
        body_to_send = {}
        if self.args.notify_indexing:
            body_to_send = prepare_for_es_indexing(
                self.yangcatalog_api_prefix,
                os.path.join(self.json_dir, 'prepare.json'),
                self.logger,
                self.args.save_file_dir,
                force_indexing=self.args.force_indexing,
            )
        if not body_to_send:
            return
        self.logger.info('Sending files for indexing')
        indexing_paths = {
            'cache_path': self.changes_cache_path,
            'deletes_path': self.delete_cache_path,
            'failed_path': self.failed_changes_cache_path,
            'lock_path': self.lock_file,
        }
        send_for_es_indexing(body_to_send, self.logger, indexing_paths)

    def _reload_cache_in_parallel(self):
        self.logger.info('Sending request to reload cache in different thread')
        url = f'{self.yangcatalog_api_prefix}/load-cache'
        response = requests.post(
            url,
            None,
            auth=(self.args.credentials[0], self.args.credentials[1]),
            headers=json_headers,
        )
        if response.status_code != 201:
            self.logger.warning(
                f'Could not send a load-cache request. Status code {response.status_code}. message {response.text}',
            )
        self.logger.info('Cache reloaded successfully')

    def _run_complicated_algorithms(self):
        self.logger.info('Running ModulesComplicatedAlgorithms from populate.py script')
        recursion_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(50000)
        complicated_algorithms = ModulesComplicatedAlgorithms(
            self.log_directory,
            self.yangcatalog_api_prefix,
            self.args.credentials,
            self.args.save_file_dir,
            self.json_dir,
            None,
            self.yang_models,
            self.temp_dir,
            self.json_ytree,
        )
        complicated_algorithms.parse_non_requests()
        self.logger.info('Waiting for cache reload to finish')
        self.process_reload_cache.join()
        complicated_algorithms.parse_requests()
        sys.setrecursionlimit(recursion_limit)
        self.logger.info('Populating with new data of complicated algorithms')
        complicated_algorithms.populate()

    def _update_files_hashes(self):
        path = os.path.join(self.json_dir, 'temp_hashes.json')
        file_hasher = FileHasher(
            'backend_files_modification_hashes',
            self.cache_dir,
            not self.args.force_parsing,
            self.log_directory,
        )
        updated_hashes = file_hasher.load_hashed_files_list(path)
        if updated_hashes:
            file_hasher.merge_and_dump_hashed_files_list(updated_hashes)


def main(
    script_conf: t.Optional[ScriptConfig] = None,
    config: ConfigParser = create_config(),
    message_factory: t.Optional[MessageFactory] = None,
):
    script_conf = script_conf or DEFAULT_SCRIPT_CONFIG.copy()
    Populate(script_conf.args, config, message_factory=message_factory).start_populating()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        exit(1)
