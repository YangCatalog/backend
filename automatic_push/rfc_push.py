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
This module contains functionality for creating a PullRequest to the: https://github.com/YangModels/yang/ repo
with new/updated modules from RFCs. There are also modules which won't be pushed into the repository,
they are stored in the /var/yang/ietf-exceptions/exceptions.dat and /var/yang/ietf-exceptions/iana-exceptions.dat files.
"""


__author__ = 'Bohdan Konovalenko'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bohdan.konovalenko@bluefield.tech'

import json
import logging
import os
import shutil
from configparser import ConfigParser
from dataclasses import dataclass
from datetime import datetime

import requests
from git import GitError

from utility.create_config import create_config
from utility.repoutil import ModifiableRepoUtil, create_pull_request


@dataclass
class PullRequestCreationResult:
    pr_created: bool
    message: str


def create_new_rfcs_pull_request(
    new_files: list[str],
    diff_files: list[str],
    forked_repo: ModifiableRepoUtil,
    logger: logging.Logger,
    config: ConfigParser = create_config(),
) -> PullRequestCreationResult:
    if not new_files and not diff_files:
        return PullRequestCreationResult(False, 'No files to update')
    token = config.get('Secrets-Section', 'yang-catalog-token')
    username = config.get('General-Section', 'repository-username')
    try:
        forked_repo.checkout(datetime.now().strftime('%Y_%m_%d_%H_%M_%S'), new_branch=True)
    except GitError:
        logger.exception('New branch creation failed')
        return PullRequestCreationResult(False, 'New branch couldn\'t be created')
    try:
        _update_files_locally(new_files, diff_files, forked_repo, config)
        if not forked_repo.repo.index.diff(None):
            return PullRequestCreationResult(False, 'No changed files found locally')
        result = _create_pull_request(forked_repo, username, token, logger, config)
        forked_repo.checkout(forked_repo.previous_active_branch)
        return result
    except Exception as e:
        forked_repo.checkout(forked_repo.previous_active_branch)
        logger.exception('Unexpected error occurred during an automatic PullRequest creation')
        return PullRequestCreationResult(False, f'Unexpected error\n{e}')


def _update_files_locally(new_files: list[str], diff_files: list[str], repo: ModifiableRepoUtil, config: ConfigParser):
    ietf_directory = config.get('Directory-Section', 'ietf-directory')
    rfc_directory = os.path.join(ietf_directory, 'YANG-rfc')
    copy_to = os.path.join(repo.local_dir, 'standard/ietf/RFC')
    cwd = os.getcwd()
    os.chdir(copy_to)
    for filename in new_files + diff_files:
        file_path = os.path.join(rfc_directory, filename)
        filename_without_revision = f'{filename.split("@")[0]}.yang'
        if not os.path.exists(file_path):
            continue
        shutil.copy2(file_path, filename)
        if filename not in new_files:
            continue
        if os.path.islink(filename_without_revision):
            os.unlink(filename_without_revision)
        os.symlink(filename, filename_without_revision)
    os.chdir(cwd)


def _create_pull_request(
    forked_repo: ModifiableRepoUtil,
    username: str,
    token: str,
    logger: logging.Logger,
    config: ConfigParser,
) -> PullRequestCreationResult:
    is_prod = config.get('General-Section', 'is-prod') == 'True'
    if not is_prod:
        forked_repo.repo.git.reset('--hard')
        return PullRequestCreationResult(
            True,
            'PullRequest creation is successful (switch to the PROD environment to actually create one)',
        )
    pr_title = 'Add new IETF RFC files'
    open_pr_response = requests.get(
        'https://api.github.com/repos/YangModels/yang/pulls',
        headers={'Authorization': f'token {token}', 'Content-Type': 'application/vnd.github+json'},
        data=json.dumps({'state': 'open', 'head': 'yang-catalog'}),
    )
    for pr in open_pr_response.json():
        if pr['title'] == pr_title:
            forked_repo.repo.git.reset('--hard')
            return PullRequestCreationResult(False, f'There is already an open PullRequest: {pr["html_url"]}')
    forked_repo.repo.git.add(all=True)
    forked_repo.commit_all(message='Add new IETF RFC files')
    forked_repo.repo.git.push('--set-upstream', 'origin', forked_repo.repo.active_branch)
    response = create_pull_request(
        'YangModels',
        'yang',
        f'{username}:{forked_repo.repo.active_branch}',
        'main',
        {'Authorization': f'token {token}'},
        title=pr_title,
    )
    message = response.json()['html_url'] if response.ok else response.text
    logger.info(f'Automatic PullRequest creation info: {message}')
    return PullRequestCreationResult(response.ok, message)
