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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import errno
import filecmp
import os
import shutil
import sys
import time

import requests
import utility.log as log
from git.exc import GitCommandError
from utility import messageFactory, repoutil
from utility.create_config import create_config
from utility.util import job_log

from ietfYangDraftPull.draftPullUtility import (check_early_revisions,
                                                check_name_no_revision_exist,
                                                extract_rfc_tgz,
                                                get_draft_module_content)


class ScriptConfig:

    def __init__(self):
        parser = argparse.ArgumentParser()
        self.help = 'Pull the latest IETF files and add them to the Github if there are any new IETF draft files.' \
                    'If there are new RFC files it will produce automated message that will be sent to the ' \
                    'Cisco Webex Teams and admin emails notifying you that these need to be added to YangModels/yang ' \
                    'Github repository manualy. This script runs as a daily cronjob.'
        parser.add_argument('--config-path', type=str,
                            default=os.environ['YANGCATALOG_CONFIG_PATH'],
                            help='Set path to config file')
        parser.add_argument('--send-message', action='store_true', default=False, help='Whether to send notification'
                            ' to Cisco Webex Teams and to emails')
        self.args, _ = parser.parse_known_args()
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
        ret['options']['send_message'] = 'Whether to send notification to cisco webex teams and to emails'
        return ret


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
    exceptions = config.get('Directory-Section', 'exceptions')
    yang_models = config.get('Directory-Section', 'yang-models-dir')
    ietf_draft_url = config.get('Web-Section', 'ietf-draft-private-url')
    ietf_rfc_url = config.get('Web-Section', 'ietf-RFC-tar-private-url')
    is_production = config.get('General-Section', 'is-prod')
    is_production = True if is_production == 'True' else False
    LOGGER = log.get_logger('draftPull', '{}/jobs/draft-pull.log'.format(log_directory))
    LOGGER.info('Starting Cron job IETF pull request')

    # Check whether fork repository is up-to-date
    try:
        main_repo = repoutil.load(yang_models, 'https://github.com/YangModels/yang.git')
        origin = main_repo.repo.remote('origin')
        fork = main_repo.repo.remote('fork')

        # git fetch --all
        for remote in main_repo.repo.remotes:
            info = remote.fetch('master')[0]
            LOGGER.info('Remote: {} - Commit: {}'.format(remote.name, info.commit))

        # git pull origin master
        pull_info = origin.pull('master')[0]

        # git push fork master
        push_info = fork.push('master')[0]
        LOGGER.info('Push info: {}'.format(push_info.summary))
        if 'non-fast-forward' in push_info.summary:
            LOGGER.warning('yang-catalog/yang repo might not be up-to-date')
    except:
        LOGGER.warning('yang-catalog/yang repo might not be up-to-date')

    repo_name = 'yang'
    try:
        # Try to clone yang-catalog/yang repo
        retry = 3
        while True:
            try:
                repourl = 'https://{}@github.com/{}/{}.git'.format(token, username, repo_name)
                repo = repoutil.RepoUtil(repourl)
                LOGGER.info('Cloning repository from: {}'.format(repourl))
                repo.clone(config_name, config_email)
                break
            except Exception as e:
                retry -= 1
                LOGGER.warning('Repository not ready yet')
                time.sleep(10)
                if retry == 0:
                    LOGGER.exception('Failed to clone repository {}'.format(repo_name))
                    job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
                    raise Exception()
        LOGGER.info('Repository cloned to local directory {}'.format(repo.localdir))

        # Get rfc.tgz file
        response = requests.get(ietf_rfc_url)
        tgz_path = '{}/rfc.tgz'.format(repo.localdir)
        extract_to = '{}/standard/ietf/RFCtemp'.format(repo.localdir)
        with open(tgz_path, 'wb') as zfile:
            zfile.write(response.content)
        tar_opened = extract_rfc_tgz(tgz_path, extract_to, LOGGER)
        if tar_opened:
            diff_files = []
            new_files = []

            for root, _, sdos in os.walk('{}/standard/ietf/RFCtemp'.format(repo.localdir)):
                for file_name in sdos:
                    if '.yang' in file_name:
                        if os.path.exists('{}/standard/ietf/RFC/{}'.format(repo.localdir, file_name)):
                            same = filecmp.cmp(
                                '{}/standard/ietf/RFC/{}'.format(repo.localdir, file_name),
                                '{}/{}'.format(root, file_name))
                            if not same:
                                diff_files.append(file_name)
                        else:
                            new_files.append(file_name)
            shutil.rmtree('{}/standard/ietf/RFCtemp'.format(repo.localdir))

            with open(exceptions, 'r') as exceptions_file:
                remove_from_new = exceptions_file.read().split('\n')
            for remove in remove_from_new:
                if remove in new_files:
                    new_files.remove(remove)

            if args.send_message:
                if len(new_files) > 0 or len(diff_files) > 0:
                    LOGGER.warning('new or modified RFC files found. Sending an E-mail')
                    mf = messageFactory.MessageFactory()
                    mf.send_new_rfc_message(new_files, diff_files)

        # Experimental draft modules
        try:
            os.makedirs('{}/experimental/ietf-extracted-YANG-modules/'.format(repo.localdir))
        except OSError as e:
            # be happy if someone already created the path
            if e.errno != errno.EEXIST:
                raise
        experimental_path = '{}/experimental/ietf-extracted-YANG-modules'.format(repo.localdir)

        LOGGER.info('Updating IETF drafts download links')
        get_draft_module_content(ietf_draft_url, experimental_path, LOGGER)

        LOGGER.info('Checking module filenames without revision in {}'.format(experimental_path))
        check_name_no_revision_exist(experimental_path, LOGGER)

        LOGGER.info('Checking for early revision in {}'.format(experimental_path))
        check_early_revisions(experimental_path, LOGGER)

        messages = []
        try:
            # Add commit and push to the forked repository
            LOGGER.info('Adding all untracked files locally')
            untracked_files = repo.repo.untracked_files
            repo.add_all_untracked()
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
        repo.remove()
        raise e
    # Remove tmp folder
    LOGGER.info('Removing tmp directory')
    repo.remove()

    if len(messages) == 0:
        messages = [
            {'label': 'Pull request created', 'message': 'True - {}'.format(commit_hash)}
        ]
    job_log(start_time, temp_dir, messages=messages, status='Success', filename=os.path.basename(__file__))
    LOGGER.info('Job finished successfully')


if __name__ == "__main__":
    main()
