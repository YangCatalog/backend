import functools
import json
import os
import shutil

from api.status_message import StatusMessage
from redisConnections.redisConnection import RedisConnection, key_quote
from utility import log
from utility.create_config import create_config
from utility.elasticsearch_util import ESIndexingPaths, prepare_for_es_removal, send_for_es_indexing


class JobRunner:
    def __init__(self):
        self.load_config()
        self.redis_connection = RedisConnection()

    def load_config(self):
        config = create_config()
        log_directory = config.get('Directory-Section', 'logs')
        self.logger = log.get_logger('job_runner', os.path.join(log_directory, 'job_runner.log'))
        self._notify_indexing = config.get('General-Section', 'notify-index') == 'True'
        self._save_file_dir = config.get('Directory-Section', 'save-file-dir')
        changes_cache_path = config.get('Directory-Section', 'changes-cache')
        delete_cache_path = config.get('Directory-Section', 'delete-cache')
        failed_changes_cache_path = config.get('Directory-Section', 'changes-cache-failed')
        lock_file = config.get('Directory-Section', 'lock')
        self._yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

        self.indexing_paths = ESIndexingPaths(
            cache_path=changes_cache_path,
            deletes_path=delete_cache_path,
            failed_path=failed_changes_cache_path,
            lock_path=lock_file,
        )

        self.logger.info('Config loaded succesfully')

    def process(self, dir: str, sdo: bool, api: bool) -> StatusMessage:
        """
        Process modules. Calls populate.py script which will parse the modules
        on the given path given by "dir" param. The directory is removed after
        completion.
        """
        try:
            return self.run_script(
                'parseAndPopulate',
                'populate',
                {
                    'sdo': sdo,
                    'api': api,
                    'dir': dir,
                    'notify_indexing': self._notify_indexing,
                    'force_indexing': self._notify_indexing,
                },
            )
        finally:
            shutil.rmtree(dir)

    def process_vendor_deletion(self, params: dict[str, str]) -> StatusMessage:
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

        redis_vendor_data = self.redis_connection.create_vendors_data_dict(redis_vendor_key)
        vendor_data = {data_key: redis_vendor_data}

        modules_keys = set()
        deleted_modules = []
        self.iterate_in_depth(vendor_data, modules_keys)

        # Delete implementation
        for mod_key in modules_keys:
            try:
                name, revision, organization = mod_key.split(',')
                redis_key = '{}@{}/{}'.format(name, revision, organization)
                raw_data = self.redis_connection.get_module(redis_key)
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
                    response = self.redis_connection.delete_implementation(redis_key, imp_key)
                    if response := self.redis_connection.delete_implementation(redis_key, imp_key):
                        self.logger.info(
                            'Implementation {} deleted from module {} successfully'.format(imp_key, mod_key),
                        )
                    elif response == 0:
                        self.logger.debug('Implementation {} already deleted from module {}'.format(imp_key, mod_key))
                    count_deleted += 1

                if count_deleted == count_of_implementations and count_of_implementations != 0:
                    if organization == params['vendor']:
                        deletion_problem = False

                        # Delete module from Redis
                        match self.redis_connection.delete_modules([redis_key]):
                            case 1:
                                self.logger.info('Module {} deleted successfully'.format(redis_key))
                            case 0:
                                self.logger.debug('Module {} already deleted'.format(redis_key))
                        if not deletion_problem:
                            deleted_modules.append(redis_key)
            except Exception:
                self.logger.exception('YANG file {} doesn\'t exist although it should exist'.format(mod_key))
        raw_all_modules = self.redis_connection.get_all_modules()
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
                            self.redis_connection.delete_dependent(mod_key_redis, dependent['name'])

        # Delete vendor branch from Redis
        response = self.redis_connection.delete_vendor(redis_vendor_key)

        if self._notify_indexing:
            body_to_send = prepare_for_es_removal(
                self._yangcatalog_api_prefix,
                deleted_modules,
                self._save_file_dir,
                self.logger,
            )
            if body_to_send.get('modules-to-delete'):
                send_for_es_indexing(body_to_send, self.logger, self.indexing_paths)
        return StatusMessage.SUCCESS

    def iterate_in_depth(self, value: dict, modules_keys: set[str]):
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
                    self.iterate_in_depth(v, modules_keys)
            if isinstance(val, dict):
                if key == 'modules':
                    for mod in val['module']:
                        mod_key = '{},{},{}'.format(mod['name'], mod['revision'], mod['organization'])
                        modules_keys.add(mod_key)
                else:
                    self.iterate_in_depth(val, modules_keys)

    def process_module_deletion(self, modules: list[dict[str, str]]) -> StatusMessage:
        """
        Delete modules. It deletes modules of given path from Redis.
        This will delete whole module in modules branch of the yang-catalog:yang module.
        It will also call the indexing script to update ES.
        """
        try:
            all_modules_raw = self.redis_connection.get_all_modules()
            all_modules = json.loads(all_modules_raw)
        except Exception:
            self.logger.exception('Problem while processing arguments')
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
                            self.logger.error(
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
                        self.redis_connection.delete_dependent(redis_key, mod['name'])
        modules_to_index = []
        for mod_key, redis_key in zip(mod_keys_to_delete, redis_keys_to_delete):
            response = self.redis_connection.delete_modules([redis_key])
            if response == 1:
                self.logger.info('Module {} deleted successfully'.format(redis_key))
            elif response == 0:
                self.logger.debug('Module {} already deleted'.format(redis_key))
            modules_to_index.append(redis_key)

        if self._notify_indexing:
            body_to_send = prepare_for_es_removal(
                self._yangcatalog_api_prefix,
                modules_to_index,
                self._save_file_dir,
                self.logger,
            )

            if len(body_to_send) > 0:
                send_for_es_indexing(body_to_send, self.logger, self.indexing_paths)
        if len(modules_not_deleted) == 0:
            return StatusMessage.SUCCESS
        else:
            return StatusMessage.IN_PROGRESS

    def run_script(self, module_name: str, script_name: str, arguments: dict = {}) -> StatusMessage:
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
            self.logger.info(
                f'Runnning {script_name}.py script with following configuration:\n{clean}',
            )
            submodule.main(script_conf=script_conf)
            return StatusMessage.SUCCESS
        except Exception:
            self.logger.exception('Server error while running {} script'.format(script_name))
            return StatusMessage.FAIL

    def github_populate(self, paths: list[str]):
        for path in paths:
            self.run_script(
                'parseAndPopulate',
                'populate',
                {'dir': path, 'notify-indexing': self._notify_indexing},
            )
