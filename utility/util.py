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

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import fnmatch
import glob
import hashlib
import json
import logging
import optparse
import os
import re
import stat
import time
import typing as t
import warnings
from configparser import ConfigParser
from datetime import date, datetime

import dateutil.parser
import requests
from Crypto.Hash import HMAC, SHA
from pyang import plugin
from pyang.plugins.check_update import check_update

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from redisConnections.redisConnection import RedisConnection
from utility import message_factory
from utility.create_config import create_config
from utility.staticVariables import JobLogStatuses, backup_date_format, json_headers
from utility.yangParser import create_context

single_line_re = re.compile(r'//.*')
multi_line_re = re.compile(r'/\*.*?\*/', flags=re.MULTILINE)
name_re = re.compile(r'(sub)?module[\s\n\r]+"?([\w_\-\.]+)')
revision_re = re.compile(r'revision[\s\n\r]+"?(\d{4}-\d{2}-\d{2})')


def strip_comments(text: str):
    text = single_line_re.sub('', text)
    text = multi_line_re.sub('', text)
    return text


def parse_name(text: str):
    match = name_re.search(text)
    return match.groups()[1] if match else 'foobar'


def parse_revision(text: str):
    match = revision_re.search(text)
    return match.groups()[0] if match else '1970-01-01'


def resolve_revision(filename: str):
    with open(filename) as f:
        text = f.read()
        text = strip_comments(text)
        return parse_revision(text)


def find_files(directory: str, pattern: str):
    """Generator that yields files matching a pattern

    Arguments:
        :param directory    directory in which to search
        :param pattern      a unix shell style pattern
        :yield              a tuple of the containing directory and the path to the matching file
    """
    for root, _, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                path = os.path.join(root, basename)
                yield root, path


def get_yang(name: str, revision: t.Optional[str] = None, config: ConfigParser = create_config()) -> t.Optional[str]:
    """Get the path to a yang file stored in the save-file-dir.
    If no revision is specified, the path to the latest revision is returned.

    Arguments:
        :param name         (str) name of the yang module
        :param revision     (Optional(str)) revision of the yang module
        :param config     (ConfigParser) config instance from which save-file-dir is extracted
    :return             (Optional(str)) path to the matched file
    """
    save_file_dir = config.get('Directory-Section', 'save-file-dir')
    if revision:
        return os.path.join(save_file_dir, f'{name}@{revision}.yang')
    files = glob.glob(os.path.join(save_file_dir, f'{name}@*.yang'))
    if not files:
        return None
    filename = max(files)
    return filename


def change_permissions_recursive(path: str):
    """Change permissions of all the files and folders recursively to rwxrwxr--

    Argument:
        :param path     (str) path to file or folder we need to change permission on
    """
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for directory in [os.path.join(root, d) for d in dirs]:
                os.chmod(
                    directory,
                    stat.S_IRGRP
                    | stat.S_IWGRP
                    | stat.S_IXGRP
                    | stat.S_IRUSR
                    | stat.S_IWUSR
                    | stat.S_IXUSR
                    | stat.S_IROTH,
                )
            for file in [os.path.join(root, f) for f in files]:
                os.chmod(
                    file,
                    stat.S_IRGRP
                    | stat.S_IWGRP
                    | stat.S_IXGRP
                    | stat.S_IRUSR
                    | stat.S_IWUSR
                    | stat.S_IXUSR
                    | stat.S_IROTH,
                )
    else:
        os.chmod(
            path,
            stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IROTH,
        )


def create_signature(secret_key: str, string: str):
    """Create the signed message using secret_key and string_to_sign

    Arguments:
        :param string: (str) String that needs to be signed
        :param secret_key: Secret key that the string will be signed with
        :return A string of 2* `digest_size` bytes. It contains only
            hexadecimal ASCII digits.
    """
    hmac = HMAC.new(secret_key.encode('utf-8'), string.encode('utf-8'), SHA)
    return hmac.hexdigest()


