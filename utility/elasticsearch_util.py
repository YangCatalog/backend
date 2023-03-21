import json
import logging
import os
import time
import typing as t
from dataclasses import dataclass

import requests

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from redisConnections.redisConnection import RedisConnection
from utility import message_factory
from utility.staticVariables import json_headers

ESIndexingBody = t.TypedDict(
    'ESIndexingBody',
    {
        'modules-to-index': dict[str, str],
        'modules-to-delete': list[str],
    },
    total=False,
)


@dataclass
class ESIndexingPaths:
    cache_path: str
    deletes_path: str
    failed_path: str
    lock_path: str


def send_for_es_indexing(body_to_send: ESIndexingBody, logger: logging.Logger, paths: ESIndexingPaths):
    """
    Creates a json file that will be used for Elasticsearch indexing.

    Arguments:
        :param body_to_send:        (dict) body that needs to be indexed
        :param logger:              (logging.Logger) Logger used for logging
        :param paths                (dict) dict containing paths to the necessary files
    """
    logger.info(f'Updating metadata for elk - file creation in {paths.cache_path} or {paths.deletes_path}')
    while os.path.exists(paths.lock_path):
        time.sleep(10)
    try:
        try:
            open(paths.lock_path, 'w').close()
        except Exception:
            raise Exception(f'Failed to obtain lock {paths.lock_path}')

        changes_cache = {}
        delete_cache = []
        if os.path.exists(paths.cache_path) and os.path.getsize(paths.cache_path) > 0:
            with open(paths.cache_path, 'r') as reader:
                changes_cache = json.load(reader)
        if os.path.exists(paths.deletes_path) and os.path.getsize(paths.deletes_path) > 0:
            with open(paths.deletes_path, 'r') as reader:
                delete_cache = json.load(reader)

        if body_to_send.get('modules-to-index') is None:
            body_to_send['modules-to-index'] = {}

        if body_to_send.get('modules-to-delete') is None:
            body_to_send['modules-to-delete'] = []

        for mname, mpath in body_to_send['modules-to-index'].items():
            changes_cache[mname] = mpath
        for mname in body_to_send['modules-to-delete']:
            exists = False
            for existing in delete_cache:
                if mname == existing:
                    exists = True
            if not exists:
                delete_cache.append(mname)

        with open(paths.cache_path, 'w') as writer:
            json.dump(changes_cache, writer, indent=2)

        with open(paths.deletes_path, 'w') as writer:
            json.dump(delete_cache, writer, indent=2)
    except Exception as e:
        logger.exception('Problem while sending modules to indexing')
        os.unlink(paths.lock_path)
        raise Exception(f'Caught exception {e}')
    os.unlink(paths.lock_path)


def prepare_for_es_removal(
    yc_api_prefix: str,
    modules_to_delete: list,
    save_file_dir: str,
    logger: logging.Logger,
) -> ESIndexingBody:
    """
    Makes an API request to identify dependencies of the modules to be deleted.
    Updates metadata of dependencies in Redis no longer list the modules to be
    deleted as dependents. Deletes the schema files for modules to be deleted
    from the disk.

    Arguments:
        :param yc_api_prefix        (str) prefix for sending request to API
        :param modules_to_delete    (list) name@revision list of modules to be deleted
        :param save_file_dir        (str) path to the directory where all the yang files are saved
        :param logger               (Logger) formated logger with the specified name
    """
    redis_connection = RedisConnection()
    for mod_to_delete in modules_to_delete:
        name, revision_organization = mod_to_delete.split('@')
        revision = revision_organization.split('/')[0]
        path_to_delete_local = f'{save_file_dir}/{name}@{revision}.yang'
        data = {'input': {'dependents': [{'name': name}]}}

        response = requests.post(f'{yc_api_prefix}/search-filter', json=data)
        if response.status_code == 200:
            data = response.json()
            modules = data['yang-catalog:modules']['module']
            for mod in modules:
                redis_key = f'{mod["name"]}@{mod["revision"]}/{mod["organization"]}'
                redis_connection.delete_dependent(redis_key, name)
        if os.path.exists(path_to_delete_local):
            os.remove(path_to_delete_local)

    post_body = {}
    if modules_to_delete:
        post_body = {'modules-to-delete': modules_to_delete}
        logger.debug(f'Modules to delete:\n{json.dumps(post_body, indent=2)}')
        mf = message_factory.MessageFactory()
        mf.send_removed_yang_files(json.dumps(post_body, indent=4))

    return post_body


def prepare_for_es_indexing(
    yc_api_prefix: str,
    modules_to_index: str,
    logger: logging.Logger,
    save_file_dir: str,
    force_indexing: bool = False,
) -> ESIndexingBody:
    """
    Sends the POST request which will activate indexing script for modules which will
    help to speed up process of searching. It will create a json body of all the modules
    containing module name and path where the module can be found if we are adding new modules.

    Arguments:
        :param yc_api_prefix        (str) prefix for sending request to API
        :param modules_to_index     (str) path to the prepare.json file generated while parsing
        :param logger               (logging.Logger) formated logger with the specified name
        :param save_file_dir        (str) path to the directory where all the yang files will be saved
        :param force_indexing       (bool) Whether we should force indexing even if module exists in cache.
    """
    mf = message_factory.MessageFactory()
    es_manager = ESManager()
    with open(modules_to_index, 'r') as reader:
        sdos_json = json.load(reader)
        logger.debug(f'{len(sdos_json.get("module", []))} modules loaded from prepare.json')
    post_body = {}
    load_new_files_to_github = False
    for module in sdos_json.get('module', []):
        url = f'{yc_api_prefix}/search/modules/{module["name"]},{module["revision"]},{module["organization"]}'
        response = requests.get(url, headers=json_headers)
        code = response.status_code

        in_es = False
        in_redis = code in [200, 201, 204]
        if in_redis:
            in_es = es_manager.document_exists(ESIndices.AUTOCOMPLETE, module)
        else:
            load_new_files_to_github = True

        if force_indexing or not in_es or not in_redis:
            path = f'{save_file_dir}/{module.get("name")}@{module.get("revision")}.yang'
            key = f'{module["name"]}@{module["revision"]}/{module["organization"]}'
            post_body[key] = path

    if post_body:
        post_body = {'modules-to-index': post_body}
        logger.debug(f'Modules to index:\n{json.dumps(post_body, indent=2)}')
        mf.send_added_new_yang_files(json.dumps(post_body, indent=4))
    if load_new_files_to_github:
        try:
            logger.info('Calling draft_push.py script')
            module = __import__('automatic_push', fromlist=['draft_push'])
            submodule = getattr(module, 'draft_push')
            submodule.main()
        except Exception:
            logger.exception('Error occurred while running draft_push.py script')
    return post_body
