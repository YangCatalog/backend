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
Cronjob tool that automatically pushes new IETF
draft yang modules to the Github repository. Old ones
are removed and naming is corrected to <name>@<revision>.yang.
New IETF RFC modules are checked too, but they are not automatically added.
E-mail is sent to yangcatalog admin users if such thing occurs.
Message about new RFC or DRAFT yang modules is also sent
to the Cisco Webex Teams, room: YANG Catalog Admin.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import errno
import filecmp
import glob
import os
import shutil
import sys
import time
import typing as t

import requests
import utility.log as log
from git.exc import GitCommandError
from utility import messageFactory
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.util import job_log

from ietfYangDraftPull import draftPullUtility


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'Pull the latest IETF files and add any new IETF draft files to Github.' \
               'If there are new RFC files, produce an automated message that will be sent to the ' \
               'Cisco Webex Teams and admin emails notifying that these need to be added to ' \
               'the YangModels/yang Github repository manualy. This script runs as a daily cronjob.'
        args: t.List[Arg] = [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH']
            },
            {
                'flag': '--send-message',
                'help': 'Whether to send a notification',
                'action': 'store_true',
                'default': False
            }
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args

    config_path = args.config_path
    config = create_config(config_path)
    token = config.get('Secrets-Section', 'yang-catalog-token')
    username = config.get('General-Section', 'repository-username')
    commit_dir = config.get('Directory-Section', 'commit-dir')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    temp_dir = config.get('Directory-Section', 'temp')
    rfc_exceptions = config.get('Directory-Section', 'rfc-exceptions')
    yang_models = config.get('Directory-Section', 'yang-models-dir')
    ietf_draft_url = config.get('Web-Section', 'ietf-draft-private-url')
    ietf_rfc_url = config.get('Web-Section', 'ietf-RFC-tar-private-url')
    is_production = config.get('General-Section', 'is-prod')
    is_production = is_production == 'True'
    LOGGER = log.get_logger('draftPull', '{}/jobs/draft-pull.log'.format(log_directory))
    LOGGER.info('Starting Cron job IETF pull request')

    repo_name = 'yang'
    repourl = 'https://{}@github.com/{}/{}.git'.format(token, username, repo_name)
    commit_author = {
        'name': config_name,
        'email': config_email
    }

    draftPullUtility.update_forked_repository(yang_models, LOGGER)
    repo = draftPullUtility.clone_forked_repository(repourl, commit_author, LOGGER)

    if not repo:
        error_message = 'Failed to clone repository {}/{}'.format(username, repo_name)
        job_log(start_time, temp_dir, error=error_message, status='Fail', filename=os.path.basename(__file__))
        sys.exit()

    try:
        # Get rfc.tgz file
        response = requests.get(ietf_rfc_url)
        tgz_path = '{}/rfc.tgz'.format(repo.local_dir)
        extract_to = '{}/standard/ietf/RFCtemp'.format(repo.local_dir)
        with open(tgz_path, 'wb') as zfile:
            zfile.write(response.content)
        tar_opened = draftPullUtility.extract_rfc_tgz(tgz_path, extract_to, LOGGER)
        if tar_opened:
            diff_files = []
            new_files = []

            temp_rfc_yang_files = glob.glob('{}/standard/ietf/RFCtemp/*.yang'.format(repo.local_dir))
            for temp_rfc_yang_file in temp_rfc_yang_files:
                file_name = os.path.basename(temp_rfc_yang_file)
                rfc_yang_file = temp_rfc_yang_file.replace('RFCtemp', 'RFC')

                if not os.path.exists(rfc_yang_file):
                    new_files.append(file_name)
                    continue

                same = filecmp.cmp(rfc_yang_file, temp_rfc_yang_file)
                if not same:
                    diff_files.append(file_name)

            shutil.rmtree('{}/standard/ietf/RFCtemp'.format(repo.local_dir))

            with open(rfc_exceptions, 'r') as exceptions_file:
                remove_from_new = exceptions_file.read().split('\n')
            new_files = [file_name for file_name in new_files if file_name not in remove_from_new]

            if args.send_message:
                if new_files or diff_files:
                    LOGGER.info('new or modified RFC files found. Sending an E-mail')
                    mf = messageFactory.MessageFactory()
                    mf.send_new_rfc_message(new_files, diff_files)

        # Experimental draft modules
        try:
            os.makedirs('{}/experimental/ietf-extracted-YANG-modules/'.format(repo.local_dir))
        except OSError as e:
            # be happy if someone already created the path
            if e.errno != errno.EEXIST:
                raise
        experimental_path = '{}/experimental/ietf-extracted-YANG-modules'.format(repo.local_dir)

        LOGGER.info('Updating IETF drafts download links')
        draftPullUtility.get_draft_module_content(ietf_draft_url, experimental_path, LOGGER)

        LOGGER.info('Checking module filenames without revision in {}'.format(experimental_path))
        draftPullUtility.check_name_no_revision_exist(experimental_path, LOGGER)

        LOGGER.info('Checking for early revision in {}'.format(experimental_path))
        draftPullUtility.check_early_revisions(experimental_path, LOGGER)

        messages = []
        try:
            # Add commit and push to the forked repository
            LOGGER.info('Adding all untracked files locally')
            untracked_files = repo.repo.untracked_files
            repo.add_untracked_remove_deleted()
            LOGGER.info('Committing all files locally')
            repo.commit_all('Cronjob - every day pull of ietf draft yang files.')
            LOGGER.info('Pushing files to forked repository')
            commit_hash = repo.repo.head.commit
            LOGGER.info('Commit hash {}'.format(commit_hash))
            with open(commit_dir, 'w+') as f:
                f.write('{}\n'.format(commit_hash))
            if is_production:
                LOGGER.info('Pushing untracked and modified files to remote repository')
                repo.push()
            else:
                LOGGER.info('DEV environment - not pushing changes into remote repository')
                LOGGER.debug('List of all untracked and modified files:\n{}'.format('\n'.join(untracked_files)))
        except GitCommandError as e:
            message = 'Error while pushing procedure - git command error: \n {} \n git command out: \n {}'.format(e.stderr, e.stdout)
            if 'Your branch is up to date' in e.stdout:
                LOGGER.warning(message)
                messages = [
                    {'label': 'Pull request created', 'message': 'False - branch is up to date'}
                ]
            else:
                LOGGER.exception('Error while pushing procedure - Git command error')
                raise e
        except Exception as e:
            LOGGER.exception(
                'Error while pushing procedure {}'.format(sys.exc_info()[0]))
            raise type(e)('Error while pushing procedure')
    except Exception as e:
        LOGGER.exception('Exception found while running draftPull script')
        job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
        raise e

    if len(messages) == 0:
        messages = [
            {'label': 'Pull request created', 'message': 'True - {}'.format(commit_hash)} # pyright: ignore
        ]
    job_log(start_time, temp_dir, messages=messages, status='Success', filename=os.path.basename(__file__))
    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
