# Copyright The IETF Trust 2021, All Rights Reserved
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
This script contains shared methods definitions
that are used in both dratfPull.py and draftPullLocal.py scripts.

Contains following method definitions:
    check_name_no_revision_exist()
    check_early_revisions()
    get_latest_revision()
    get_draft_module_content()
    extract_rfc_tgz()
    set_permissions()
    update_forked_repository()
    clone_forked_repository()
"""

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

import configparser
import grp
import json
import logging
import os
import pwd
import tarfile
import time
import typing as t
from datetime import datetime

import requests
from git.exc import GitCommandError
from requests.exceptions import ConnectionError
from utility import repoutil, yangParser
from utility.staticVariables import github_url


def get_latest_revision(path: str, LOGGER: logging.Logger):
    """ Search for the latest revision in yang file

    Arguments:
        :param path     (str) full path to the yang file
        :param LOGGER   (logging.Logger) formated logger with the specified name
        :return         revision of the module at the given path
    """
    try:
        stmt = yangParser.parse(path)
        result = stmt.search_one('revision')
        assert result
        rev = result.arg
    except Exception:
        LOGGER.error(f'Cannot yangParser.parse {path}')
        rev = None  # In case of invalid YANG syntax, None is returned

    return rev


def check_name_no_revision_exist(directory: str, LOGGER: logging.Logger) -> None:
    """
    This function checks the format of all the modules filename.
    If it contains module with a filename without revision,
    we check if there is a module that has revision in
    its filename. If such module exists, then module with no revision
    in filename will be removed.

    Arguments:
        :param directory    (str) full path to directory with yang modules
        :param LOGGER       (logging.Logger) formated logger with the specified name
    """
    LOGGER.debug(f'Checking revision for directory: {directory}')
    for _, _, files in os.walk(directory):
        for basename in files:
            if '@' in basename:
                yang_file_name = basename.split('@')[0] + '.yang'
                revision = basename.split('@')[1].split('.')[0]
                yang_file_path = os.path.join(directory, yang_file_name)
                exists = os.path.exists(yang_file_path)
                if exists:
                    compared_revision = get_latest_revision(os.path.abspath(yang_file_path), LOGGER)
                    if compared_revision is None:
                        continue
                    if revision == compared_revision:
                        os.remove(yang_file_path)


def check_early_revisions(directory: str, LOGGER: logging.Logger) -> None:
    """
    This function checks all modules revisions and keeps only
    ones that are the newest. If there are two modules with
    two different revisions, then the older one is removed.

    Arguments:
        :param directory    (str) full path to directory with yang modules
        :param LOGGER       (logging.Logger) formated logger with the specified name
    """
    get_module_name = lambda filename: filename.split('.yang')[0].split('@')[0]
    is_revision_part_valid = lambda revision_part: revision_part.startswith('.') or revision_part.startswith('@')
    for filename in (filenames := os.listdir(directory)):
        module_name = get_module_name(filename)  # Beware of some invalid file names such as '@2015-03-09.yang'
        if module_name == '':
            continue
        files_to_delete = []
        revisions = []
        for nested_filename in filenames:
            if get_module_name(nested_filename) != module_name:
                continue
            nested_filename_revision_part = nested_filename.split(module_name)[1]
            if not is_revision_part_valid(nested_filename_revision_part):
                continue
            files_to_delete.append(nested_filename)
            revision = nested_filename_revision_part.split('.')[0].replace('@', '')
            if revision == '':
                yang_file_path = os.path.join(directory, nested_filename)
                revision = get_latest_revision(os.path.abspath(yang_file_path), LOGGER)
                if revision is None:
                    continue
            revision = convert_revision_to_datetime(revision)
            if revision:
                revisions.append(revision)
                continue
            # Probably revision filename contained invalid characters such as alphanumeric characters
            LOGGER.exception(f'Failed to process revision for {nested_filename}: (rev: {revision})')
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
                
                
def convert_revision_to_datetime(revision: str) -> t.Optional[datetime]:
    """
    This function tries to convert revision to a datetime object,
    in case of any exception returns None.

    Arguments:
        :param revision (str) yang module revision, looks like "2015-03-09"
    """
    try:
        revision_date = revision.split('-')
        year = int(revision_date[0])
        month = int(revision_date[1])
        day = int(revision_date[2])
    except ValueError:
        return
    try:
        return datetime(year, month, day)
    except ValueError:
        if month == 2 and day == 29:
            return datetime(year, month, 28)


def get_draft_module_content(experimental_path: str, config: configparser.ConfigParser, LOGGER: logging.Logger) -> None:
    """ Loop through download links for each module found in IETFDraft.json and try to get their content.

    Aruments:
        :param experimental_path    (str) full path to the directory with cloned experimental modules
        :param config               (configparser.ConfigParser) instance of ConfigParser class
        :param LOGGER               (logging.Logger) formated logger with the specified name
    """
    ietf_draft_url = config.get('Web-Section', 'ietf-draft-private-url')
    my_uri = config.get('Web-Section', 'my-uri')
    domain_prefix = config.get('Web-Section', 'domain-prefix')
    ietf_draft_json = {}
    response = requests.get(ietf_draft_url)
    try:
        ietf_draft_json = response.json()
    except json.decoder.JSONDecodeError:
        LOGGER.error(f'Unable to get content of {os.path.basename(ietf_draft_url)} file')
    for key in ietf_draft_json:
        filename = os.path.join(experimental_path, key)
        with open(filename, 'w+') as yang_file:
            yang_download_link = ietf_draft_json[key][2].split('href="')[1].split('">Download')[0]
            yang_download_link = yang_download_link.replace(domain_prefix, my_uri)
            try:
                yang_raw = requests.get(yang_download_link).text
                yang_file.write(yang_raw)
            except ConnectionError:
                LOGGER.error(f'Unable to retreive content of {key} - {yang_download_link}')
                yang_file.write('')


def extract_rfc_tgz(tgz_path: str, extract_to: str, LOGGER: logging.Logger) -> bool:
    """ Extract downloaded rfc.tgz file to directory and remove file.

    Arguments:
        :param tgz_path     (str) full path to the rfc.tgz file
        :param extract_to   (str) path to the directory where rfc.tgz is extractracted to
        :param LOGGER       (logging.Logger) formated logger with the specified name
    """
    tar_opened = False
    tgz = ''
    try:
        tgz = tarfile.open(tgz_path)
        tar_opened = True
        tgz.extractall(extract_to)
        tgz.close()
    except tarfile.ReadError:
        LOGGER.warning('tarfile could not be opened. It might not have been generated yet.'
                       ' Did the sdo_analysis cron job run already?')
    os.remove(tgz_path)

    return tar_opened


def set_permissions(directory: str) -> None:
    """ Use chown for all the files and folders recursively in provided directory.

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


