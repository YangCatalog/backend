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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import datetime
import fnmatch
import json
import optparse
import os
import socket
import stat
import sys
import time
import typing as t
import warnings

import requests
from Crypto.Hash import HMAC, SHA
from elasticsearch import Elasticsearch
from pyang import plugin
from pyang.plugins.check_update import check_update
from redisConnections.redisConnection import RedisConnection

from utility import messageFactory, yangParser
from utility.confdService import ConfdService
from utility.create_config import create_config
from utility.staticVariables import backup_date_format, json_headers
from utility.yangParser import create_context


def get_curr_dir(path: str):
    """Get current working directory

    Argument:
        :param path     (str) path to file
        :return     path to current directory
    """
    cur_dir = '/'.join(path.split('/')[:-1])
    if cur_dir == '':
        return os.getcwd()
    else:
        return cur_dir


def find_first_file(directory: str, pattern: str, pattern_with_revision: str, yang_models_dir: str = ''):
    """ Search for the first file in 'directory' which either match 'pattern' or 'pattern_with_revision' string.

    Arguments:
        :param directory                (str) directory where to look for a file
        :param pattern                  (str) name of the yang file
        :param pattern_with_revision    (str) name and revision of the module in format <name>@<revision>
        :param yang_models_dir          (str) path to the directory where YangModels/yang repo is cloned
        :return path to current directory
    """
    def __match_file(directory, pattern):
        for root, _, files in os.walk(directory):
            for basename in files:
                if fnmatch.fnmatch(basename, pattern):
                    filename = os.path.join(root, basename)
                    return filename

    rfcs_dir = '{}/standard/ietf/RFC'.format(yang_models_dir)
    standards_dir = '{}/standard'.format(yang_models_dir)
    experimental_dir = '{}/experimental/ietf-extracted-YANG-modules'.format(yang_models_dir)
    paths_to_check = [directory, rfcs_dir, standards_dir, experimental_dir, yang_models_dir]
    patterns_order = []

    if '*' not in pattern_with_revision:
        patterns_order = [pattern_with_revision, pattern]
    else:
        patterns_order = [pattern, pattern_with_revision]

    for path in paths_to_check:
        for pattern in patterns_order:
            filename = __match_file(path, pattern)
            if filename:
                try:
                    revision = yangParser.parse(filename).search('revision')[0].arg
                except Exception:
                    revision = '1970-01-01'
                if '*' not in pattern_with_revision:
                    if revision in pattern_with_revision:
                        return filename
                else:
                    return filename


def change_permissions_recursive(path: str):
    """ Change permissions of all the files and folders recursively to rwxrwxr--

    Argument:
        :param path:     (str) path to file or folder we need to change permission on
    """
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for dir in [os.path.join(root, d) for d in dirs]:
                os.chmod(dir, stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IROTH)
            for file in [os.path.join(root, f) for f in files]:
                os.chmod(file, stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IROTH)
    else:
        os.chmod(path, stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IROTH)


def create_signature(secret_key: str, string: str):
    """ Create the signed message using secret_key and string_to_sign

    Arguments:
        :param string: (str) String that needs to be signed
        :param secret_key: Secret key that the string will be signed with
        :return A string of 2* `digest_size` bytes. It contains only
            hexadecimal ASCII digits.
    """
    string_to_sign = string.encode('utf-8')
    if sys.version_info >= (3, 4):
        secret_key = secret_key.encode('utf-8')
    hmac = HMAC.new(secret_key, string_to_sign, SHA)
    return hmac.hexdigest()


