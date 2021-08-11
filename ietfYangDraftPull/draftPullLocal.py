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
This python script is set as automatic cronjob
tool to parse and populate all new ietf DRAFT
and RFC modules.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import os
import shutil
import sys
import time

import requests
import utility.log as log
from utility import repoutil
from utility.util import create_config, job_log

from ietfYangDraftPull.draftPullUtility import (check_early_revisions,
                                                check_name_no_revision_exist,
                                                extract_rfc_tgz,
                                                get_draft_module_content)


class ScriptConfig:
    def __init__(self):
        self.help = 'Run populate script on all ietf RFC and DRAFT files to parse all ietf modules and populate the' \
                    ' metadata to yangcatalog if there are any new. This runs as a daily cronjob'
        parser = argparse.ArgumentParser()
        parser.add_argument('--config-path', type=str, default=os.environ['YANGCATALOG_CONFIG_PATH'],
                            help='Set path to config file')
        self.args, extra_args = parser.parse_known_args()
        self.defaults = [parser.get_default(key) for key in self.args.__dict__.keys()]

    def get_args_list(self):
        args_dict = {}
        keys = [key for key in self.args.__dict__.keys()]
        types = [type(value).__name__ for value in self.args.__dict__.values()]

        i = 0
        for key in keys:
            args_dict[key] = dict(type=types[i], default=self.defaults[i])
            i += 1
        return args_dict

    def get_help(self):
        ret = {}
        ret['help'] = self.help
        ret['options'] = {}
        ret['options']['config_path'] = 'Set path to config file'
        return ret


def run_populate_script(directory: str, notify: bool, LOGGER):
    """ Run populate.py script and return whether execution was successful or not.

    Argumets:
        :param directory    (str) full path to directory with yang modules
        :param notify       (str) whether to send files for'indexing
        :param LOGGER       (obj) formated logger with the specified name
    """
    successful = True
    try:
        module = __import__('parseAndPopulate', fromlist=['populate'])
        submodule = getattr(module, 'populate')
        script_conf = submodule.ScriptConfig()
        script_conf.args.__setattr__('sdo', True)
        script_conf.args.__setattr__('dir', directory)
        script_conf.args.__setattr__('notify_indexing', notify)
        LOGGER.info('Running populate.py script')
        submodule.main(scriptConf=script_conf)
    except Exception:
        LOGGER.exception('Error occurred while running populate.py script')
        successful = False

    return successful


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args

    config_path = args.config_path
    config = create_config(config_path)
    notify = config.get('General-Section', 'notify-index')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    ietf_draft_url = config.get('Web-Section', 'ietf-draft-private-url')
    ietf_rfc_url = config.get('Web-Section', 'ietf-RFC-tar-private-url')
    temp_dir = config.get('Directory-Section', 'temp')
    LOGGER = log.get_logger('draftPullLocal', '{}/jobs/draft-pull-local.log'.format(log_directory))
    LOGGER.info('Starting cron job IETF pull request local')

    messages = []
    notify = True if notify == 'True' else False
    populate_error = False
    repo = None
    try:
        # Clone YangModels/yang repository
        clone_dir = '{}/draftpulllocal'.format(temp_dir)
        if os.path.exists(clone_dir):
            shutil.rmtree(clone_dir)
        repo = repoutil.RepoUtil('https://github.com/YangModels/yang.git')
        repo.clone(config_name, config_email, clone_dir)
        LOGGER.info('YangModels/yang repo cloned to local directory {}'.format(repo.localdir))

        response = requests.get(ietf_rfc_url)
        tgz_path = '{}/rfc.tgz'.format(repo.localdir)
        extract_to = '{}/standard/ietf/RFC'.format(repo.localdir)
        with open(tgz_path, 'wb') as zfile:
            zfile.write(response.content)
        tar_opened = extract_rfc_tgz(tgz_path, extract_to, LOGGER)

        if tar_opened:
            # Standard RFC modules
            direc = '{}/standard/ietf/RFC'.format(repo.localdir)

            LOGGER.info('Checking module filenames without revision in {}'.format(direc))
            check_name_no_revision_exist(direc, LOGGER)

            LOGGER.info('Checking for early revision in {}'.format(direc))
            check_early_revisions(direc, LOGGER)

            execution_result = run_populate_script(direc, notify, LOGGER)
            if execution_result == False:
                populate_error = True
                message = {'label': 'Standard RFC modules', 'message': 'Error while calling populate script'}
                messages.append(message)
            else:
                message = {'label': 'Standard RFC modules', 'message': 'populate script finished successfully'}
                messages.append(message)

        # Experimental modules
        experimental_path = '{}/experimental/ietf-extracted-YANG-modules'.format(repo.localdir)

        LOGGER.info('Updating IETF drafts download links')
        get_draft_module_content(ietf_draft_url, experimental_path, LOGGER)

        LOGGER.info('Checking module filenames without revision in {}'.format(experimental_path))
        check_name_no_revision_exist(experimental_path, LOGGER)

        LOGGER.info('Checking for early revision in {}'.format(experimental_path))
        check_early_revisions(experimental_path, LOGGER)

        execution_result = run_populate_script(experimental_path, notify, LOGGER)
        if execution_result == False:
            populate_error = True
            message = {'label': 'Experimental modules', 'message': 'Error while calling populate script'}
            messages.append(message)
        else:
            message = {'label': 'Experimental modules', 'message': 'populate script finished successfully'}
            messages.append(message)
    except Exception as e:
        LOGGER.exception('Exception found while running draftPullLocal script')
        job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
        repo.remove()
        raise e
    repo.remove()
    if not populate_error:
        LOGGER.info('Job finished successfully')
    else:
        LOGGER.info('Job finished, but errors found while calling populate script')
    job_log(start_time, temp_dir, messages=messages, status='Success', filename=os.path.basename(__file__))


if __name__ == "__main__":
    main()
