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
import re
import subprocess
import unittest

from git.exc import GitCommandError
from git.repo import Repo

import utility.repoutil as ru
from utility.create_config import create_config


class TestRepoutil(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repourl = 'https://github.com/yang-catalog/test'
        cls.repo_owner = 'yang-catalog'

        cls.logger = logging.getLogger(__name__)
        f_handler = logging.FileHandler('test_repoutil.log')
        f_handler.setLevel(logging.ERROR)
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)
        cls.logger.addHandler(f_handler)

        cls.myname = 'yang-catalog'
        cls.myemail = 'fake@gmail.com'

        if os.environ.get('GITHUB_ACTIONS'):
            cls.token = os.environ['TOKEN']
        else:
            cls.token = create_config().get('Secrets-Section', 'yang-catalog-token')

    def setUp(self):
        self.repo = ru.ModifiableRepoUtil(
            self.repourl,
            clone_options={'config_username': self.myname, 'config_user_email': self.myemail},
        )
        self.repo.logger = self.logger

    def test_pull(self):
        ru.pull(self.repo.local_dir)

    def test_load(self):
        repo = ru.load(self.repo.local_dir, self.repo.url)

        self.assertEqual(repo.url, self.repo.url)

    def test_get_repo_dir(self):
        self.assertEqual(self.repo.get_repo_dir(), 'test')

    def test_get_commit_hash(self):
        self.assertEqual(self.repo.get_commit_hash(), '0d8d5a76cdd4cc2a9e9709f6acece6d57c0b06ea')
        self.assertEqual(self.repo.get_commit_hash(branch='test'), '971423d605268bd7b38c5153c72ff12bfa408f1d')
        self.assertEqual(self.repo.get_commit_hash('subrepo', 'master'), 'de04507eaba334bfdad41ac75a2044d9d63922ee')

    def test_get_repo_owner(self):
        self.assertEqual(self.repo.get_repo_owner(), 'yang-catalog')

    def test_clone(self):
        local_dir = self.repo.local_dir

        self.assertTrue(os.path.exists(local_dir))
        self.assertIsNotNone(self.repo.repo)
        with self.repo.repo.config_reader() as config:
            self.assertEqual(config.get_value('user', 'email'), self.myemail)
            self.assertEqual(config.get_value('user', 'name'), self.myname)

    def test_clone_invalid_url(self):
        with self.assertRaises(GitCommandError):
            ru.ModifiableRepoUtil('https://github.com/yang-catalog/fake')

    def test_add_untracked_remove_deleted(self):
        repodir = self.repo.local_dir
        repo = Repo(repodir)
        status_command = f'cd {repodir} && git status'

        file = os.path.join(repodir, 'new')
        f = open(file, 'w')
        f.write('test')
        f.close()

        self.assertEqual('new', repo.untracked_files[0])
        self.repo.add_untracked_remove_deleted()
        self.assertFalse(repo.untracked_files, 'should be empty after succesful adding')
        out = subprocess.getoutput(status_command)
        self.assertTrue(re.search('new file:.*new', out))

        file = os.path.join(repodir, 'README.md')
        f = open(file, 'a+')
        f.write('test')
        f.close()

        self.repo.add_untracked_remove_deleted()
        out = subprocess.getoutput(status_command)
        self.assertTrue(re.search('modified:.*README\\.md', out))

        file = os.path.join(repodir, 'ok.txt')
        os.remove(file)

        self.repo.add_untracked_remove_deleted()
        out = subprocess.getoutput(status_command)
        self.assertTrue(re.search('deleted:.*ok\\.txt', out))

        os.mkdir(os.path.join(repodir, 'dir'))
        os.rename(os.path.join(repodir, 'foo', 'a.txt'), os.path.join(repodir, 'dir', 'a.txt'))

        self.repo.add_untracked_remove_deleted()
        out = subprocess.getoutput(status_command)
        self.assertTrue(re.search('renamed:.*foo/a\\.txt.*->.*dir/a\\.txt', out))

    def test_commit_all(self):
        repodir = self.repo.local_dir
        status_command = f'cd {repodir} && git status'

        file = os.path.join(repodir, 'README.md')
        f = open(file, 'a+')
        f.write('test')
        f.close()

        self.repo.add_untracked_remove_deleted()
        self.repo.commit_all()
        out = subprocess.getoutput(status_command)
        self.assertIn("Your branch is ahead of 'origin/master' by 1 commit.", out)
        out = subprocess.getoutput(f'cd {repodir} && git log -1')
        self.assertIn('RepoUtil Commit', out)

    def test_push(self):
        # relatively big repo, takes long to clone, maybe create a smaller dummy repo?
        if self.token == 'test':
            raise unittest.SkipTest('Replace yang-catalog-token in the Secrets-Section of the test config')
        push_repo = ru.ModifiableRepoUtil(
            f'https://yang-catalog:{self.token}@github.com/yang-catalog/deployment',
            clone_options={'config_username': 'yang-catalog', 'config_user_email': 'fake@gmail.com'},
        )
        repodir = push_repo.local_dir
        current_tip = push_repo.get_commit_hash()
        status_command = f'cd {repodir} && git status'

        def clean():
            reset_repo = Repo(repodir)
            reset_repo.git.reset('--hard', current_tip)
            reset_repo.git.push(force=True)

        f = open(os.path.join(repodir, 'README.md'), 'a+')
        f.write('This is added to the end of README.md file')
        f.close()

        # add
        push_repo.add_untracked_remove_deleted()
        out = subprocess.getoutput(status_command)
        self.assertTrue(re.search('modified:.*README\\.md', out))

        push_repo.commit_all()
        push_repo.push()
        status = subprocess.getoutput(status_command)
        log = subprocess.getoutput(f'cd {repodir} && git log -1 --decorate=short')
        commit_hash = push_repo.get_commit_hash()
        clean()
        self.assertIn("Your branch is up to date with 'origin/master'.", status)
        self.assertIn('origin', log)
        self.assertNotEqual(commit_hash, current_tip)

    def test_del(self):
        self.assertTrue(os.path.exists(self.repo.local_dir))
        repodir = self.repo.local_dir

        del self.repo
        self.assertFalse(os.path.exists(repodir))


if __name__ == '__main__':
    unittest.main()