def send_to_indexing2(body_to_send: dict, LOGGER, changes_cache_dir: str, delete_cache_dir: str, lock_file: str):
    """
    Creates a json file that will be used for elasticsearch indexing.
    :param body_to_send:        (dict) body that needs to be indexed
    :param LOGGER:              (logging) Logger used for logging
    :param changes_cache_dir:   (str) path to file containing module to be indexed (can be empty)
    :param delete_cache_dir:    (str) path to file containing module to be removed from indexing (can be empty)
    :param lock_file:           (str) path to file working as a lock file. If exists script has to wait until removed
    """
    LOGGER.info('Updating metadata for elk - file creation in {} or {}'.format(changes_cache_dir, delete_cache_dir))
    while os.path.exists(lock_file):
        time.sleep(10)
    try:
        try:
            open(lock_file, 'w').close()
        except Exception:
            raise Exception('Failed to obtain lock {}'.format(lock_file))

        changes_cache = dict()
        delete_cache = []
        if os.path.exists(changes_cache_dir) and os.path.getsize(changes_cache_dir) > 0:
            f = open(changes_cache_dir)
            changes_cache = json.load(f)
            f.close()
        if os.path.exists(delete_cache_dir) and os.path.getsize(delete_cache_dir) > 0:
            f = open(delete_cache_dir)
            delete_cache = json.load(f)
            f.close()

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
        fd = open(changes_cache_dir, 'w')
        fd.write(json.dumps(changes_cache))
        fd.close()
        fd = open(delete_cache_dir, 'w')
        fd.write(json.dumps(delete_cache))
        fd.close()
    except Exception as e:
        os.unlink(lock_file)
        raise Exception('Caught exception {}'.format(e))
    os.unlink(lock_file)


def send_to_indexing(body_to_send: str, credentials: list, protocol: str, LOGGER, secret_key: str, api_ip: str):
    """ Send a request to index new or deleted yang modules with body that
    contains path to the modules and name of the modules.

    This definition is DEPRECATED and should not be used any more in any situation !!!

    Arguments:
        :param body_to_send:    (str) body that contains path to the modules and names of the modules
        :param credentials      (list) basic authorization credentials - username, password respectively
        :param protocol         (str) protocol where API runs
        :param LOGGER           (obj) formated logger with the specified name
        :param secret_key       (str) secret key to sign the body with
        :param api_ip           (str) IP address or domain name of yangcatalog.org API
    """
    ip_addr = socket.gethostbyname(api_ip)
    LOGGER.info('IP address from hostname {} is {}'.format(api_ip, ip_addr))
    path = '{}://{}/yang-search/metadata_update'.format(protocol, api_ip)
    LOGGER.info('Sending data for indexing with body {} \n and path {}'.format(body_to_send, path))

    verify = False
    if api_ip == 'yangcatalog.org':
        verify = True
    response = requests.post(path, data=body_to_send,
                             auth=(credentials[0], credentials[1]),
                             headers={**json_headers,
                                      'X-YC-Signature': 'sha1={}'.format(create_signature(secret_key, body_to_send))},
                             verify=verify)
    code = response.status_code

    if code != 200 and code != 201 and code != 204:
        LOGGER.error('Could not send data for indexing. Reason: {}'.format(response.text))
    else:
        LOGGER.info('Data sent for indexing successfully')


