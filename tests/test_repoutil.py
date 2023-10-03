# Copyright The IETF Trust 2019, All Rights Reserved
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

__author__ = 'Stanislav Chlebec'
__copyright__ = 'Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'stanislav.chlebec@pantheon.tech'

import logging
import os
import shutil
import unittest

from git import Repo

import utility.repoutil as repoutil
from utility.create_config import create_config

TEST_REPO_URL = 'https://github.com/yang-catalog/test'
TEST_REPO_MAIN_BRANCH = 'master'


class TestRepoutil(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.myname = 'yang-catalog'
        cls.myemail = 'fake@gmail.com'

    def setUp(self):
        self.repo = repoutil.RepoUtil.clone(
            TEST_REPO_URL,
            temp=True,
            clone_options={'config_username': self.myname, 'config_user_email': self.myemail},
        )

    def test_pull(self):
        repoutil.pull(self.repo.local_dir)

    def test_load(self):
        repo = repoutil.RepoUtil.load(self.repo.local_dir, self.repo.url, True)

        self.assertEqual(repo.url, self.repo.url)

    def test_clone(self):
        local_dir = self.repo.local_dir

        self.assertTrue(os.path.exists(local_dir))
        self.assertIsNotNone(self.repo.repo)
        with self.repo.repo.config_reader() as config:
            self.assertEqual(config.get_value('user', 'email'), self.myemail)
            self.assertEqual(config.get_value('user', 'name'), self.myname)

    def test_del(self):
        self.assertTrue(os.path.exists(self.repo.local_dir))
        repodir = self.repo.local_dir

        del self.repo
        self.assertFalse(os.path.exists(repodir))


class TestWorktree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = create_config()
        cls.repo_config_username = cls.config.get('General-Section', 'repo-config-name')
        cls.repo_config_user_email = cls.config.get('General-Section', 'repo-config-email')
        cls.logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        handler.setLevel(logging.ERROR)
        cls.logger.addHandler(handler)
        cls.path_to_test_repo = os.path.join(os.environ['BACKEND'], 'utility/tests/resources/test_repo')
        os.makedirs(cls.path_to_test_repo, exist_ok=True)
        cls.repo = Repo.clone_from(TEST_REPO_URL, cls.path_to_test_repo)
        cls.test_branch_name = 'test'

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.path_to_test_repo)

    def test_create_worktree_from_non_existent_branch(self):
        try:
            wt = self._create_worktree()
            self._check_worktree_validity(wt)
            del wt
        finally:
            if self.test_branch_name in self.repo.branches:
                self.repo.delete_head(self.test_branch_name)

    def test_create_worktree_from_existing_branch(self):
        self.repo.create_head(self.test_branch_name)
        try:
            wt = self._create_worktree()
            self._check_worktree_validity(wt)
            del wt
        finally:
            self.repo.delete_head(self.test_branch_name)

    def test_create_worktree_if_one_already_exists(self):
        self.repo.create_head(self.test_branch_name)
        try:
            wt1 = self._create_worktree()
            wt2 = self._create_worktree()
            self._check_worktree_validity(wt2)
            self.assertTrue(not os.path.exists(wt1.worktree_dir))
            del wt2
        finally:
            self.repo.delete_head(self.test_branch_name)

    def _create_worktree(self) -> repoutil.Worktree:
        return repoutil.Worktree(
            self.path_to_test_repo,
            self.logger,
            main_branch=TEST_REPO_MAIN_BRANCH,
            branch=self.test_branch_name,
            config_options=repoutil.Worktree.ConfigOptions(
                config_username=self.repo_config_username,
                config_user_email=self.repo_config_user_email,
            ),
        )

    def _check_worktree_validity(self, wt: repoutil.Worktree):
        self.assertTrue(os.path.exists(wt.worktree_dir))
        with wt.repo.config_reader() as git_config_reader:
            self.assertEqual(git_config_reader.get_value('user', 'email'), self.repo_config_user_email)
            self.assertEqual(git_config_reader.get_value('user', 'name'), self.repo_config_username)


if __name__ == '__main__':
    unittest.main()
