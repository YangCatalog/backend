# Copyright The IETF Trust 2023, All Rights Reserved
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

__author__ = 'Bohdan Konovalenko'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bohdan.konovalenko@pantheon.tech'

import functools
import json
import logging
import os
import shutil
import typing as t

import requests
from celery import Celery

from jobs.status_messages import StatusMessage
from redisConnections.redisConnection import RedisConnection, key_quote
from utility import log
from utility.create_config import create_config
from utility.elasticsearch_util import ESIndexingPaths, prepare_for_es_removal, send_for_es_indexing
from utility.staticVariables import json_headers


class BackendCeleryApp(Celery):
    logger: logging.Logger
    redis_connection: RedisConnection
    notify_indexing: bool
    save_file_dir: str
    yangcatalog_api_prefix: str
    indexing_paths: ESIndexingPaths
    confd_credentials: list[str, str]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_config()

    def load_config(self):
        config = create_config()
        log_directory = config.get('Directory-Section', 'logs')
        self.logger = log.get_logger('job_runner', os.path.join(log_directory, 'job_runner.log'))
        self.redis_connection = RedisConnection(config=config)
        self.notify_indexing = config.get('General-Section', 'notify-index') == 'True'
        self.save_file_dir = config.get('Directory-Section', 'save-file-dir')
        changes_cache_path = config.get('Directory-Section', 'changes-cache')
        delete_cache_path = config.get('Directory-Section', 'delete-cache')
        failed_changes_cache_path = config.get('Directory-Section', 'changes-cache-failed')
        lock_file = config.get('Directory-Section', 'lock')
        self.yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')
        self.indexing_paths = ESIndexingPaths(
            cache_path=changes_cache_path,
            deletes_path=delete_cache_path,
            failed_path=failed_changes_cache_path,
            lock_path=lock_file,
        )
        self.confd_credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split()
        self.logger.info('Config loaded succesfully')

    def reload_cache(self):
        requests.post(f'{self.yangcatalog_api_prefix}/load-cache', auth=self.confd_credentials, headers=json_headers)


celery_app = BackendCeleryApp('backend_celery_app')

celery_app.config_from_object('jobs.celery_configuration')

# celery_app.autodiscover_tasks()  # for celery versions higher than 5.0.1


@celery_app.task
def test_task(s: str, n: int):
    celery_app.logger.info(f'Test task called with such args: {s}, {n}')
    return StatusMessage.SUCCESS


@celery_app.task
def process(dir: str, sdo: bool, api: bool):
    """
    Process modules. Calls populate.py script which will parse the modules
    on the given path given by "dir" param. The directory is removed after
    completion.
    """
    try:
        return run_script(
            'parseAndPopulate',
            'populate',
            {
                'sdo': sdo,
                'api': api,
                'dir': dir,
                'notify_indexing': celery_app.notify_indexing,
                'force_indexing': celery_app.notify_indexing,
            },
        )
    finally:
        shutil.rmtree(dir)
        celery_app.reload_cache()


@celery_app.task
def process_vendor_deletion(params: dict[str, str]):
    """
    Deleting vendors metadata. Deletes all the modules in the vendor branch of the yang-catalog.yang
    module on given path. If the module was added by a vendor and it doesn't contain any other implementations
    it will delete the whole module in the modules branch of the yang-catalog.yang module.
    It will also call the indexing script to update Elasticsearch searching.
    """
    data_key = ''
    redis_vendor_key = ''
    param_names = ['vendor', 'platform', 'software-version', 'software-flavor']
    for param_name in param_names:
        if param := params.get(param_name):
            data_key = f'yang-catalog:{param_name}'
            redis_vendor_key += f'/{key_quote(param)}'
    redis_vendor_key = redis_vendor_key.removeprefix('/')

    redis_vendor_data = celery_app.redis_connection.create_vendors_data_dict(redis_vendor_key)
    vendor_data = {data_key: redis_vendor_data}

    modules_keys = set()
    deleted_modules = []
    iterate_in_depth(vendor_data, modules_keys)

    # Delete implementation
    for mod_key in modules_keys:
        try:
            name, revision, organization = mod_key.split(',')
            redis_key = f'{name}@{revision}/{organization}'
            raw_data = celery_app.redis_connection.get_module(redis_key)
            modules_data = json.loads(raw_data)
            implementations = modules_data.get('implementations', {}).get('implementation', [])

            count_of_implementations = len(implementations)
            count_deleted = 0
            for implementation in implementations:
                imp_key = ''
                for param_name in param_names:
                    if not (param := params.get(param_name)) or param == implementation[param_name]:
                        imp_key += f',{implementation[param_name]}'
                imp_key = imp_key.removeprefix(',')

                # Delete module implementation from Redis
                if response := celery_app.redis_connection.delete_implementation(redis_key, imp_key):
                    celery_app.logger.info(f'Implementation {imp_key} deleted from module {mod_key} successfully')
                elif response == 0:
                    celery_app.logger.debug(f'Implementation {imp_key} already deleted from module {mod_key}')
                count_deleted += 1

            if count_deleted == count_of_implementations and count_of_implementations != 0:
                if organization == params['vendor']:
                    deletion_problem = False

                    # Delete module from Redis
                    match celery_app.redis_connection.delete_modules([redis_key]):
                        case 1:
                            celery_app.logger.info(f'Module {redis_key} deleted successfully')
                        case 0:
                            celery_app.logger.debug(f'Module {redis_key} already deleted')
                    if not deletion_problem:
                        deleted_modules.append(redis_key)
        except Exception:
            celery_app.logger.exception(f'YANG file {mod_key} doesn\'t exist although it should exist')
    raw_all_modules = celery_app.redis_connection.get_all_modules()
    all_modules = json.loads(raw_all_modules)

    # Delete dependets
    for module_key in modules_keys:
        name, revision, organization = module_key.split(',')
        for existing_module in all_modules.values():
            if existing_module.get('dependents') is not None:
                dependents = existing_module['dependents']
                for dependent in dependents:
                    if dependent['name'] == name and dependent.get('revision') == revision:
                        mod_key_redis = (
                            f'{existing_module["name"]}@{existing_module["revision"]}/'
                            f'{existing_module["organization"]}'
                        )
                        # Delete module's dependent from Redis
                        celery_app.redis_connection.delete_dependent(mod_key_redis, dependent['name'])

    # Delete vendor branch from Redis
    celery_app.redis_connection.delete_vendor(redis_vendor_key)

    if celery_app.notify_indexing:
        body_to_send = prepare_for_es_removal(
            celery_app.yangcatalog_api_prefix,
            deleted_modules,
            celery_app.save_file_dir,
            celery_app.logger,
        )
        if body_to_send.get('modules-to-delete'):
            send_for_es_indexing(body_to_send, celery_app.logger, celery_app.indexing_paths)
    celery_app.reload_cache()
    return StatusMessage.SUCCESS


