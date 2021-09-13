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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import os
import shutil
import sys
import tempfile

from git import Repo
from git.cmd import Git
from git.exc import GitCommandError

'''Notes:

repo.index.add(repo.untracked_files)

  Add all new files to the index

repo.index.add([i.a_path for i in repo.index.diff(None)])

  Add all modified files to the index. Also works for new directories.

repo.index.commit('commit for delete file')

  Commit any changes

repo.git.push()

  Push changes to origin.

repo.git.rm([f1, f2, ...])

  Remove files safely and add removal to index (note that files are
  left in lace, and then look like untracked files).

'''


def pull(repo_dir):
    """
    Pull all the new files in the master in specified directory.
    Directory should contain path where .git file is located.
    :param repo_dir: directory where .git file is located
    """
    g = Git(repo_dir)
    g.pull()
    a = Repo(repo_dir)
    for s in a.submodules:
        s.update(recursive=True, init=True)


def load(repo_dir: str, repo_url: str):
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


class RepoUtil(object):
    """Simple class for rolling up some git operations as part of file
    manipulation. The user should create the object with the URL to
    the repository and an appropriate set of credentials. At this
    """

    def __init__(self, repourl, logger=None):
        self.repourl = repourl
        self.localdir = None
        self.repo = None
        self.logger = logger

    def get_repo_dir(self):
        """Return the repository directory name from the URL"""
        return os.path.basename(self.repourl)

    def get_commit_hash(self, path=None, branch='master'):
        self.updateSubmodule()
        repo_temp = self
        remove_temp_repo = False
        if path is not None:
            for submodule in self.repo.submodules:
                if submodule.path in path:
                    repo_temp = RepoUtil(submodule._url)
                    repo_temp.clone()
                    remove_temp_repo = True
                    break
        found_hash = None
        if branch == 'master':
            found_hash = repo_temp.repo.head.commit.hexsha
        else:
            refs = repo_temp.repo.refs
            for ref in refs:
                if ref.name == branch or ref.name == 'origin/{}'.format(branch):
                    found_hash = ref.commit.hexsha
                    break
        if remove_temp_repo:
            repo_temp.remove()
        if found_hash is not None:
            return found_hash
        if self.logger is not None:
            self.logger.error('Git branch - {} - could not be resolved'.format(branch))
        return branch

    def get_repo_owner(self):
        """Return the root directory name of the repo.  In GitHub
        parlance, this would be the owner of the repository.
        """
        owner = os.path.basename(os.path.dirname(self.repourl))
        if ':' in owner:
            return owner[owner.index(':') + 1:]

        return owner

    def clone(self, config_user_name=None, config_user_email=None, local_dir=None):
        """Clone the specified repository to a local temp directory. This
        method may generate a git.exec.GitCommandError if the
        repository does not exist
        """
        if local_dir:
            self.localdir = local_dir
        else:
            self.localdir = tempfile.mkdtemp()
        self.repo = Repo.clone_from(self.repourl, self.localdir)
        if config_user_name:
            with self.repo.config_writer() as config:
                config.set_value('user', 'email', config_user_email)
                config.set_value('user', 'name', config_user_name)

    def updateSubmodule(self, recursive=True, init=True):
        """Clone submodules of a git repository"""
        for submodule in self.repo.submodules:
            submodule.update(recursive, init)

    def add_all_untracked(self):
        """Commit all untracked and modified files. This method shouldn't
        generate any exceptions as we don't allow unexpected
        operations to be invoked.
        """
        self.repo.index.add(self.repo.untracked_files)
        modified = []
        deleted = []
        for i in self.repo.index.diff(None):
            if os.path.exists(self.localdir+'/'+i.a_path):
                modified.append(i.a_path)
            else:
                deleted.append(i.a_path)
        if len(modified) > 0:
            self.repo.index.add(modified)
        if len(deleted) > 0:
            self.repo.index.remove(deleted)

    def commit_all(self, message='RepoUtil Commit'):
        """Equivalent of git commit -a -m MESSAGE."""
        self.repo.git.commit(a=True, m=message)

    def push(self):
        """Push repo to origin. Credential errors may happen here."""
        self.repo.git.push("origin")

    def remove(self):
        """Remove the temporary storage."""
        if self.localdir is not None:
            shutil.rmtree(self.localdir)
        self.localdir = None
        self.repo = None


if __name__ == '__main__':

    #
    # local imports
    #
    from argparse import ArgumentParser

    #
    # test arguments
    #
    parser = ArgumentParser(description='RepoUtil test params:')
    parser.add_argument('userpass', nargs=1, type=str,
                        help='Provide username:password for github https access'
                        )
    args, extra_args = parser.parse_known_args()
    if not args.userpass:
        print("username:password required")
        sys.exit(1)

    #
    # This repo exists
    #
    TEST_REPO = 'https://{}@github.com/einarnn/test.git'

    #
    # This repo does not exist
    #
    BOGUS_REPO = 'https://{}@github.com/einarnn/testtest.git'

    #
    # Create, clone and remove repo that exists.
    #
    print('\nTest 1\n------')
    try:
        r = RepoUtil(TEST_REPO.format(args.userpass[0]))
        r.clone()
        print('Temp directory: '+r.localdir)
        r.remove()
    except GitCommandError as e:
        print('Git Exception: ' + e.status)

    #
    # Create, clone and modify a repo with good credentials. Will Then
    # try to modify, commit and push. If the file 'ok.txt' is present,
    # we will try to delete it. If it's not, we will create it!
    #
    print('\nTest 2\n------')
    try:
        r = RepoUtil(TEST_REPO.format(args.userpass[0]))
        r.clone()
        print('Temp directory: '+r.localdir)
        ok_path = r.localdir + '/ok.txt'
        if os.path.exists(ok_path):
            print('Removing test file!')
            r.repo.git.rm(ok_path)
            # os.remove(ok_path)
        else:
            print('Creating test file!')
            with open(ok_path, 'w') as f:
                f.write('hello!\n')
                f.close()
        try:
            r.add_all_untracked()
            r.commit_all(message='push should succeed')
            r.push()
        except GitCommandError as e:
            print('Git Exception: ' + e.stderr)
        r.remove()
    except GitCommandError as e:
        print('Git Exception: ' + e.stderr)

    #
    # Create, clone and modify a repo with bogus credentials. Will Then try
    # to modify, commit and push, but still with bogus credentials.
    #
    print('\nTest 3\n------')
    try:
        r = RepoUtil(TEST_REPO.format('{}bogus'.format(args.userpass[0])))
        r.clone()
        print('Temp directory: '+r.localdir)
        with open(r.localdir+'/bogus.txt', 'w') as f:
            f.write('hello!\n')
            f.close()
        try:
            r.add_all_untracked()
            r.commit_all(message='push should fail')
            r.push()
        except GitCommandError as e:
            print('Git Exception as expected: ' + e.stderr)
        r.remove()
    except GitCommandError as e:
        print('Git Exception: ' + e.stderr)

    #
    # Try to create, clone and remove repo that does not exist. If
    # this is the caser, no dangling directory is left, so no need to
    # try and remove it.
    #
    print('\nTest 4\n------')
    try:
        r = RepoUtil(BOGUS_REPO.format(args.userpass[0]))
        r.clone()
        print('Temp directory: ' + r.localdir)
        r.remove()
    except GitCommandError as e:
        print('Git Exception as expected: ' + e.stderr)