def update_forked_repository(yang_models: str, forked_repo_url: str, LOGGER: logging.Logger) -> None:
    """ Check whether forked repository yang-catalog/yang is up-to-date with YangModels/yang repository.
    Push missing commits to the forked repository if any are missing.

    Arguments:
        :param yang_models      (str) path to the directory where YangModels/yang repo is cloned
        :param forked_repo_url  (str) url to the forked repository
        :param LOGGER           (logging.Logger) formated logger with the specified name
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

        # git fetch --all
        for remote in main_repo.repo.remotes:
            info = remote.fetch('main')[0]
            LOGGER.info(f'Remote: {remote.name} - Commit: {info.commit}')

        # git pull origin main
        origin.pull('main')[0]

        # git push fork main
        push_info = fork.push('main')[0]
        LOGGER.info(f'Push info: {push_info.summary}')
        if 'non-fast-forward' in push_info.summary:
            LOGGER.warning('yang-catalog/yang repo might not be up-to-date')
    except GitCommandError:
        LOGGER.exception('yang-catalog/yang repo might not be up-to-date')


def clone_forked_repository(repourl: str, commit_author: dict, LOGGER: logging.Logger) \
        -> t.Optional[repoutil.ModifiableRepoUtil]:
    """ Try to clone forked repository. Repeat the cloning process several times if the attempt was not successful.

    Arguments:
        :param repourl          (str) URL to the Github repository
        :param commit_author    (dict) Dictionary that contains information about the author of the commit
        :param LOGGER           (logging.Logger) formated logger with the specified name
    """
    attempts = 3
    wait_for_seconds = 30
    repo_name = repourl.split('github.com/')[-1].split('.git')[0]
    while True:
        try:
            LOGGER.info(f'Cloning repository from: {repourl}')
            repo = repoutil.ModifiableRepoUtil(
                repourl,
                clone_options={
                    'config_username': commit_author['name'],
                    'config_user_email': commit_author['email']
                })
            LOGGER.info(f'Repository cloned to local directory {repo.local_dir}')
            break
        except GitCommandError:
            attempts -= 1
            LOGGER.warning(f'Unable to clone {repo_name} repository - waiting for {wait_for_seconds} seconds')
            if attempts == 0:
                LOGGER.exception(f'Failed to clone repository {repo_name}')
                return
            time.sleep(wait_for_seconds)

    return repo