def prepare_to_indexing(yc_api_prefix: str, modules_to_index, LOGGER, save_file_dir: str, temp_dir: str,
                        sdo_type: bool = False, delete: bool = False, from_api: bool = True, force_indexing: bool = False):
    """ Sends the POST request which will activate indexing script for modules which will
    help to speed up process of searching. It will create a json body of all the modules
    containing module name and path where the module can be found if we are adding new
    modules. Other situation can be if we need to delete module. In this case we are sending
    list of modules that need to be deleted.

    Arguments:
        :param yc_api_prefix        (str) prefix for sending request to api
        :param modules_to_index     (json file) prepare.json file generated while parsing
        :param LOOGER:              (obj) LOGGER in case we can not use receiver's because other module is calling this method
        :param save_file_dir        (str) path to the directory where all the yang files will be saved
        :param temp_dir             (str) path to temporary directory
        :param sdo_type             (bool) Whether or not it is sdo that needs to be sent
        :param delete               (bool) Whether or not we are deleting module
        :param from_api             (bool) Whether or not api sent the request to index.
        :param force_indexing       (bool) Whether or not we should force indexing even if module exists in cache.
    """
    LOGGER.info('Sending data for indexing')
    mf = messageFactory.MessageFactory()
    if delete:
        post_body = {'modules-to-delete': modules_to_index}

        mf.send_removed_yang_files(json.dumps(post_body, indent=4))
        for mod in modules_to_index:
            name, revision_organization = mod.split('@')
            revision = revision_organization.split('/')[0]
            path_to_delete_local = '{}/{}@{}.yang'.format(save_file_dir, name, revision)
            data = {'input': {'dependents': [{'name': name}]}}

            response = requests.post('{}search-filter'.format(yc_api_prefix), json=data)
            if response.status_code == 200:
                data = response.json()
                modules = data['yang-catalog:modules']['module']
                for mod in modules:
                    module_key = '{},{},{}'.format(mod['name'], mod['revision'], mod['organization'])
                    confdService = ConfdService()
                    confdService.delete_dependent(module_key, name)
                    redis_key = '{}@{}/{}'.format(mod['name'], mod['revision'], mod['organization'])
                    redisConnection = RedisConnection()
                    redisConnection.delete_dependent(redis_key, name)
            if os.path.exists(path_to_delete_local):
                os.remove(path_to_delete_local)
    else:
        with open(modules_to_index, 'r') as f:
            sdos_json = json.load(f)
            LOGGER.debug('{} modules loaded from prepare.json'.format(len(sdos_json.get('module', []))))
        post_body = {}
        load_new_files_to_github = False
        if from_api:
            if sdo_type:
                prefix = 'sdo/'
            else:
                prefix = 'vendor/'

            for module in sdos_json.get('module', []):
                url = '{}search/modules/{},{},{}'.format(yc_api_prefix,
                                                         module['name'], module['revision'], module['organization'])
                response = requests.get(url, headers=json_headers)
                code = response.status_code
                if force_indexing or (code != 200 and code != 201 and code != 204):
                    if module.get('schema'):
                        path = '{}{}'.format(prefix, module['schema'].split('githubusercontent.com/')[1])
                        path = os.path.abspath('{}/{}'.format(temp_dir, path))
                    else:
                        path = 'module does not exist'
                    key = '{}@{}/{}'.format(module['name'], module['revision'], module['organization'])
                    post_body[key] = path
        else:
            for module in sdos_json.get('module', []):
                url = '{}search/modules/{},{},{}'.format(yc_api_prefix,
                                                         module['name'], module['revision'], module['organization'])
                response = requests.get(url, headers=json_headers)
                code = response.status_code

                in_es = False
                if code != 200 and code != 201 and code != 204:
                    load_new_files_to_github = True
                else:
                    es_result = get_module_from_es(module.get('name'), module.get('revision'))
                    in_es = False if es_result == {} else es_result['hits']['total'] != 0
                if force_indexing or not in_es or (
                        code != 200 and code != 201 and code != 204):
                    path = '{}/{}@{}.yang'.format(save_file_dir, module.get('name'), module.get('revision'))
                    key = '{}@{}/{}'.format(module['name'], module['revision'], module['organization'])
                    post_body[key] = path

        if len(post_body) > 0:
            post_body = {'modules-to-index': post_body}
        if len(post_body) > 0 and not force_indexing:
            mf.send_added_new_yang_files(json.dumps(post_body, indent=4))
        if load_new_files_to_github:
            try:
                LOGGER.info('Calling draftPull.py script')
                module = __import__('ietfYangDraftPull', fromlist=['draftPull'])
                submodule = getattr(module, 'draftPull')
                submodule.main()
            except Exception:
                LOGGER.exception('Error occurred while running draftPull.py script')
    return post_body


def job_log(start_time: int, temp_dir: str, filename: str, messages: list = [], error: str = '', status: str = ''):
    """ Dump job run information into cronjob.json file.

    Arguments:
    :param start_time   (int) Start time of job
    :param temp_dir     (str) Path to the directory where cronjob.json file will be stored
    :param filename     (str) Name of python script
    :param messages     (list) Optional - list of additional messages
    :param error        (str) Error message - if any error has occured
    :param status       (str) Status of job run - either 'Fail' or 'Success'
    """
    end_time = int(time.time())
    result = {}
    result['start'] = start_time
    result['end'] = end_time
    result['status'] = status
    result['error'] = error
    result['messages'] = messages

    try:
        with open('{}/cronjob.json'.format(temp_dir), 'r') as f:
            file_content = json.load(f)
    except Exception:
        file_content = {}

    filename = filename.split('.py')[0]
    last_successfull = None
    # If successfull rewrite, otherwise use last_successfull value from JSON
    if status == 'Success':
        last_successfull = end_time
    else:
        try:
            previous_state = file_content.get(filename)
            last_successfull = previous_state.get('last_successfull')
        except Exception:
            last_successfull = None

    result['last_successfull'] = last_successfull
    file_content[filename] = result

    with open('{}/cronjob.json'.format(temp_dir), 'w') as f:
        f.write(json.dumps(file_content, indent=4))