def iterate_in_depth(value: dict, modules_keys: set[str]):
    """
    Iterates through the branch to get to the level with modules.

    Arguments:
        :param value            (dict) data through which we will need to iterate
        :param modules_keys     (set) set that will contain all the modules that need to be deleted
    """
    for key, val in value.items():
        if key == 'protocols':
            continue
        if isinstance(val, list):
            for v in val:
                iterate_in_depth(v, modules_keys)
        if isinstance(val, dict):
            if key == 'modules':
                for mod in val['module']:
                    mod_key = f'{mod["name"]},{mod["revision"]},{mod["organization"]}'
                    modules_keys.add(mod_key)
            else:
                iterate_in_depth(val, modules_keys)


@celery_app.task
def process_module_deletion(modules: list[dict[str, str]]):
    """
    Delete modules. It deletes modules of given path from Redis.
    This will delete whole module in modules branch of the yang-catalog:yang module.
    It will also call the indexing script to update ES.
    """
    try:
        all_modules_raw = celery_app.redis_connection.get_all_modules()
        all_modules = json.loads(all_modules_raw)
    except Exception:
        celery_app.logger.exception('Problem while processing arguments')
        return StatusMessage.FAIL

    def module_in(name: str, revision: str, modules: list) -> bool:
        for module in modules:
            if module['name'] == name and module.get('revision') == revision:
                return True
        return False

    @functools.lru_cache(maxsize=None)
    def can_delete(name: str, revision: str) -> bool:
        """
        Check whether module with given 'name' and 'revison' which should be removed
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
                        celery_app.logger.error(
                            f'{name}@{revision} module has reference in another module\'s {dep_type}: {redis_key}',
                        )
                        return False
        return True

    modules_not_deleted = []
    modules_to_delete = []
    mod_keys_to_delete = []
    redis_keys_to_delete = []
    for module in modules:
        mod_key = f'{module["name"]},{module["revision"]},{module["organization"]}'
        redis_key = f'{module["name"]}@{module["revision"]}/{module["organization"]}'
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
                dependents_dict = [f'{m["name"]}@{m.get("revision", "")}' for m in dependents]
                searched_dependent = f'{mod["name"]}@{mod.get("revision", "")}'
                if searched_dependent in dependents_dict:
                    celery_app.redis_connection.delete_dependent(redis_key, mod['name'])
    modules_to_index = []
    for mod_key, redis_key in zip(mod_keys_to_delete, redis_keys_to_delete):
        response = celery_app.redis_connection.delete_modules([redis_key])
        if response == 1:
            celery_app.logger.info(f'Module {redis_key} deleted successfully')
        elif response == 0:
            celery_app.logger.debug(f'Module {redis_key} already deleted')
        modules_to_index.append(redis_key)

    if celery_app.notify_indexing:
        body_to_send = prepare_for_es_removal(
            celery_app.yangcatalog_api_prefix,
            modules_to_index,
            celery_app.save_file_dir,
            celery_app.logger,
        )

        if len(body_to_send) > 0:
            send_for_es_indexing(body_to_send, celery_app.logger, celery_app.indexing_paths)
    celery_app.reload_cache()
    if len(modules_not_deleted) == 0:
        return StatusMessage.SUCCESS
    return StatusMessage.FAIL, f'modules-not-deleted:{":".join(modules_not_deleted)}'


@celery_app.task
def run_script(module_name: str, script_name: str, arguments: t.Optional[dict] = None):
    arguments = arguments if isinstance(arguments, dict) else {}
    try:
        module = __import__(module_name, fromlist=[script_name])
        submodule = getattr(module, script_name)
        script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()

        script_conf.set_args(**arguments)

        clean = script_conf.args.__dict__.copy()
        try:
            username, _ = clean.pop('credentials')
            clean['username'] = username
        except KeyError:
            pass
        celery_app.logger.info(f'Runnning {script_name}.py script with following configuration:\n{clean}')
        submodule.main(script_conf=script_conf)
        return StatusMessage.SUCCESS
    except Exception:
        celery_app.logger.exception(f'Server error while running {script_name} script')
        return StatusMessage.FAIL


@celery_app.task
def github_populate(paths: list[str]):
    for path in paths:
        run_script(
            'parseAndPopulate',
            'populate',
            {'dir': path, 'notify-indexing': celery_app.notify_indexing},
        )
