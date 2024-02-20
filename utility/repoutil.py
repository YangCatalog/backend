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
from dataclasses import dataclass

import requests
from git.cmd import Git
from git.exc import GitCommandError, InvalidGitRepositoryError
from git.repo import Repo


class RepoUtil:
    """
    Simple class for rolling up some git operations as part of file manipulation. The user should create the object
    with the URL to the repository and an appropriate set of credentials.
    """

    local_dir: str
    repo: Repo

    class CloneOptions(t.TypedDict, total=False):
        """Data used during cloning of a repository"""

        local_dir: str
        'Directory where to clone the repo. By default, a new temporary directory will be created.'
        config_username: str
        'Username to set in the git config.'
        config_user_email: str
        'Email to set in the git config.'
        recurse_submodules: bool
        'If set to True then the repository will be cloned with all of submodules, will be set to True by default'

    def __init__(self, repourl: str, temp: bool = True):
        """
        For internal use only, for creating RepoUtil objects, use the load or clone class methods.

        Arguments:
            :param repourl          (str) URL of the repository
            :param temp             (bool) Delete directory when the RepoUtil object is deleted
        """
        self.temp = temp
        self.url = repourl

    @classmethod
    def clone(cls, repourl: str, temp: bool, clone_options: t.Optional[CloneOptions] = None) -> 'RepoUtil':
        """
        Clone the specified repository and recursively clone submodules.
        This method raises a git.exec.GitCommandError if the repository does not exist.

        Arguments:
            :param repourl          (str) URL of the repository
            :param temp             (bool) Delete directory when the RepoUtil object is deleted
            :param clone_options    (CloneOptions) Data for the repository cloning
        """
        clone_options = clone_options or cls.CloneOptions()
        repoutil = cls(repourl, temp)
        if local_dir := clone_options.get('local_dir'):
            repoutil.local_dir = local_dir
        else:
            repoutil.local_dir = tempfile.mkdtemp()
        multi_options = ['--recurse-submodules'] if clone_options.setdefault('recurse_submodules', True) else None
        repoutil.repo = Repo.clone_from(repoutil.url, repoutil.local_dir, multi_options=multi_options)
        if config_username := clone_options.get('config_username'):
            with repoutil.repo.config_writer() as config:
                config.set_value('user', 'email', clone_options.get('config_user_email'))
                config.set_value('user', 'name', config_username)
        return repoutil

    @classmethod
    def load(cls, repo_dir: str, repo_url: str, temp: bool) -> 'RepoUtil':
        """
        Load git repository from a local directory into a Python object.

        Arguments:
            :param repo_dir    (str) directory where .git file is located
            :param repo_url    (str) url to GitHub repository
            :param temp             (bool) Delete directory when the RepoUtil object is deleted
        """
        repoutil = cls(repo_url, temp)
        try:
            repoutil.repo = Repo(repo_dir)
        except InvalidGitRepositoryError:
            raise InvalidGitRepositoryError(repo_dir)
        repoutil.local_dir = repo_dir
        return repoutil

    def __del__(self):
        """Remove the temporary storage."""
        if self.temp and os.path.isdir(self.local_dir):
            shutil.rmtree(self.local_dir)


class Worktree:
    """
    Creates a new git worktree in the new_worktree_dir directory: https://git-scm.com/docs/git-worktree#_description.
    """

    repo: Repo
    worktree_dir: str

    @dataclass
    class ConfigOptions:
        config_username: str
        'Username to set in the git config.'
        config_user_email: str
        'Email to set in the git config.'

    def __init__(
        self,
        repo_dir: str,
        logger: logging.Logger,
        main_branch: str = 'main',
        branch: t.Optional[str] = None,
        new_worktree_dir: t.Optional[str] = None,
        config_options: t.Optional[ConfigOptions] = None,
    ):
        """
        Arguments:
            :param repo_dir (str) Path to the existing repository to create a worktree for.
            :param logger (Logger) Logger object.
            :param main_branch (str) Name of the repository's main branch.
            :param branch (Optional[str]) Branch to create a worktree from.
            :param new_worktree_dir (Optional[str]) Directory where the new worktree will be created, if None,
            a new temporary directory will be created. Be careful, the new_worktree_dir will be automatically deleted
            after deleting the Worktree object, so don't pass permanent directories here.
            :param config_options (Optional[ConfigOptions]) Options to write to the git config, by default no options
            will be written to the git config.
        """
        self.logger = logger
        self._create_worktree(repo_dir, main_branch, branch=branch, new_worktree_dir=new_worktree_dir)
        self._repo_git = Git(self.worktree_dir)
        self.repo = Repo(self.worktree_dir)
        if config_options:
            self._set_config_options(config_options)

    def _create_worktree(
        self,
        repo_dir: str,
        main_branch: str,
        branch: t.Optional[str] = None,
        new_worktree_dir: t.Optional[str] = None,
    ):
        self.worktree_dir = new_worktree_dir or tempfile.mkdtemp()
        if not branch:
            Git(repo_dir).worktree('add', '--detach', self.worktree_dir)
            return
        repo = Repo(repo_dir)
        if branch not in repo.branches:
            repo.git.checkout(main_branch)
            repo.create_head(branch)
        repo_git = Git(repo_dir)
        repo_git.worktree('prune')
        try:
            repo_git.worktree('add', self.worktree_dir, branch)
        except GitCommandError as e:
            conflicting_worktree_exists: bool = (
                'is already checked out at' in e.stderr or 'is already used by worktree at' in e.stderr
            )
            if not conflicting_worktree_exists:
                raise e
            worktrees_output: list[str] = repo.git.worktree('list', '--porcelain').splitlines()
            conflicting_worktree = None
            for line in worktrees_output:
                if line.startswith('worktree '):
                    conflicting_worktree = line.lstrip('worktree ')
                elif line.startswith('branch ') and branch in line:
                    repo_git.worktree('remove', conflicting_worktree, '--force')
                    break
            repo_git.worktree('add', self.worktree_dir, branch)

    def _set_config_options(self, config_options: ConfigOptions):
        with self.repo.config_writer() as git_config:
            git_config.set_value('user', 'email', config_options.config_user_email)
            git_config.set_value('user', 'name', config_options.config_username)

    def __del__(self):
        """
        Removes the worktree and its directory. Be careful, can be called when you don't use the worktree object itself
        anymore, for example, when you return not the Worktree object from a function itself, for example:
        return Worktree().repo
        """
        if hasattr(self, '_repo_git'):
            try:
                self._repo_git.worktree('remove', '.', '--force')
            except GitCommandError:
                pass


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


def construct_github_repo_url(user: str, repo: str, token: t.Optional[str] = None) -> str:
    """Construct the URL to a GitHub repository."""
    if token:
        return f'https://{token}@github.com/{user}/{repo}.git'
    return f'https://github.com/{user}/{repo}.git'


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
    request_body_dict = dict(request_body or PullRequestCreationDetail())
    request_body_dict['head'] = head_branch
    request_body_dict['base'] = base_branch
    return requests.post(
        f'https://api.github.com/repos/{owner}/{repo}/pulls',
        headers=headers,
        data=json.dumps(request_body_dict),
    )


class PullRequestApprovingDetail(t.TypedDict, total=False):
    """
    Additional data to send for a PullRequest approving, detail information about each param can be found here:
    https://docs.github.com/en/rest/pulls/reviews?apiVersion=latest#create-a-review-for-a-pull-request
    """

    commit_id: str
    body: str
    comments: list[dict]
    event: t.Literal['APPROVE']


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
