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

__author__ = 'Bohdan Konovalenko, Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bohdan.konovalenko@pantheon.tech, slavomir.mazur@pantheon.tech'

import grp
import logging
import os
import pwd
import tarfile
from configparser import ConfigParser

from git import GitCommandError

from utility import repoutil, yangParser
from utility.staticVariables import github_url
from utility.util import revision_to_date


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


def get_latest_revision(path: str, logger: logging.Logger):
    """Search for the latest revision in yang file

    Arguments:
        :param path     (str) full path to the yang file
        :param logger   (logging.Logger) formated logger with the specified name
        :return         revision of the module at the given path
    """
    try:
        stmt = yangParser.parse(path)
        result = stmt.search_one('revision')
        assert result
        rev = result.arg
    except Exception:
        logger.warning(f'Cannot yangParser.parse {path}')
        rev = None  # In case of invalid YANG syntax, None is returned

    return rev


def check_name_no_revision_exist(directory: str, logger: logging.Logger) -> None:
    """
    This function checks the format of all the modules' filename. If it contains module with a filename without
    revision, we check if there is a module that has revision in its filename. If such module exists,
    then module with no revision in filename will be removed.

    Arguments:
        :param directory    (str) full path to directory with yang modules
        :param logger       (logging.Logger) formated logger with the specified name
    """
    logger.debug(f'Checking revision for directory: {directory}')
    for _, _, files in os.walk(directory):
        for basename in files:
            if '@' not in basename:
                continue
            yang_file_name = basename.split('@')[0] + '.yang'
            revision = basename.split('@')[1].split('.')[0]
            yang_file_path = os.path.join(directory, yang_file_name)
            exists = os.path.exists(yang_file_path)
            if not exists:
                continue
            compared_revision = get_latest_revision(os.path.abspath(yang_file_path), logger)
            if compared_revision is None:
                continue
            if revision == compared_revision:
                os.remove(yang_file_path)


def check_early_revisions(directory: str, logger: logging.Logger) -> None:
    """
    This function checks all modules revisions and keeps only
    ones that are the newest. If there are two modules with
    two different revisions, then the older one is removed.

    Arguments:
        :param directory    (str) full path to directory with yang modules
        :param logger       (logging.Logger) formated logger with the specified name
    """
    for filename in (filenames := os.listdir(directory)):
        module_name = _get_module_name(filename)  # Beware of some invalid file names such as '@2015-03-09.yang'
        if module_name == '':
            continue
        files_to_delete = []
        revisions = []
        for nested_filename in filenames:
            if _get_module_name(nested_filename) != module_name:
                continue
            nested_filename_revision_part = nested_filename.split(module_name)[1]
            if not _is_revision_part_valid(nested_filename_revision_part):
                continue
            files_to_delete.append(nested_filename)
            revision = nested_filename_revision_part.split('.')[0].replace('@', '')
            if revision == '':
                yang_file_path = os.path.join(directory, nested_filename)
                revision = get_latest_revision(os.path.abspath(yang_file_path), logger)
                if revision is None:
                    continue
            revision = revision_to_date(revision)
            if revision:
                revisions.append(revision)
                continue
            # Probably revision filename contained invalid characters such as alphanumeric characters
            logger.exception(f'Failed to process revision for {nested_filename}: (rev: {revision})')
            revisions.append(revision)
        if len(revisions) == 0:  # Single revision...
            continue
        # Keep the latest (max) revision and delete the rest
        latest = revisions.index(max(revisions))
        files_to_delete.remove(files_to_delete[latest])
        for file_to_delete in files_to_delete:
            if 'iana-if-type' in file_to_delete:
                break
            if os.path.exists((path := os.path.join(directory, file_to_delete))):
                os.remove(path)


def _get_module_name(filename: str) -> str:
    return filename.split('.yang')[0].split('@')[0]


def _is_revision_part_valid(revision_part: str) -> bool:
    return revision_part.startswith('.') or revision_part.startswith('@')


def extract_rfc_tgz(tgz_path: str, extract_to: str, logger: logging.Logger) -> bool:
    """
    Extract downloaded rfc.tgz file to directory and remove file.

    Arguments:
        :param tgz_path     (str) full path to the rfc.tgz file
        :param extract_to   (str) path to the directory where rfc.tgz is extractracted to
        :param logger       (logging.Logger) formated logger with the specified name
    :return  (bool) Indicates if the tar archive was opened or not
    """
    try:
        tgz = tarfile.open(tgz_path)
        tar_opened = True
        tgz.extractall(extract_to)
        tgz.close()
    except tarfile.ReadError:
        tar_opened = False
        logger.warning(
            'Tarfile could not be opened. It might not have been generated yet. '
            'Did the module-compilation cron job run already?',
        )
    os.remove(tgz_path)

    return tar_opened


def set_permissions(directory: str):
    """
    Use chown for all the files and folders recursively in provided directory.

    Argument:
        :param directory    (str) path to the directory where permissions should be set
    """
    uid = pwd.getpwnam('yang').pw_uid
    gid = grp.getgrnam('yang').gr_gid
    os.chown(directory, uid, gid)
    for root, dirs, files in os.walk(directory):
        for dir in dirs:
            os.chown(os.path.join(root, dir), uid, gid)
        for file in files:
            os.chown(os.path.join(root, file), uid, gid)
