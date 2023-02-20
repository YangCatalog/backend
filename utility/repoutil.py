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

import json
import logging
import os
import shutil
import tempfile
import typing as t

import requests
from git.cmd import Git
from git.exc import InvalidGitRepositoryError
from git.repo import Repo
from gitdb.exc import BadName


class RepoUtil:
    """
    Simple class for rolling up some git operations as part of file
    manipulation. The user should create the object with the URL to
    the repository and an appropriate set of credentials.
    """

    local_dir: str
    repo: Repo

    def __init__(
        self,
        repourl: str,
        clone: bool = True,
        clone_options: t.Optional[dict] = None,
        logger: t.Optional[logging.Logger] = None,
    ):
        """
        Arguments:
            :param repourl          (str) URL of the repository
            :param clone            (bool) Should always be set to True. To load a repository
                                           which has already been cloned, see  the load() function.
            :param clone_options    (dict) May contain the keys local_dir, config_username and config_email
            :param logger           (Optional[Logger])
        """
        self.url = repourl
        self.logger = logger
        clone_options = clone_options or {}
        if clone:
            self._clone(**clone_options)
        self.previous_active_branch: t.Optional[str] = None

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
                    assert isinstance(submodule.path, str)
                    if submodule.path in path:
                        return load(os.path.join(self.local_dir, submodule.path), submodule._url).get_commit_hash(
                            path,
                            branch,
                        )
            return self.repo.commit(f'origin/{branch}').hexsha
        except BadName:
            if self.logger:
                self.logger.error(f'Git branch - {branch} - could not be resolved')
            return branch

    def get_repo_owner(self) -> str:
        """Return the root directory name of the repo.  In GitHub
        parlance, this would be the owner of the repository.

        Arguments:
            :return     (str) GitHub repo owner.
        """
        owner = os.path.basename(os.path.dirname(self.url))
        return owner.split(':')[-1]

    def _clone(
        self,
        local_dir: t.Optional[str] = None,
        config_username: t.Optional[str] = None,
        config_user_email: t.Optional[str] = None,
    ):
        """
        Clone the specified repository and recursively clone submodules.
        This method raises a git.exec.GitCommandError if the repository does not exist.

        Arguments:
            :param local_dir  (Optional[str]) Directory where to clone the repo.
            By default, a new temporary directory is created.
            :param config_username  (Optional[str]) Username to set in the git config.
            :param config_user_email  (Optional[str]) Email to set in the git config.
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
    """
    RepoUtil subclass with methods for manipulating the repository.
    The repository directory is automatically removed on object deletion.
    """

    def __init__(
        self,
        repourl: str,
        clone: bool = True,
        clone_options: t.Optional[dict] = None,
        logger: t.Optional[logging.Logger] = None,
    ):
        super().__init__(repourl, clone, clone_options, logger)

    def add_untracked_remove_deleted(self):
        """Add untracked files and remove deleted files."""
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
    Perform a git pull inside the directory.
    The directory should contain a git repository.

    Arguments:
        :param repo_dir     (str) Directory containing a git repository
    """
    git = Git(repo_dir)
    git.pull()
    repo = Repo(repo_dir)
    for submodule in repo.submodules:
        submodule.update(recursive=True, init=True)


def load(repo_dir: str, repo_url: str) -> RepoUtil:
    """
    Load git repository from a local directory into a Python object.

    Arguments:
        :param repo_dir    (str) directory where .git file is located
        :param repo_url    (str) url to GitHub repository
    """
    repo = (RepoUtil if 'yangmodels/yang' in repo_dir else ModifiableRepoUtil)(repo_url, clone=False)
    try:
        repo.repo = Repo(repo_dir)
    except InvalidGitRepositoryError:
        raise InvalidGitRepositoryError(repo_dir)
    repo.local_dir = repo_dir
    return repo


class PullRequestCreationDetail(t.TypedDict, total=False):
    """
    Additional data to send for a PullRequest creation, detail information about each param can be found here:
    https://docs.github.com/en/rest/pulls/pulls?apiVersion=latest#create-a-pull-request
    """

    head_repo: str
    title: str
    body: str
    maintainer_can_modify: bool
    draft: bool
    issue: int