def fetch_module_by_schema(schema: str, dst_path: str):
    """ Fetch content of yang module from Github and store it to the file.

    Arguments:
    :param schema       (str) URL to Github where the content of the module should be stored
    :param dst_path     (str) Path where the module should be saved
    :return             Whether the content of the module was obtained or not.
    :rtype              bool
    """
    file_exist = False
    try:
        yang_file_response = requests.get(schema)
        yang_file_content = yang_file_response.content.decode(encoding='utf-8')

        if yang_file_response.status_code == 200:
            with open(dst_path, 'w') as f:
                f.write(yang_file_content)
            os.chmod(dst_path, 0o644)
            file_exist = os.path.isfile(dst_path)
    except Exception:
        file_exist = os.path.isfile(dst_path)

    return file_exist


def get_module_from_es(name: str, revision: str):
    """ Get module with the given name and revision from Elasticsearch.

    Arguments:
        :param name         (str) name of the module
        :param revision     (str) revision of the module in format YYYY-MM-DD
    """
    config = create_config()
    es_aws = config.get('DB-Section', 'es-aws', fallback=False)
    es_host = config.get('DB-Section', 'es-host', fallback='localhost')
    es_port = config.get('DB-Section', 'es-port', fallback='9200')
    elk_credentials = config.get('Secrets-Section', 'elk-secret', fallback='').strip('"').split(' ')

    if es_aws == 'True':
        es = Elasticsearch([es_host], http_auth=(elk_credentials[0], elk_credentials[1]), scheme='https', port=443)
    else:
        es = Elasticsearch([{'host': '{}'.format(es_host), 'port': es_port}])

    query = \
        {
            "query": {
                "bool": {
                    "must": [{
                        "match_phrase": {
                            "module.keyword": {
                                "query": name
                            }
                        }
                    }, {
                        "match_phrase": {
                            "revision": {
                                "query": revision
                            }
                        }
                    }]
                }
            }
        }

    try:
        es_result = es.search(index='modules', doc_type='modules', body=query)
    except Exception:
        return {}

    return es_result


def context_check_update_from(old_schema: str, new_schema: str, yang_models: str, save_file_dir: str):
    """ Perform pyang --check-update-from validation using context.

    Argumets:
        :param old_schema       (str) full path to the yang file with older revision
        :param new_schema       (str) full path to the yang file with newer revision
        :param yang_models      (str) path to the directory where YangModels/yang repo is cloned
        :param save_file_dir    (str) path to the directory where all the yang files will be saved
    """
    plugin.plugins = []
    plugin.init([])
    ctx = create_context(
        '{}:{}'.format(os.path.abspath(yang_models), save_file_dir))
    ctx.opts.lint_namespace_prefixes = []
    ctx.opts.lint_modulename_prefixes = []
    optParser = optparse.OptionParser('', add_help_option=False)
    for p in plugin.plugins:
        p.setup_ctx(ctx)
        p.add_opts(optParser)
    with open(new_schema, 'r', errors='ignore') as f:
        new_schema_ctx = ctx.add_module(new_schema, f.read())
    ctx.opts.check_update_from = old_schema
    ctx.opts.old_path = [os.path.abspath(yang_models)]
    ctx.opts.verbose = False
    ctx.opts.old_deviation = []
    retry = 5
    while retry:
        try:
            ctx.validate()
            # NOTE: ResourceWarning appears due to the incorrect way pyang opens files for reading
            # ResourceWarning: Enable tracemalloc to get the object allocation traceback
            with warnings.catch_warnings(record=True):
                check_update(ctx, new_schema_ctx)
            break
        except Exception as e:
            retry -= 1
            if retry == 0:
                raise e

    return ctx, new_schema_ctx


def get_list_of_backups(directory: str) -> t.List[str]:
    dates = []
    for name in os.listdir(directory):
        try:
            split_name = os.path.splitext(name)
            datetime.datetime.strptime(split_name[0], backup_date_format)
            if os.stat(os.path.join(directory, name)).st_size == 0:
                continue
            dates.append(split_name)
        except ValueError:
            continue
    return sorted(dates)
