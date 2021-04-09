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
Cronjob tool that automatically pushes new ietf
draft yang modules to github repository old ones
are removed and naming is corrected to
<name>@<revision>.yang. New ietf RFC modules are
checked too but they are not automatically added.
E-mail is sent to yangcatalog admin users if such
thing occurs. Message about new RFC or DRAFT modules
is also sent to Cisco webex teams yangcatalog admin
room
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
import warnings

import requests
import utility.log as log
from git.exc import GitCommandError
from travispy import TravisPy
from travispy.errors import TravisError
from utility import messageFactory, repoutil
from utility.util import job_log

from ietfYangDraftPull.draftPullUtility import (check_early_revisions,
                                                check_name_no_revision_exist,
                                                extract_rfc_tgz,
                                                get_draft_module_content)

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


class ScriptConfig:

    def __init__(self):
        parser = argparse.ArgumentParser()
        self.help = 'Pull the latest ietf files and add them to github if there are any new ietf draf files. If there' \
                    'are new RFC files it will produce automated message that will be sent to webex teams and admin' \
                    ' emails notifying you that these need to be added to yangModels/yang github manualy. This runs as ' \
                    'a daily cronjob'
        parser.add_argument('--config-path', type=str,
                            default='/etc/yangcatalog/yangcatalog.conf',
                            help='Set path to config file')
        parser.add_argument('--send-message', action='store_true', default=False, help='Whether to send notification'
                            ' to cisco webex teams and to emails')
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
        ret['options']['send_message'] = 'Whether to send notification to cisco webex teams and to emails'
        return ret


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args

    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    token = config.get('Secrets-Section', 'yang-catalog-token')
    username = config.get('General-Section', 'repository-username')
    commit_dir = config.get('Directory-Section', 'commit-dir')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    temp_dir = config.get('Directory-Section', 'temp')
    exceptions = config.get('Directory-Section', 'exceptions')
    ietf_models_forked_url = config.get('Web-Section', 'yang-models-forked-repo-url')
    ietf_models_url_suffix = config.get('Web-Section', 'yang-models-repo-url-suffix')
    ietf_draft_url = config.get('Web-Section', 'ietf-draft-private-url')
    ietf_rfc_url = config.get('Web-Section', 'ietf-RFC-tar-private-url')
    LOGGER = log.get_logger('draftPull', '{}/jobs/draft-pull.log'.format(log_directory))
    LOGGER.info('Starting Cron job IETF pull request')
    github_credentials = ''
    if len(username) > 0:
        github_credentials = '{}:{}@'.format(username, token)

    token_header_value = 'token {}'.format(token)
    # Remove old fork
    requests.delete('{}yang'.format(ietf_models_forked_url), headers={'Authorization': token_header_value})
    time.sleep(20)

    # Fork YangModels/yang repository
    LOGGER.info('Cloning repository')
    response = requests.post('https://{}{}'.format(github_credentials, ietf_models_url_suffix))
    repo_name = response.json()['name']
    repo = None
    try:
        # Try to clone YangModels/yang repo
        retry = 3
        while True:
            try:
                repourl = 'https://{}@github.com/{}/{}.git'.format(token, username, repo_name)
                repo = repoutil.RepoUtil(repourl)
                LOGGER.info(repourl)
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

        # Try to activate Travis CI
        retry = 3
        while True:
            try:
                LOGGER.info('Activating Travis')
                travis = TravisPy.github_auth(token)
                break
            except:
                retry -= 1
                LOGGER.warning('Travis CI not ready yet')
                time.sleep(10)
                if retry == 0:
                    LOGGER.exception('Activating Travis - Failed')
                    LOGGER.info('Removing local directory and deleting forked repository')
                    requests.delete('{}{}'.format(ietf_models_forked_url, repo_name),
                                    headers={'Authorization': token_header_value})
                    repo.remove()
                    e = 'Failed to activate Travis'
                    job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
                    sys.exit(500)

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

            for root, subdirs, sdos in os.walk('{}/standard/ietf/RFCtemp'.format(repo.localdir)):
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
            # Get user and sync
            with warnings.catch_warnings(record=True):
                travis_user = travis.user()
            LOGGER.info('Syncing repo user for Travis')
            response = travis_user.sync()
            travis_repo = travis.repo('{}/{}'.format(username, repo_name))
            LOGGER.info('Enabling repo for Travis')
            travis_repo.enable()  # Switch is now on
            travis_enabled_retry = 5
            while not travis_repo.active:
                LOGGER.warning('Travis repo not enabled retrying')
                time.sleep(3)
                travis_enabled_retry -= 1
                travis_repo.enable()
                if travis_enabled_retry == 0:
                    raise Exception()
            # Add commit and push to the forked repository
            LOGGER.info('Adding all untracked files locally')
            repo.add_all_untracked()
            LOGGER.info('Committing all files locally')
            repo.commit_all('Cronjob - every day pull of ietf draft yang files.')
            LOGGER.info('Pushing files to forked repository')
            commit_hash = repo.repo.head.commit
            LOGGER.info('Commit hash {}'.format(commit_hash))
            with open(commit_dir, 'w+') as f:
                f.write('{}\n'.format(commit_hash))
            repo.push()
        except TravisError as e:
            LOGGER.exception('Error while pushing procedure - Travis error')
            requests.delete('{}{}'.format(ietf_models_forked_url, repo_name),
                            headers={'Authorization': token_header_value})
            raise e
        except GitCommandError as e:
            message = 'Error while pushing procedure - git command error: \n {} \n git command out: \n {}'.format(e.stderr, e.stdout)
            requests.delete('{}{}'.format(ietf_models_forked_url, repo_name),
                            headers={'Authorization': token_header_value})
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
            requests.delete('{}{}'.format(ietf_models_forked_url, repo_name),
                            headers={'Authorization': token_header_value})
            raise type(e)('Error while pushing procedure')
    except Exception as e:
        LOGGER.exception('Exception found while running draftPull script')
        job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
        requests.delete('{}{}'.format(ietf_models_forked_url, repo_name), headers={'Authorization': token_header_value})
        repo.remove()
        raise e
    # Remove tmp folder
    LOGGER.info('Removing tmp directory')
    repo.remove()
    # we can not remove forked repository here since there could be new modules added
    if len(messages) == 0:
        messages = [
            {'label': 'Pull request created', 'message': 'True - {}'.format(commit_hash)}
        ]
    job_log(start_time, temp_dir, messages=messages, status='Success', filename=os.path.basename(__file__))
    LOGGER.info('Job finished successfully')


if __name__ == "__main__":
    main()
