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
This module contains functionality for pushing new/updated modules extracted from RFCs in the:
https://github.com/yang-catalog/yang/ repo. There are also modules which won't be pushed into the repository,
they are stored in the /var/yang/ietf-exceptions/exceptions.dat and /var/yang/ietf-exceptions/iana-exceptions.dat files.
"""


__author__ = 'Bohdan Konovalenko'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bohdan.konovalenko@bluefield.tech'

import logging
import os
import shutil
from configparser import ConfigParser
from dataclasses import dataclass

from utility.create_config import create_config
from utility.repoutil import ModifiableRepoUtil


@dataclass
class RFCsPushResult:
    push_successful: bool
    message: str


def push_new_rfcs(
    new_files: list[str],
    diff_files: list[str],
    forked_repo: ModifiableRepoUtil,
    logger: logging.Logger,
    config: ConfigParser = create_config(),
) -> RFCsPushResult:
    if not new_files and not diff_files:
        return RFCsPushResult(False, 'No files to update')
    commit_dir = config.get('Directory-Section', 'commit-dir')
    try:
        _update_files_locally(new_files, diff_files, forked_repo, config)
        if not forked_repo.repo.index.diff(None):
            return RFCsPushResult(False, 'No changed files found locally')
        is_prod = config.get('General-Section', 'is-prod') == 'True'
        if not is_prod:
            forked_repo.repo.git.reset('--hard')
            return RFCsPushResult(
                True,
                'Push is successful (switch to the PROD environment to actually push changes to the repo)',
            )
        forked_repo.repo.git.add(all=True)
        forked_repo.commit_all(message='Add new IETF RFC files')
        forked_repo.repo.git.push('--set-upstream', 'origin', forked_repo.repo.active_branch)
        with open(commit_dir, 'w') as f:
            f.write(f'{forked_repo.repo.head.commit}\n')
        logger.info(
            f'new/diff modules are pushed into {forked_repo.repo.active_branch} branch, '
            f'commit hash: {forked_repo.repo.head.commit}',
        )
        return RFCsPushResult(
            True,
            f'Files are pushed in the {forked_repo.repo.active_branch} branch, '
            f'PullRequest should be created after the successful run of GitHub Actions, '
            f'or updated if there\'s already an existing one',
        )
    except Exception as e:
        logger.exception('Unexpected error occurred during an automatic PullRequest creation')
        return RFCsPushResult(False, f'Unexpected error\n{e}')


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
