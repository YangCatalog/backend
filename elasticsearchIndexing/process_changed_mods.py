# Copyright The IETF Trust 2021, All Rights Reserved
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

__author__ = 'Miroslav Kovac, Joe Clarke'
__copyright__ = 'Copyright 2018 Cisco and its affiliates'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech, jclarke@cisco.com'

import json
import logging
import os
import shutil
import sys

from elasticsearchIndexing.build_yindex import build_indices
from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.index_build import BuildYINDEXModule
from utility import log
from utility.create_config import create_config
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.util import validate_revision

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME]['args'],
    arglist=None if __name__ == '__main__' else [],
)


class ProcessChangedMods:
    def __init__(self, script_config: ScriptConfig):
        self.args = script_config.args
        self.config = create_config(self.args.config_path)
        self.log_directory = self.config.get('Directory-Section', 'logs')
        self.yang_models = self.config.get('Directory-Section', 'yang-models-dir')
        self.changes_cache_path = self.config.get('Directory-Section', 'changes-cache')
        self.failed_changes_cache_path = self.config.get('Directory-Section', 'changes-cache-failed')
        self.delete_cache_path = self.config.get('Directory-Section', 'delete-cache')
        self.lock_file = self.config.get('Directory-Section', 'lock')
        self.lock_file_cron = self.config.get('Directory-Section', 'lock-cron')
        self.json_ytree = self.config.get('Directory-Section', 'json-ytree')
        self.save_file_dir = self.config.get('Directory-Section', 'save-file-dir')

        self.logger = log.get_logger(
            'process_changed_mods',
            os.path.join(self.log_directory, 'process_changed_mods.log'),
        )

    def start_processing_changed_mods(self):
        self.logger.info('Starting process_changed_mods.py script')

        if os.path.exists(self.lock_file) or os.path.exists(self.lock_file_cron):
            # we can exist since this is run by cronjob every 3 minutes of every day
            self.logger.warning('Temporary lock file used by something else. Exiting script !!!')
            sys.exit()
        self._create_lock_files()

        self.changes_cache = self._load_changes_cache(self.changes_cache_path)
        self.delete_cache = self._load_delete_cache(self.delete_cache_path)

        if not self.changes_cache and not self.delete_cache:
            self.logger.info('No new modules are added or removed. Exiting script!!!')
            os.unlink(self.lock_file)
            os.unlink(self.lock_file_cron)
            sys.exit()

        self._initialize_es_manager()

        self.logger.info('Running cache files backup')
        self._backup_cache_files(self.delete_cache_path)
        self._backup_cache_files(self.changes_cache_path)
        os.unlink(self.lock_file)

        if self.delete_cache:
            self._delete_modules_from_es()
        if self.changes_cache:
            self._change_modules_in_es()

        os.unlink(self.lock_file_cron)
        self.logger.info('Job finished successfully')

    def _create_lock_files(self):
        try:
            open(self.lock_file, 'w').close()
            open(self.lock_file_cron, 'w').close()
        except Exception:
            os.unlink(self.lock_file)
            os.unlink(self.lock_file_cron)
            self.logger.error('Temporary lock file could not be created although it is not locked')
            sys.exit()

    def _initialize_es_manager(self):
        self.es_manager = ESManager()
        logging.getLogger('elasticsearch').setLevel(logging.ERROR)

    def _delete_modules_from_es(self):
        for module in self.delete_cache:
            name, rev_org = module.split('@')
            revision, organization = rev_org.split('/')
            revision = validate_revision(revision)
            self.logger.info(f'Deleting {module} from es indices')
            module = {
                'name': name,
                'revision': revision,
                'organization': organization,
            }
            self.es_manager.delete_from_indices(module)

    def _change_modules_in_es(self):
        recursion_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(50000)
        try:
            for module_count, (module_key, module_path) in enumerate(self.changes_cache.items(), 1):
                name, rev_org = module_key.split('@')
                revision, organization = rev_org.split('/')
                revision = validate_revision(revision)
                name_revision = f'{name}@{revision}'

                module = BuildYINDEXModule(name=name, revision=revision, organization=organization, path=module_path)
                self.logger.info(
                    f'yindex on module {name_revision}. module {module_count} out of {len(self.changes_cache)}',
                )

                try:
                    build_indices(self.es_manager, module, self.save_file_dir, self.json_ytree, self.logger)
                except Exception:
                    self.logger.exception(f'Problem while processing module {module_key}')
                    try:
                        with open(self.failed_changes_cache_path, 'r') as reader:
                            failed_modules = json.load(reader)
                    except (FileNotFoundError, json.decoder.JSONDecodeError):
                        failed_modules = {}
                    if module_key not in failed_modules:
                        failed_modules[module_key] = module_path
                    with open(self.failed_changes_cache_path, 'w') as writer:
                        json.dump(failed_modules, writer)
        except Exception:
            sys.setrecursionlimit(recursion_limit)
            os.unlink(self.lock_file_cron)
            self.logger.exception('Error while running build_yindex.py script')
            self.logger.info('Job failed execution')
            sys.exit()

        sys.setrecursionlimit(recursion_limit)

    def _load_changes_cache(self, changes_cache_path: str):
        changes_cache = {}

        try:
            with open(changes_cache_path, 'r') as reader:
                changes_cache = json.load(reader)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            with open(changes_cache_path, 'w') as writer:
                json.dump({}, writer)

        return changes_cache

    def _load_delete_cache(self, delete_cache_path: str):
        delete_cache = []

        try:
            with open(delete_cache_path, 'r') as reader:
                delete_cache = json.load(reader)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            with open(delete_cache_path, 'w') as writer:
                json.dump([], writer)

        return delete_cache

    def _backup_cache_files(self, cache_path: str):
        shutil.copyfile(cache_path, f'{cache_path}.bak')
        empty = {}
        if 'deletes' in cache_path:
            empty = []
        with open(cache_path, 'w') as writer:
            json.dump(empty, writer)


def main(script_config: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()):
    ProcessChangedMods(script_config).start_processing_changed_mods()


if __name__ == '__main__':
    main()
