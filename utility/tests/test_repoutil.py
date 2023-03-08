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
import unittest

from git.exc import GitCommandError

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

    def test_del(self):
        self.assertTrue(os.path.exists(self.repo.local_dir))
        repodir = self.repo.local_dir

        del self.repo
        self.assertFalse(os.path.exists(repodir))


if __name__ == '__main__':
    unittest.main()
