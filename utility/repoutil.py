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
import time
import typing as t

import requests
from git import GitCommandError
from git.cmd import Git
from git.exc import InvalidGitRepositoryError
from git.repo import Repo


class RepoUtil:
    """
    Simple class for rolling up some git operations as part of file
    manipulation. The user should create the object with the URL to
    the repository and an appropriate set of credentials.
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

    def __init__(
        self,
        repourl: str,
        clone: bool = True,
        clone_options: t.Optional[CloneOptions] = None,
        logger: t.Optional[logging.Logger] = None,
    ):
        """
        Arguments:
            :param repourl          (str) URL of the repository
            :param clone            (bool) Should always be set to True. To load a repository
                                           which has already been cloned, see  the load() function.
            :param clone_options    (Optional[CloneOptions]) May contain the information for the repository cloning
            :param logger           (Optional[Logger])
        """
        self.url = repourl
        self.logger = logger
        clone_options = clone_options or self.CloneOptions()
        if clone:
            self._clone(clone_options)
        self.previous_active_branch: t.Optional[str] = None

    def _clone(self, clone_options: CloneOptions):
        """
        Clone the specified repository and recursively clone submodules.
        This method raises a git.exec.GitCommandError if the repository does not exist.

        Arguments:
            :param clone_options  (CloneOptions) Data for the repository cloning
        """
        if local_dir := clone_options.get('local_dir'):
            self.local_dir = local_dir
        else:
            self.local_dir = tempfile.mkdtemp()
        multi_options = ['--recurse-submodules'] if clone_options.setdefault('recurse_submodules', True) else None
        self.repo = Repo.clone_from(self.url, self.local_dir, multi_options=multi_options)
        if config_username := clone_options.get('config_username'):
            with self.repo.config_writer() as config:
                config.set_value('user', 'email', clone_options.get('config_user_email'))
                config.set_value('user', 'name', config_username)


# This probably isn't worth it's own class anymore
class ModifiableRepoUtil(RepoUtil):
    """
    RepoUtil subclass with methods for manipulating the repository.
    The repository directory is automatically removed on object deletion.
    """

    def __init__(
        self,
        repourl: str,
        clone: bool = True,
        clone_options: t.Optional[RepoUtil.CloneOptions] = None,
        logger: t.Optional[logging.Logger] = None,
    ):
        super().__init__(repourl, clone, clone_options, logger)

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


def construct_github_repo_url(user: str, repo: str, token: t.Optional[str] = None) -> str:
    """Construct the URL to a GitHub repository."""
    if token:
        return f'https://{token}@github.com/{user}/{repo}.git'
    return f'https://github.com/{user}/{repo}.git'


def clone_repo(
    repo_url: str,
    clone_options: RepoUtil.CloneOptions,
    logger: logging.Logger,
) -> t.Optional[ModifiableRepoUtil]:
    """
    Tries to clone a repository. Repeat the cloning process several times if the attempt was not successful.

    Arguments:
        :param repo_url          (str) URL to the GitHub repository
        :param clone_options    (dict) Dictionary that contains information about the author of the commit
        :param logger           (logging.Logger) formated logger with the specified name
    """
    attempts = 3
    wait_for_seconds = 30
    repo_name = repo_url.split('github.com/')[-1].split('.git')[0]
    while True:
        try:
            logger.info(f'Cloning repository from: {repo_url}')
            repo = ModifiableRepoUtil(repo_url, clone_options=clone_options)
            logger.info(f'Repository cloned to local directory {repo.local_dir}')
            break
        except GitCommandError:
            attempts -= 1
            logger.warning(f'Unable to clone {repo_name} repository - waiting for {wait_for_seconds} seconds')
            if attempts == 0:
                logger.exception(f'Failed to clone repository {repo_name}')
                return
            time.sleep(wait_for_seconds)
    return repo


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
    head: str
    base: str


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
    event: str


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


def add_worktree(repo_dir: str, branch: t.Optional[str] = None, new_worktree_dir: t.Optional[str] = None) -> str:
    new_worktree_dir = new_worktree_dir or tempfile.mkdtemp()
    if branch:
        Git(repo_dir).worktree('add', new_worktree_dir, branch)
    else:
        Git(repo_dir).worktree('add', '--detach', new_worktree_dir)
    return new_worktree_dir


def remove_worktree(worktree_dir: str):
    Git(worktree_dir).worktree('remove', '.')