def create_pull_request(
    owner: str,
    repo: str,
    head_branch: str,
    base_branch: str,
    headers: t.Optional[dict] = None,
    request_body: t.Optional[PullRequestCreationDetail] = None,
) -> requests.Response:
    """
    Creates a PullRequest to the needed repository, full documentation can be found here:
    https://docs.github.com/en/rest/pulls/pulls?apiVersion=latest#create-a-pull-request

    Arguments:
        :param owner (str) Repository owner's name.
        :param repo (str) Repository name.
        :param head_branch (str) The name of the branch where your changes are implemented.
        For cross-repository pull requests in the same network, namespace head with a user like this: username:branch.
        :param base_branch (str) The name of the branch you want the changes pulled into.
        This should be an existing branch on the current repository.
        This should be an existing branch on the current repo.
        :param request_body (Optional[PullRequestCreationDetail]) Request body to send.
        :param headers (Optional[dict]) Headers to send,
        access token can be provided here like that {'Authorization': 'token TOKEN_VALUE'}.
        :return (requests.Response) result of the PR creation
    """
    headers = headers or {}
    headers['accept'] = 'application/vnd.github+json'
    request_body = request_body or PullRequestCreationDetail()
    request_body['head'] = head_branch
    request_body['base'] = base_branch
    return requests.post(
        f'https://api.github.com/repos/{owner}/{repo}/pulls',
        headers=headers,
        data=json.dumps(request_body),
    )


class PullRequestApprovingDetail(t.TypedDict, total=False):
    """
    Additional data to send for a PullRequest approving, detail information about each param can be found here:
    https://docs.github.com/en/rest/pulls/reviews?apiVersion=latest#create-a-review-for-a-pull-request
    """

    commit_id: str
    body: str
    comments: list[dict]


def approve_pull_request(
    owner: str,
    repo: str,
    pull_number: int,
    headers: t.Optional[dict] = None,
    request_body: t.Optional[PullRequestApprovingDetail] = None,
) -> requests.Response:
    """
    Approves the PullRequest, full documentation can be found here:
    https://docs.github.com/en/rest/pulls/reviews?apiVersion=latest#create-a-review-for-a-pull-request

    Arguments:
        :param owner (str) Repository owner's name.
        :param repo (str) Repository name.
        :param pull_number (int) Number of the PullRequest to approve
        :param headers (Optional[dict]) Headers to send,
         access token can be provided here like that {'Authorization': 'token TOKEN_VALUE'}.
        :param request_body (Optional[PullRequestApprovingDetail]) Request body to send.
        :return (requests.Response) result of the PR creation
    """
    headers = headers or {}
    headers['accept'] = 'application/vnd.github+json'
    request_body = request_body or PullRequestApprovingDetail()
    request_body['event'] = 'APPROVE'
    return requests.post(
        f'https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/reviews',
        headers=headers,
        data=json.dumps(request_body),
    )


class PullRequestMergingDetail(t.TypedDict, total=False):
    """
    Additional data to send for a PullRequest merging, detail information about each param can be found here:
    https://docs.github.com/en/rest/pulls/reviews?apiVersion=latest#merge-a-pull-request
    """

    commit_title: str
    commit_message: str
    sha: str
    merge_method: str


def merge_pull_request(
    owner: str,
    repo: str,
    pull_number: int,
    headers: t.Optional[dict] = None,
    request_body: t.Optional[dict] = None,
) -> requests.Response:
    """
    Merges the PullRequest, full documentation can be found here:
    https://docs.github.com/en/rest/pulls/reviews?apiVersion=latest#merge-a-pull-request

    Arguments:
        :param owner (str) Repository owner's name.
        :param repo (str) Repository name.
        :param pull_number (int) Number of the PullRequest to approve
        :param headers (Optional[dict]) Headers to send,
         access token can be provided here like that {'Authorization': 'token TOKEN_VALUE'}.
        :param request_body (Optional[PullRequestMergingDetail]) Request body to send.
        :return (requests.Response) result of the PR creation
    """
    headers = headers or {}
    headers['accept'] = 'application/vnd.github+json'
    return requests.put(
        f'https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/merge',
        headers=headers,
        data=json.dumps(request_body or PullRequestMergingDetail()),
    )
