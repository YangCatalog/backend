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
Pull the latest IETF files and add any new IETF draft files to GitHub.
Remove old files and ensure all filenames have a <name>@<revision>.yang format.
If there are new RFC files, produce an automated message that will be sent to the
Cisco Webex Teams and admin emails notifying that these need to be added to
the YangModels/yang GitHub repository manually. This script runs as a daily cronjob.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import filecmp
import glob
import os
import shutil
import sys

import requests
from git.exc import GitCommandError

import utility.log as log
from ietfYangDraftPull import draftPullUtility as dpu
from utility import message_factory
from utility.create_config import create_config
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.util import job_log

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME]['args'],
    arglist=None if __name__ == '__main__' else [],
)


@job_log(file_basename=BASENAME)
def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()) -> list[dict[str, str]]:
    args = script_conf.args
    config_path = args.config_path
    config = create_config(config_path)
    token = config.get('Secrets-Section', 'yang-catalog-token')
    username = config.get('General-Section', 'repository-username')
    commit_dir = config.get('Directory-Section', 'commit-dir')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    rfc_exceptions = config.get('Directory-Section', 'rfc-exceptions')
    yang_models = config.get('Directory-Section', 'yang-models-dir')
    ietf_rfc_url = config.get('Web-Section', 'ietf-RFC-tar-private-url')
    is_production = config.get('General-Section', 'is-prod')
    is_production = is_production == 'True'
    logger = log.get_logger('draftPull', f'{log_directory}/jobs/draft-pull.log')
    logger.info('Starting Cron job IETF pull request')

    repo_name = 'yang'
    commit_author = {'name': config_name, 'email': config_email}

    github_repo_url = dpu.construct_github_repo_url(username, repo_name, token)
    dpu.update_forked_repository(yang_models, github_repo_url, logger)
    repo = dpu.clone_forked_repository(github_repo_url, commit_author, logger)

    if not repo:
        raise RuntimeError(f'Failed to clone repository {username}/{repo_name}')

    try:
        # Get rfc.tgz file
        response = requests.get(ietf_rfc_url)
        tgz_path = os.path.join(repo.local_dir, 'rfc.tgz')
        extract_to = os.path.join(repo.local_dir, 'standard/ietf/RFCtemp')
        with open(tgz_path, 'wb') as zfile:
            zfile.write(response.content)
        tar_opened = dpu.extract_rfc_tgz(tgz_path, extract_to, logger)
        if tar_opened:
            diff_files = []
            new_files = []
            temp_rfc_yang_files = glob.glob(f'{extract_to}/*.yang')
            for temp_rfc_yang_file in temp_rfc_yang_files:
                file_name = os.path.basename(temp_rfc_yang_file)
                rfc_yang_file = temp_rfc_yang_file.replace('RFCtemp', 'RFC')

                if not os.path.exists(rfc_yang_file):
                    new_files.append(file_name)
                    continue

                files_are_identical = filecmp.cmp(rfc_yang_file, temp_rfc_yang_file)
                if not files_are_identical:
                    diff_files.append(file_name)

            shutil.rmtree(extract_to)

            try:
                with open(rfc_exceptions, 'r') as exceptions_file:
                    remove_from_new = exceptions_file.read().split('\n')
            except FileNotFoundError:
                open(rfc_exceptions, 'w').close()
                os.chmod(rfc_exceptions, 0o664)
                remove_from_new = []
            new_files = [file_name for file_name in new_files if file_name not in remove_from_new]

            if args.send_message and (new_files or diff_files):
                logger.info('new or modified RFC files found. Sending an E-mail')
                mf = message_factory.MessageFactory()
                mf.send_new_rfc_message(new_files, diff_files)

        # Experimental draft modules
        experimental_path = os.path.join(repo.local_dir, 'experimental/ietf-extracted-YANG-modules')
        os.makedirs(experimental_path, exist_ok=True)

        logger.info('Updating IETF drafts download links')
        dpu.get_draft_module_content(experimental_path, config, logger)

        logger.info(f'Checking module filenames without revision in {experimental_path}')
        dpu.check_name_no_revision_exist(experimental_path, logger)

        logger.info(f'Checking for early revision in {experimental_path}')
        dpu.check_early_revisions(experimental_path, logger)

        messages = []
        try:
            # Add commit and push to the forked repository
            logger.info('Adding all untracked files locally')
            untracked_files = repo.repo.untracked_files
            repo.add_untracked_remove_deleted()
            logger.info('Committing all files locally')
            repo.commit_all('Cronjob - every day pull of ietf draft yang files.')
            logger.info('Pushing files to forked repository')
            commit_hash = repo.repo.head.commit
            logger.info(f'Commit hash {commit_hash}')
            with open(commit_dir, 'w+') as f:
                f.write(f'{commit_hash}\n')
            if is_production:
                logger.info('Pushing untracked and modified files to remote repository')
                repo.push()
            else:
                logger.info('DEV environment - not pushing changes into remote repository')
                untracked_files_list = '\n'.join(untracked_files)
                logger.debug(f'List of all untracked and modified files:\n{untracked_files_list}')
        except GitCommandError as e:
            message = (
                f'Error while pushing procedure - git command error: \n {e.stderr} \n git command out: \n {e.stdout}'
            )
            if 'Your branch is up to date' in e.stdout:
                logger.warning(message)
                messages = [{'label': 'Pull request created', 'message': 'False - branch is up to date'}]
            else:
                logger.exception('Error while pushing procedure - Git command error')
                raise e
        except Exception as e:
            logger.exception(f'Error while pushing procedure {sys.exc_info()[0]}')
            raise type(e)('Error while pushing procedure')
    except Exception as e:
        logger.exception('Exception found while running draftPull script')
        raise e

    logger.info('Job finished successfully')
    if len(messages) == 0:
        messages = [{'label': 'Pull request created', 'message': f'True - {commit_hash}'}]  # pyright: ignore
    return messages


if __name__ == '__main__':
    main()
