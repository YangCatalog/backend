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

__author__ = "Stanislav Chlebec"
__copyright__ = "Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "stanislav.chlebec@pantheon.tech"

import logging
import os
import re
import subprocess
import unittest

from git import Repo
from git.exc import GitCommandError

import utility.repoutil as ru
from utility.create_config import create_config


class TestRepoutil(unittest.TestCase):

    def setUp(self):
        repourl = 'https://github.com/yang-catalog/test'
        self.repo_owner = 'yang-catalog'

        logger = logging.getLogger(__name__)
        f_handler = logging.FileHandler('test_repoutil.log')
        f_handler.setLevel(logging.ERROR)
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

        self.repo = ru.RepoUtil(repourl)

        self.assertEqual(self.repo.url, repourl)
        self.assertEqual(self.repo.localdir, None)
        self.assertEqual(self.repo.repo, None)
        self.assertEqual(self.repo.logger, None)

        self.repo.logger = logger

        self.myname = 'yang-catalog'
        self.myemail = 'fake@gmail.com'

        if os.environ.get('GITHUB_ACTIONS'):
            self.token = os.environ['TOKEN']
        else:
            self.token = create_config().get('Secrets-Section', 'yang-catalog-token')

    def tearDown(self):
        self.repo.remove()

    def test_pull(self):
        self.repo.clone(self.myname, self.myemail)
        ru.pull(self.repo.localdir)

    def test_load(self):
        self.repo.clone(self.myname, self.myemail)
        repo = ru.load(self.repo.localdir, self.repo.url)
        if repo:
            self.addCleanup(repo.remove)

        self.assertEqual(repo.url, self.repo.url)

    def test_get_repo_dir(self):
        self.repo.clone(self.myname, self.myemail)

        self.assertEqual(self.repo.get_repo_dir(), 'test')

    def test_get_commit_hash(self):
        self.repo.clone(self.myname, self.myemail)

        self.assertEqual(self.repo.get_commit_hash(), '0d8d5a76cdd4cc2a9e9709f6acece6d57c0b06ea')
        self.assertEqual(self.repo.get_commit_hash(branch='test'), '971423d605268bd7b38c5153c72ff12bfa408f1d')
        self.assertEqual(self.repo.get_commit_hash('subrepo','master'), 'de04507eaba334bfdad41ac75a2044d9d63922ee')

    def test_get_repo_owner(self):
        self.assertEqual(self.repo.get_repo_owner(), 'yang-catalog')

    def test_clone(self):
        self.repo.clone(self.myname, self.myemail)
        localdir = self.repo.localdir

        self.assertTrue(os.path.exists(localdir))
        self.assertIsNotNone(self.repo.repo)
        with self.repo.repo.config_reader() as config:
            self.assertEqual(config.get_value('user','email'), self.myemail)
            self.assertEqual(config.get_value('user','name'), self.myname)
        self.repo.remove()

    def test_clone_invalid_url(self):
        repo = ru.RepoUtil('https://github.com/yang-catalog/fake')

        with self.assertRaises(GitCommandError):
            repo.clone(self.myname, self.myemail)
        repo.remove()

    def test_update_submodule(self):
        self.repo.clone(self.myname, self.myemail)

        self.assertTrue(os.path.isfile(os.path.join(self.repo.localdir, '.gitmodules')))
        # init = False should not update submodules
        self.repo.update_submodule(True, False)
        subdir = os.path.join(self.repo.localdir, 'subrepo')
        self.assertTrue(os.path.isdir(subdir))
        self.assertFalse(os.listdir(subdir))
        self.repo.update_submodule()
        self.assertTrue(os.path.isfile(os.path.join(subdir, 'README.md')))

    def test_add_untracked_remove_deleted(self):
        self.repo.clone(self.myname, self.myemail)
        repodir = self.repo.localdir
        repo = Repo(repodir)
        status_command = 'cd {} && git status'.format(repodir)

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
        f = open(file,'a+')
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
        self.repo.clone(self.myname, self.myemail)
        repodir = self.repo.localdir
        status_command = 'cd {} && git status'.format(repodir)

        file = os.path.join(repodir, 'README.md')
        f = open(file,'a+')
        f.write('test')
        f.close()

        self.repo.add_untracked_remove_deleted()
        self.repo.commit_all()
        out = subprocess.getoutput(status_command)
        self.assertIn("Your branch is ahead of 'origin/master' by 1 commit.", out)
        out = subprocess.getoutput('cd {} && git log -1'.format(repodir))
        self.assertIn('RepoUtil Commit', out)

    def test_push(self):
        # relatively big repo, takes long to clone, maybe create a smaller dummy repo?
        if self.token == 'test':
            raise unittest.SkipTest('Replace yang-catalog-token in the Secrets-Section of the test config')
        push_repo = ru.RepoUtil('https://yang-catalog:{}@github.com/yang-catalog/deployment'.format(self.token))
        push_repo.clone('yang-catalog', 'fake@gmail.com')
        self.addCleanup(push_repo.remove)
        repodir = push_repo.localdir
        current_tip = push_repo.get_commit_hash()
        status_command = 'cd {} && git status'.format(repodir)

        def clean():
            reset_repo = Repo(repodir)
            reset_repo.git.reset('--hard',current_tip)
            reset_repo.git.push(force=True)

        self.addCleanup(clean)

        f = open(os.path.join(repodir, 'README.md'),'a+')
        f.write('This is added to the end of README.md file')
        f.close()

        # add
        push_repo.add_untracked_remove_deleted()
        out = subprocess.getoutput(status_command)
        self.assertTrue(re.search('modified:.*README\\.md', out))

        push_repo.commit_all()
        push_repo.push()
        out = subprocess.getoutput(status_command)
        self.assertIn("Your branch is up to date with 'origin/master'.", out)
        out = subprocess.getoutput('cd {} && git log -1 --decorate=short'.format(repodir))
        self.assertIn('origin', out)
        self.assertNotEqual(push_repo.get_commit_hash(), current_tip)

    def test_remove(self):
        self.repo.clone(self.myname, self.myemail)
        self.assertTrue(os.path.exists(self.repo.localdir))
        repodir = self.repo.localdir

        self.repo.remove()
        self.assertEqual(self.repo.localdir, None)
        self.assertEqual(self.repo.repo, None)
        self.assertFalse(os.path.exists(repodir))

    def test_remove_twice(self):
        self.repo.clone(self.myname, self.myemail)
        self.repo.remove()
        self.repo.remove()

if __name__ == '__main__':
    unittest.main()
