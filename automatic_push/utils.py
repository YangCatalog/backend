# Copyright The IETF Trust 2023, All Rights Reserved
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
This module contains common functions used in the automatic_push directory.
"""

__author__ = 'Bohdan Konovalenko'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bohdan.konovalenko@pantheon.tech'

import json
import logging
import os
import sys
from configparser import ConfigParser

import requests
from git import GitCommandError

from utility import repoutil
from utility.staticVariables import github_url


def update_forked_repository(yang_models: str, forked_repo_url: str, logger: logging.Logger):
    """
    Check whether forked repository yang-catalog/yang is up-to-date with YangModels/yang repository.
    Push missing commits to the forked repository if any are missing.

    Arguments:
        :param yang_models      (str) path to the directory where YangModels/yang repo is cloned
        :param forked_repo_url  (str) url to the forked repository
        :param logger           (logging.Logger) formated logger with the specified name
    """
    try:
        main_repo = repoutil.load(yang_models, f'{github_url}/YangModels/yang.git')
        origin = main_repo.repo.remote('origin')
        try:
            fork = main_repo.repo.remote('fork')
        except ValueError:
            git_config_lock_file = os.path.join(yang_models, '.git', 'config.lock')
            if os.path.exists(git_config_lock_file):
                os.remove(git_config_lock_file)
            fork = main_repo.repo.create_remote('fork', forked_repo_url)
            os.mknod(git_config_lock_file)

        # git fetch --all
        for remote in main_repo.repo.remotes:
            info = remote.fetch('main')[0]
            logger.info(f'Remote: {remote.name} - Commit: {info.commit}')

        # git pull origin main
        origin.pull('main')

        # git push fork main
        push_info = fork.push('main')[0]
        logger.info(f'Push info: {push_info.summary}')
        if 'non-fast-forward' in push_info.summary:
            logger.warning('yang-catalog/yang repo might not be up-to-date')
    except GitCommandError:
        logger.exception('yang-catalog/yang repo might not be up-to-date')


def download_draft_modules_content(experimental_path: str, config: ConfigParser, logger: logging.Logger):
    """
    Loop through download links for each module found in IETFDraft.json and try to get their content.

    Arguments:
        :param experimental_path    (str) full path to the directory with cloned experimental modules
        :param config               (configparser.ConfigParser) instance of ConfigParser class
        :param logger               (logging.Logger) formated logger with the specified name
    """
    ietf_draft_url = config.get('Web-Section', 'ietf-draft-private-url')
    my_uri = config.get('Web-Section', 'my-uri')
    domain_prefix = config.get('Web-Section', 'domain-prefix')
    ietf_draft_json = {}
    response = requests.get(ietf_draft_url)
    try:
        ietf_draft_json = response.json()
    except json.decoder.JSONDecodeError:
        logger.error(f'Unable to get content of {os.path.basename(ietf_draft_url)} file')
    for key in ietf_draft_json:
        file_path = os.path.join(experimental_path, key)
        yang_download_link = ietf_draft_json[key]['compilation_metadata'][2].split('href="')[1].split('">Download')[0]
        yang_download_link = yang_download_link.replace(domain_prefix, my_uri)
        try:
            file_content_response = requests.get(yang_download_link)
        except ConnectionError:
            logger.error(f'Unable to retrieve content of: {key} - {yang_download_link}')
            continue
        if 'text/html' in file_content_response.headers['content-type']:
            logger.error(f'The content of "{key}" file is a broken html, download link: {yang_download_link}')
            if not os.path.exists(file_path):
                continue
            with open(file_path, 'r') as possibly_broken_module:
                lines = possibly_broken_module.readlines()
                module_is_broken = '<html>' in lines[1] and '</html>' in lines[-1]
            if module_is_broken:
                logger.info(f'Deleted the file because of broken content: {key} - {yang_download_link}')
                os.remove(file_path)
            continue
        with open(file_path, 'w') as yang_file:
            yang_file.write(file_content_response.text)


def push_untracked_files(
    repo: repoutil.ModifiableRepoUtil,
    commit_message: str,
    logger: logging.Logger,
    verified_commits_file_path: str,
    is_production: bool,
) -> list[dict[str, str]]:
    """
    Commits locally and pushes all the changes to the remote repository.

    Arguments:
          :param repo (ModifiableRepoUtil) Repository where to push changes.
          :param commit_message (str) New commit message.
          :param logger (logging.Logger) Logger instance to log information/exceptions.
          :param verified_commits_file_path (str) Path to file where our verified commits should be stored
          in order to verify commits in GitHub webhooks.
          :param is_production (bool) If set to False then files would only be committed and not pushed to the repo.
    :return (list[dict[str, str]]) Returns information about the push.
    """
    try:
        logger.info('Adding all untracked files locally')
        untracked_files = repo.repo.untracked_files
        repo.add_untracked_remove_deleted()
        logger.info('Committing all files locally')
        repo.commit_all(message=commit_message)
        logger.info('Pushing files to forked repository')
        commit_hash = repo.repo.head.commit
        logger.info(f'Commit hash {commit_hash}')
        with open(verified_commits_file_path, 'w') as f:
            f.write(f'{commit_hash}\n')
        if is_production:
            logger.info('Pushing untracked and modified files to remote repository')
            repo.push()
        else:
            logger.info('DEV environment - not pushing changes into remote repository')
            untracked_files_list = '\n'.join(untracked_files)
            logger.debug(f'List of all untracked and modified files:\n{untracked_files_list}')
    except GitCommandError as e:
        message = f'Error while pushing procedure - git command error: \n {e.stderr} \n git command out: \n {e.stdout}'
        if 'Your branch is up to date' in e.stdout:
            logger.warning(message)
            return [{'label': 'Push successful', 'message': 'False - branch is up to date'}]
        else:
            logger.exception('Error while pushing procedure - Git command error')
            raise e
    except Exception as e:
        logger.exception(f'Error while pushing procedure {sys.exc_info()[0]}')
        raise type(e)('Error while pushing procedure')
    return [{'label': 'Push successful', 'message': f'True - {commit_hash}'}]