def send_for_es_indexing(body_to_send: dict, logger: logging.Logger, paths: dict):
    """
    Creates a json file that will be used for Elasticsearch indexing.

    Arguments:
        :param body_to_send:        (dict) body that needs to be indexed
        :param logger:              (logging.Logger) Logger used for logging
        :param paths                (dict) dict containing paths to the necessary files
    """
    logger.info(f'Updating metadata for elk - file creation in {paths["cache_path"]} or {paths["deletes_path"]}')
    while os.path.exists(paths['lock_path']):
        time.sleep(10)
    try:
        try:
            open(paths['lock_path'], 'w').close()
        except Exception:
            raise Exception(f'Failed to obtain lock {paths["lock_path"]}')

        changes_cache = {}
        delete_cache = []
        if os.path.exists(paths['cache_path']) and os.path.getsize(paths['cache_path']) > 0:
            with open(paths['cache_path'], 'r') as reader:
                changes_cache = json.load(reader)
        if os.path.exists(paths['deletes_path']) and os.path.getsize(paths['deletes_path']) > 0:
            with open(paths['deletes_path'], 'r') as reader:
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

        with open(paths['cache_path'], 'w') as writer:
            json.dump(changes_cache, writer, indent=2)

        with open(paths['deletes_path'], 'w') as writer:
            json.dump(delete_cache, writer, indent=2)
    except Exception as e:
        logger.exception('Problem while sending modules to indexing')
        os.unlink(paths['lock_path'])
        raise Exception(f'Caught exception {e}')
    os.unlink(paths['lock_path'])


