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
from xym import xym

from utility.create_config import create_config
from utility.repoutil import ModifiableRepoUtil


@dataclass
class PullRequestCreationResult:
    pr_created: bool
    message: str


def create_new_rfcs_pull_request(
    files_to_update: list[str],
    forked_repo: ModifiableRepoUtil,
    logger: logging.Logger,
    config: ConfigParser = create_config(),
) -> PullRequestCreationResult:
    if not files_to_update:
        return PullRequestCreationResult(False, 'No files to update')
    token = config.get('Secrets-Section', 'yang-catalog-token')
    username = config.get('General-Section', 'repository-username')
    repo_previous_active_branch = forked_repo.repo.active_branch
    try:
        forked_repo.repo.git.checkout('HEAD', b=datetime.now().strftime('%Y_%m_%d_%H_%M_%S'))
        _extract_modules(files_to_update, forked_repo, config)
        if not forked_repo.repo.untracked_files:
            forked_repo.repo.git.checkout(repo_previous_active_branch)
            return PullRequestCreationResult(False, 'No files to update after extraction')
        result = _create_pull_request(forked_repo, username, token, logger, config)
        forked_repo.repo.git.checkout(repo_previous_active_branch)
        return result
    except Exception as e:
        logger.exception('Unexpected error occurred during an automatic PullRequest creation')
        forked_repo.repo.git.checkout(repo_previous_active_branch)
        return PullRequestCreationResult(False, f'Unexpected error\n{e}')


def _extract_modules(files_to_update: list[str], repo: ModifiableRepoUtil, config: ConfigParser):
    private_dir = config.get('Web-Section', 'private-directory')
    extract_to = os.path.join(repo.local_dir, 'standard/ietf/RFCtemp')
    rfc_directory = os.path.join(repo.local_dir, 'standard/ietf/RFC')
    if os.path.exists(extract_to):
        shutil.rmtree(extract_to)
    os.makedirs(extract_to)
    with open(os.path.join(private_dir, 'IETFYANGRFC.json'), 'r') as f:
        rfcs_dict = json.load(f)
    extracted_rfcs = set()
    cwd = os.getcwd()
    os.chdir(rfc_directory)
    for filename in files_to_update:
        rfc_url = rfcs_dict.get(filename)
        if not rfc_url:
            continue
        try:
            rfc_url = rfc_url.split('<a href=\"')[1].split('\">')[0]
        except IndexError:
            continue
        if rfc_url not in extracted_rfcs:
            xym.xym(source_id=rfc_url, srcdir='', dstdir=extract_to)
            extracted_rfcs.add(rfc_url)
        filename_without_revision = f'{filename.split("@")[0]}.yang'
        extracted_file_path = os.path.join(extract_to, filename_without_revision)
        if not os.path.exists(extracted_file_path):
            continue
        shutil.copy2(extracted_file_path, filename)
        if os.path.islink(filename_without_revision):
            os.unlink(filename_without_revision)
        os.symlink(filename, filename_without_revision)
    os.chdir(cwd)
    shutil.rmtree(extract_to)


def _create_pull_request(
    forked_repo: ModifiableRepoUtil,
    username: str,
    token: str,
    logger: logging.Logger,
    config: ConfigParser,
) -> PullRequestCreationResult:
    is_prod = config.get('General-Section', 'is-prod') == 'True'
    forked_repo.repo.git.add(all=True)
    forked_repo.commit_all(message='Add new IETF RFC files')
    if not is_prod:
        return PullRequestCreationResult(
            True,
            'PullRequest creation is successful (switch to the PROD environment to actually create one)',
        )
    forked_repo.repo.git.push('--set-upstream', 'origin', forked_repo.repo.active_branch)
    data = {
        'title': 'Add new IETF RFC files',
        'head': f'{username}:{forked_repo.repo.active_branch}',
        'base': 'main',
    }
    response = requests.post(
        'https://api.github.com/repos/YangModels/yang/pulls',
        headers={'Authorization': f'token {token}', 'Content-Type': 'application/vnd.github+json'},
        data=json.dumps(data),
    )
    message = response.json()['html_url'] if response.ok else response.text
    logger.info(f'Automatic PullRequest creation info: {message}')
    return PullRequestCreationResult(response.ok, message)
