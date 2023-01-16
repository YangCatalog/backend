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
Cronjob tool that automatically runs populate.py over 3 different directories:
I. RFC .yang modules -> standard/ietf/RFC path
II. Draft .yang modules -> experimental/ietf-extracted-YANG-modules path
III. IANA maintained modules -> standard/iana path
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import logging
import os
import shutil
import time

import requests
from draftPull_config import args, help

import utility.log as log
from ietfYangDraftPull import draftPullUtility
from utility import repoutil
from utility.create_config import create_config
from utility.scriptConfig import BaseScriptConfig
from utility.staticVariables import JobLogStatuses, github_url
from utility.util import job_log

current_file_basename = os.path.basename(__file__)


def run_populate_script(directory: str, notify: bool, logger: logging.Logger) -> bool:
    """
    Run populate.py script and return whether execution was successful or not.

    Argumets:
        :param directory    (str) full path to directory with yang modules
        :param notify       (str) whether to send files for'indexing
        :param logger       (obj) formated logger with the specified name
    """
    successful = True
    try:
        module = __import__('parseAndPopulate', fromlist=['populate'])
        submodule = getattr(module, 'populate')
        script_conf = submodule.ScriptConfig()
        script_conf.args.__setattr__('sdo', True)
        script_conf.args.__setattr__('dir', directory)
        script_conf.args.__setattr__('notify_indexing', notify)
        logger.info(f'Running populate.py script over {directory}')
        submodule.main(script_conf=script_conf)
    except Exception:
        logger.exception('Error occurred while running populate.py script')
        successful = False

    return successful


def populate_directory(directory: str, notify_indexing: bool, logger: logging.Logger):
    """
    Run the populate script on a directory and return the result.

    Arguments:
        :param directory        (str) Directory to run the populate script on
        :param notify_indexing  (bool)
        :param logger           (Logger)
        :return                 (tuple[bool, str]) First specifies whether the script ran successfully,
            second element is a corresponding text message.
    """
    logger.info(f'Checking module filenames without revision in {directory}')
    draftPullUtility.check_name_no_revision_exist(directory, logger)

    logger.info(f'Checking for early revision in {directory}')
    draftPullUtility.check_early_revisions(directory, logger)

    success = run_populate_script(directory, notify_indexing, logger)
    if success:
        message = 'Populate script finished successfully'
    else:
        message = 'Error while calling populate script'
    return success, message


def main(script_conf: BaseScriptConfig = BaseScriptConfig(help, args, None if __name__ == '__main__' else [])):
    start_time = int(time.time())
    args = script_conf.args

    config_path = args.config_path
    config = create_config(config_path)
    notify_indexing = config.get('General-Section', 'notify-index')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    ietf_rfc_url = config.get('Web-Section', 'ietf-RFC-tar-private-url')
    temp_dir = config.get('Directory-Section', 'temp')
    logger = log.get_logger('draftPullLocal', f'{log_directory}/jobs/draft-pull-local.log')
    logger.info('Starting cron job IETF pull request local')
    job_log(start_time, temp_dir, status=JobLogStatuses.IN_PROGRESS, filename=current_file_basename)

    messages = []
    notify_indexing = notify_indexing == 'True'
    success = True
    repo = None
    try:
        # Clone YangModels/yang repository
        clone_dir = os.path.join(temp_dir, 'draftpulllocal')
        if os.path.exists(clone_dir):
            shutil.rmtree(clone_dir)
        repo = repoutil.ModifiableRepoUtil(
            os.path.join(github_url, 'YangModels/yang.git'),
            clone_options={'config_username': config_name, 'config_user_email': config_email, 'local_dir': clone_dir},
        )
        logger.info(f'YangModels/yang repo cloned to local directory {repo.local_dir}')

        response = requests.get(ietf_rfc_url)
        tgz_path = os.path.join(repo.local_dir, 'rfc.tgz')
        extract_to = os.path.join(repo.local_dir, 'standard/ietf/RFC')
        with open(tgz_path, 'wb') as zfile:
            zfile.write(response.content)
        tar_opened = draftPullUtility.extract_rfc_tgz(tgz_path, extract_to, logger)

        if tar_opened:
            # Standard RFC modules
            rfc_path = os.path.join(repo.local_dir, 'standard/ietf/RFC')
            directory_success, message = populate_directory(rfc_path, notify_indexing, logger)
            success = success and directory_success
            messages.append({'label': 'Standard RFC modules', 'message': message})

        # Experimental modules
        experimental_path = os.path.join(repo.local_dir, 'experimental/ietf-extracted-YANG-modules')

        directory_success, message = populate_directory(experimental_path, notify_indexing, logger)
        success = success and directory_success
        messages.append({'label': 'Experimental modules', 'message': message})

        # IANA modules
        iana_path = os.path.join(repo.local_dir, 'standard/iana')

        if os.path.exists(iana_path):
            directory_success, message = populate_directory(iana_path, notify_indexing, logger)
            success = success and directory_success
            messages.append({'label': 'IANA modules', 'message': message})

    except Exception as e:
        logger.exception('Exception found while running draftPullLocal script')
        job_log(start_time, temp_dir, error=str(e), status=JobLogStatuses.FAIL, filename=current_file_basename)
        raise e
    if success:
        logger.info('Job finished successfully')
    else:
        logger.info('Job finished, but errors found while calling populate script')
    job_log(start_time, temp_dir, messages=messages, status=JobLogStatuses.SUCCESS, filename=current_file_basename)


if __name__ == '__main__':
    main()
