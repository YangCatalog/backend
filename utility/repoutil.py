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

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import logging
import os
import shutil
import tempfile
import typing as t

from git.cmd import Git
from git.exc import InvalidGitRepositoryError
from git.repo import Repo
from gitdb.exc import BadName


class RepoUtil:
    """Simple class for rolling up some git operations as part of file
    manipulation. The user should create the object with the URL to
    the repository and an appropriate set of credentials.
    """

    local_dir: str
    repo: Repo

    def __init__(self, repourl: str, clone: bool = True, clone_options: dict = {}, 
                 logger: t.Optional[logging.Logger] = None):
        """
        Arguments:
            :param repourl          (str) URL of the repository
            :param clone            (bool) Should always be set to True. To load a repository
                                           which has already been cloned, see  the load() function.
            :param clone_options    (dict) May contain the keys local_dir, config_username and config_email
            :param logger           (logging.Logger)
        """
        self.url = repourl
        self.logger = logger
        if clone:
            self._clone(**clone_options)


    def get_repo_dir(self) -> str:
        """Return the repository directory name from the URL"""
        return os.path.splitext(os.path.basename(self.url))[0]

    def get_commit_hash(self, path: str = '', branch: str = 'HEAD') -> str:
        """Get the commit hash of a branch.

        Arguments:
            :param path     (str) Path to a file of interest. This is used to determine
                                  if we should search for the the commit hash in a submodule.
            :param branch   (str) The branch we want to get the commit hash of.
            :return         (str) The commit hash.
        """
        assert self.repo is not None, 'Git repo not initialized'
        try:
            if path:
                for submodule in self.repo.submodules:
                    if submodule.path in path:
                        return load(os.path.join(self.local_dir, submodule.path), submodule._url) \
                            .get_commit_hash(path, branch)
            return self.repo.commit('origin/{}'.format(branch)).hexsha
        except BadName:
            if self.logger:
                self.logger.error('Git branch - {} - could not be resolved'.format(branch))
            return branch

    def get_repo_owner(self) -> str:
        """Return the root directory name of the repo.  In GitHub
        parlance, this would be the owner of the repository.

        Arguments:
            :return:
        """
        owner = os.path.basename(os.path.dirname(self.url))
        return owner.split(':')[-1]

    def _clone(self, local_dir: t.Optional[str] = None, config_username: t.Optional[str] = None,
              config_user_email: t.Optional[str] = None):
        """Clone the specified repository and recursively clone submodules.
        This method raises a git.exec.GitCommandError if the repository does not exist.
        """
        if local_dir:
            self.local_dir = local_dir
        else:
            self.local_dir = tempfile.mkdtemp()
        self.repo = Repo.clone_from(self.url, self.local_dir, multi_options=['--recurse-submodules'])
        if config_username:
            with self.repo.config_writer() as config:
                config.set_value('user', 'email', config_user_email)
                config.set_value('user', 'name', config_username)


class ModifiableRepoUtil(RepoUtil):
    """RepoUtil subclass with methods for manipulating the repository.
    The repository directory is automatically removed on object deletion.
    """

    def __init__(self, repourl: str, clone: bool = True, clone_options: dict = {}, 
                 logger: t.Optional[logging.Logger] = None):
        super().__init__(repourl, clone, clone_options, logger)

    def add_untracked_remove_deleted(self):
        """Add untracked files and remove deleted files. This method shouldn't
        generate any exceptions as we don't allow unexpected
        operations to be invoked.
        """
        self.repo.index.add(self.repo.untracked_files)
        diff = self.repo.index.diff(None)
        for file in diff.iter_change_type('D'):
            self.repo.index.remove(file.a_path)

    def commit_all(self, message: str = 'RepoUtil Commit'):
        """Equivalent of git commit -a -m MESSAGE."""
        self.repo.git.commit(a=True, m=message)

    def push(self):
        """Push repo to origin. Credential errors may happen here."""
        self.repo.git.push('origin')

    def __del__(self):
        """Remove the temporary storage."""
        if os.path.isdir(self.local_dir):
            shutil.rmtree(self.local_dir)


def pull(repo_dir: str):
    """
    Pull all the new files in the master in specified directory.
    Directory should contain path where .git file is located.

    Arguments:
        :param repo_dir directory where .git file is located
    """
    git = Git(repo_dir)
    git.pull()
    repo = Repo(repo_dir)
    for submodule in repo.submodules:
        submodule.update(recursive=True, init=True)


def load(repo_dir: str, repo_url: str) -> RepoUtil:
    """
    Load git repository from local directory into Python object.

    Arguments:
        :param repo_dir    (str) directory where .git file is located
        :param repo_url    (str) url to Github repository
    """
    repo = (RepoUtil if 'yangmodels/yang' in repo_dir else ModifiableRepoUtil)(repo_url, clone=False)
    try:
        repo.repo = Repo(repo_dir)
    except InvalidGitRepositoryError:
        raise InvalidGitRepositoryError(repo_dir)
    repo.local_dir = repo_dir
    return repo