def prepare_for_es_removal(yc_api_prefix: str, modules_to_delete: list, save_file_dir: str, logger: logging.Logger):
    """Makes an API request to identify dependencies of the modules to be deleted.
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
):
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
            logger.info('Calling draftPull.py script')
            module = __import__('ietfYangDraftPull', fromlist=['draftPull'])
            submodule = getattr(module, 'draftPull')
            submodule.main()
        except Exception:
            logger.exception('Error occurred while running draftPull.py script')
    return post_body


def job_log(file_basename: str):
    def _job_log_decorator(func):
        config = create_config()
        temp_dir = config.get('Directory-Section', 'temp')

        def _job_log(*args, **kwargs):
            nonlocal temp_dir, file_basename
            start_time = int(time.time())
            write_job_log(start_time, temp_dir, file_basename, status=JobLogStatuses.IN_PROGRESS)
            try:
                success_messages: list[dict[str, str], ...] = func(*args, **kwargs)
            except Exception as e:
                write_job_log(
                    start_time,
                    temp_dir,
                    file_basename,
                    end_time=int(time.time()),
                    error=str(e),
                    status=JobLogStatuses.FAIL,
                )
                return
            write_job_log(
                start_time,
                temp_dir,
                file_basename,
                end_time=int(time.time()),
                messages=success_messages,
                status=JobLogStatuses.SUCCESS,
            )

        return _job_log

    return _job_log_decorator


def write_job_log(
    start_time: int,
    temp_dir: str,
    filename: str,
    status: JobLogStatuses,
    end_time: t.Union[str, int] = '',
    messages: t.Optional[t.Union[tuple, list]] = (),
    error: str = '',
):
    """
    Dump job run information into cronjob.json file.

    Arguments:
        :param start_time   (int) Start time of job
        :param temp_dir     (str) Path to the directory where cronjob.json file will be stored
        :param filename     (str) Name of python script
        :param messages     (list) Optional - list of additional messages
        :param end_time     (Union[str, int]) - End time of the job
        :param error        (str) Error message - if any error has occurred
        :param status       (str) Status of job run - either 'Fail' or 'Success'
    """
    cronjob_results_path = os.path.join(temp_dir, 'cronjob.json')
    result = {'start': start_time, 'end': end_time, 'status': status, 'error': error, 'messages': messages or ()}

    try:
        with open(cronjob_results_path, 'r') as reader:
            file_content = json.load(reader)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        file_content = {}

    filename = filename.split('.py')[0]
    # If successfully rewrite, otherwise use last_successfull value from JSON
    last_successful = None
    if status == JobLogStatuses.SUCCESS:
        last_successful = end_time
    elif previous_state := file_content.get(filename):
        last_successful = previous_state.get('last_successfull')

    result['last_successfull'] = last_successful
    file_content[filename] = result

    with open(cronjob_results_path, 'w') as writer:
        writer.write(json.dumps(file_content, indent=4))


def fetch_module_by_schema(schema: t.Optional[str], dst_path: str) -> bool:
    """Fetch content of yang module from GitHub and store it to the file.

    Arguments:
        :param schema       (Optional[str]) URL to GitHub where the content of the module should be stored
        :param dst_path     (str) Path where the module should be saved
        :return             (bool) Whether the content of the module was obtained or not.
    """
    file_exist = False
    try:
        assert schema
        yang_file_response = requests.get(schema)
        yang_file_content = yang_file_response.content.decode(encoding='utf-8')

        if yang_file_response.status_code == 200:
            with open(dst_path, 'w') as writer:
                writer.write(yang_file_content)
            os.chmod(dst_path, 0o644)
            file_exist = os.path.isfile(dst_path)
    except Exception:
        file_exist = os.path.isfile(dst_path)

    return file_exist


def context_check_update_from(old_schema: str, new_schema: str, yang_models: str, save_file_dir: str):
    """Perform pyang --check-update-from validation using context.

    Argumets:
        :param old_schema       (str) full path to the yang file with older revision
        :param new_schema       (str) full path to the yang file with newer revision
        :param yang_models      (str) path to the directory where YangModels/yang repo is cloned
        :param save_file_dir    (str) path to the directory where all the yang files will be saved
    """
    plugin.plugins = []
    plugin.init([])
    ctx = create_context(f'{os.path.abspath(yang_models)}:{save_file_dir}')
    ctx.opts.lint_namespace_prefixes = []
    ctx.opts.lint_modulename_prefixes = []
    opt_parser = optparse.OptionParser('', add_help_option=False)
    for plug in plugin.plugins:
        plug.setup_ctx(ctx)
        plug.add_opts(opt_parser)
    with open(new_schema, 'r', errors='ignore') as reader:
        new_schema_ctx = ctx.add_module(new_schema, reader.read())
    ctx.opts.check_update_from = old_schema
    ctx.opts.old_path = [os.path.abspath(yang_models)]
    ctx.opts.verbose = False
    ctx.opts.old_deviation = []
    retry = 5
    while retry:
        try:
            ctx.validate()
            # NOTE: ResourceWarning appears due to the incorrect way pyang opens files for reading
            # ResourceWarning: Enable trace malloc to get the object allocation traceback
            with warnings.catch_warnings(record=True):
                check_update(ctx, new_schema_ctx)
            break
        except Exception as e:
            retry -= 1
            if retry == 0:
                raise e

    return ctx, new_schema_ctx


def get_list_of_backups(directory: str) -> t.List[str]:
    """Get a sorted list of backup file or directory names in a directory.
    Backups are identified by matching backup date format.

    Arguments:
        :param directory    directory in with to search
        :return             sorted list of file/directory names
    """
    dates: t.List[str] = []
    for name in os.listdir(directory):
        try:
            i = name.index('.')
            root = name[:i]
            datetime.strptime(root, backup_date_format)
            if os.stat(os.path.join(directory, name)).st_size == 0:
                continue
            dates.append(name)
        except ValueError:
            continue
    return sorted(dates)


def validate_revision(revision: str) -> str:
    """Validate if revision has correct format and return default 1970-01-01 if not.

    Argument:
        :param revision     (str) Revision to validate
    """
    if '02-29' in revision:
        revision = revision.replace('02-29', '02-28')

    try:
        dateutil.parser.parse(revision)
        year, month, day = map(int, revision.split('-'))
        revision = date(year, month, day).isoformat()
    except (ValueError, dateutil.parser.ParserError):
        revision = '1970-01-01'

    return revision


def revision_to_date(revision: str) -> date:
    return date.fromisoformat(validate_revision(revision))


def hash_pw(password: str) -> str:
    encoded_password = password.encode(encoding='utf-8', errors='strict')
    return hashlib.sha256(encoded_password).hexdigest()
