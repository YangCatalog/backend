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

import logging
import os
from configparser import ConfigParser

from git import GitCommandError

from utility import repoutil
from utility.staticVariables import github_url


def get_forked_repository(config: ConfigParser, logger: logging.Logger) -> repoutil.ModifiableRepoUtil:
    """
    Returns the ModifiableRepoUtil instance of the https://github.com/yang-catalog/yang repository
    updated with the respect to the origin repo: https://github.com/YangModels/yang
    """
    repo_name = 'yang'
    repo_token = config.get('Secrets-Section', 'yang-catalog-token')
    repo_owner = config.get('General-Section', 'repository-username')
    repo_config_name = config.get('General-Section', 'repo-config-name')
    repo_config_email = config.get('General-Section', 'repo-config-email')
    yang_models_dir = config.get('Directory-Section', 'yang-models-dir')
    repo_clone_options = repoutil.RepoUtil.CloneOptions(
        config_username=repo_config_name,
        config_user_email=repo_config_email,
        recurse_submodules=False,
    )
    github_repo_url = repoutil.construct_github_repo_url(repo_owner, repo_name, repo_token)
    update_forked_repository(yang_models_dir, github_repo_url, logger)
    repo = repoutil.clone_repo(github_repo_url, repo_clone_options, logger)
    if not repo:
        raise RuntimeError(f'Failed to clone repository {repo_owner}/{repo_name}')
    return repo


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
