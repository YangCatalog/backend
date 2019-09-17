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

import unittest
import repoutil
from repoutil import RepoUtil
import os

test_repo_dir = '~/work/yang'


class TestRepoutil(unittest.TestCase):

	def test_remove(self):
		repo1 = RepoUtil('https://github.com/stanislav-chlebec/docs')

		result = repo1.clone('Stanislav Chlebec', 'stanislav.chlebec@pantheon.tech')
		self.assertEqual(result, None)
		print(repo1.localdir + '/' + repo1.get_repo_dir())
		localdir = repo1.localdir
		self.assertTrue(os.path.exists(localdir))

		result = repo1.remove() 
		self.assertEqual(result, None)
		self.assertEqual(repo1.localdir, None)
		self.assertEqual(repo1.repo, None)
		self.assertFalse(os.path.exists(localdir))
		

	def test_clone(self):
		repo1 = RepoUtil('https://github.com/stanislav-chlebec/docs')
		repo2 = RepoUtil('https://github.com/stanislav-chlebec/docker-kafka')
		repo3 = RepoUtil('https://github.com/YangCatalog/backend.git')

		#repo1.clone(self)
		#TypeError: decoding to str: need a bytes-like object, NoneType found
		#self.assertRaises(TypeError, repo1.clone)
		#with self.assertRaises(TypeError):
		#	repo1.clone()
	
		#self.assertRaises(TypeError, repo1.clone, 'stanislav.chlebec@pantheon.tech', 'Stanislav Chlebec')

		self.assertRaises(TypeError, repo1.clone, 1)

		result = repo1.clone('Stanislav Chlebec', 'stanislav.chlebec@pantheon.tech')
		self.assertEqual(result, None)
		print(repo1.localdir + '/' + repo1.get_repo_dir())
		localdir = repo1.localdir
		self.assertTrue(os.path.exists(localdir))

		result = repo2.clone()
		#result = repo2.clone('Stanislav Chlebec', 'stanislav.chlebec@pantheon.tech')
		self.assertEqual(result, None)
		print(repo2.localdir + '/' + repo2.get_repo_dir())
		# NOT EXPECTED.... 
		localdir = repo2.localdir
		self.assertTrue(os.path.exists(localdir))

		result = repo3.clone()
		#result = repo3.clone('Stanislav Chlebec', 'stanislav.chlebec@pantheon.tech')
		self.assertEqual(result, None)
		print(repo3.localdir + '/' + repo3.get_repo_dir())
		# NOT EXPECTED.... 
		localdir = repo3.localdir
		self.assertTrue(os.path.exists(localdir))

	def test_get_repo_dir(self):
		repo1 = RepoUtil('https://github.com/stanislav-chlebec/docs')
		repo2 = RepoUtil('https://github.com/stanislav-chlebec/docker-kafka')
		repo3 = RepoUtil('https://github.com/YangCatalog/backend.git')
		
		self.assertEqual(repo1.get_repo_dir(), 'docs')
		self.assertEqual(repo2.get_repo_dir(), 'docker-kafka')
		self.assertEqual(repo3.get_repo_dir(), 'backend.git')

		repo1.repourl = 'https://github.com/stanislav-chlebec/docker-kafka'
		repo2.repourl = 'https://github.com/YangCatalog/backend.git'
		repo3.repourl = 'https://github.com/stanislav-chlebec/docs'

		self.assertEqual(repo1.get_repo_dir(), 'docker-kafka')
		self.assertEqual(repo2.get_repo_dir(), 'backend.git')
		self.assertEqual(repo3.get_repo_dir(), 'docs')

	def test_get_repo_owner(self):
		repo1 = RepoUtil('https://github.com/stanislav-chlebec/docs')
		repo2 = RepoUtil('https://github.com/stanislav-chlebec/docker-kafka')
		repo3 = RepoUtil('https://github.com/YangCatalog/backend.git')
		
		self.assertEqual(repo1.get_repo_owner(), 'stanislav-chlebec')
		self.assertEqual(repo2.get_repo_owner(), 'stanislav-chlebec')
		self.assertEqual(repo3.get_repo_owner(), 'YangCatalog')

		repo1.repourl = 'https://github.com/stanislav-chlebec/docker-kafka'
		repo2.repourl = 'https://github.com/YangCatalog/backend.git'
		repo3.repourl = 'https://github.com/stanislav-chlebec/docs'

		self.assertEqual(repo1.get_repo_owner(), 'stanislav-chlebec')
		self.assertEqual(repo2.get_repo_owner(), 'YangCatalog')
		self.assertEqual(repo3.get_repo_owner(), 'stanislav-chlebec')

	def test_pull(self):
		result = repoutil.pull(test_repo_dir)
		self.assertEqual(result, None)
		#self.assertEqual(result, 1)
		# here should I test if 'git status' is outputting something like 'no update'
		# also I need to check submodules ....
		# test cases when pull failes


	def pomoc():
		pass
#(stano) stanislav@stanislav-VirtualBox:/tmp/tmpppssnx29/docs$ git status
#On branch master
#Your branch is up to date with 'origin/master'.
#
#nothing to commit, working tree clean


if __name__ == '__main__':
	unittest.main()
