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

from git.repo import Repo
from git.cmd import Git


class RepoUtil(object):
    """Simple class for rolling up some git operations as part of file
    manipulation. The user should create the object with the URL to
    the repository and an appropriate set of credentials. At this
    """

    def __init__(self, repourl: str, logger: t.Optional[logging.Logger] = None):
        self.url = repourl
        self.localdir = None
        self.repo = None
        self.logger = logger

    def get_repo_dir(self) -> str:
        """Return the repository directory name from the URL"""
        return os.path.splitext(os.path.basename(self.url))[0]

    def get_commit_hash(self, path: t.Optional[str] = None, branch: str = 'master') -> str:
        self.update_submodule()
        repo_temp = self
        remove_temp_repo = False
        if path is not None:
            assert self.repo is not None
            for submodule in self.repo.submodules:
                if submodule.path in path:
                    repo_temp = RepoUtil(submodule._url)
                    repo_temp.clone()
                    remove_temp_repo = True
                    break
        try:
            assert repo_temp.repo is not None
            return repo_temp.repo.commit('origin/{}'.format(branch)).hexsha
        except:
            if self.logger:
                self.logger.error('Git branch - {} - could not be resolved'.format(branch))
            return branch
        finally:
            if remove_temp_repo:
                repo_temp.remove()

    def get_repo_owner(self) -> str:
        """Return the root directory name of the repo.  In GitHub
        parlance, this would be the owner of the repository.
        """
        owner = os.path.basename(os.path.dirname(self.url))
        return owner.split(':')[-1]

    def clone(self, config_user_name: t.Optional[str] = None,
              config_user_email: t.Optional[str] = None, local_dir: t.Optional[str] = None):
        """Clone the specified repository to a local temp directory. This
        method may generate a git.exec.GitCommandError if the
        repository does not exist
        """
        if local_dir:
            self.localdir = local_dir
        else:
            self.localdir = tempfile.mkdtemp()
        self.repo = Repo.clone_from(self.url, self.localdir)
        if config_user_name:
            with self.repo.config_writer() as config:
                config.set_value('user', 'email', config_user_email)
                config.set_value('user', 'name', config_user_name)

    def update_submodule(self, recursive: bool = True, init: bool = True):
        """Clone submodules of a git repository"""
        self.repo.submodule_update(recursive=recursive, init=init)

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
        self.repo.git.push("origin")

    def remove(self):
        """Remove the temporary storage."""
        if self.localdir is not None and os.path.isdir(self.localdir):
            shutil.rmtree(self.localdir)
        self.localdir = None
        self.repo = None


def pull(repo_dir: str):
    """
    Pull all the new files in the master in specified directory.
    Directory should contain path where .git file is located.
    :param repo_dir: directory where .git file is located
    """
    git = Git(repo_dir)
    git.pull()
    repo = Repo(repo_dir)
    for submodule in repo.submodules:
        submodule.update(recursive=True, init=True)


def load(repo_dir: str, repo_url: str) -> t.Optional[RepoUtil]:
    """
    Load git repository from local directory into Python object.

    :param repo_dir:    (str) directory where .git file is located
    :param repo_url:    (str) url to Github repository
    """
    repo = RepoUtil(repo_url)
    try:
        repo.repo = Repo(repo_dir)
    except:
        repo = None
    return repo
