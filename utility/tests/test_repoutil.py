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
from git.exc import GitCommandError
import logging
import configparser

test_repo_dir = '~/work/yang'


def get_repo_dir_without_git_suffix(repourl):
	repo_name = os.path.basename(repourl) 
	if repo_name.endswith('.git'):
		return repo_name[:-4]
	else:
		return repo_name	

class TestRepoutil(unittest.TestCase):

	def setUp(self):
		repourl1 = 'https://github.com/stanislav-chlebec/docs'
		repourl2 = 'https://github.com/stanislav-chlebec/docker-kafka'
		repourl3 = 'https://github.com/YangCatalog/backend.git'
		repourl4 = 'https://sergej-testerko:anabela123456@github.com/XangXatalog/Xackend.XXX' # does not exist
		repourl5 = 'https://sergej-testerko:anabela123456@github.com/Sergej-Testerko/deployment'

		self.repo_owner1 = 'stanislav-chlebec'
		self.repo_owner2 = 'stanislav-chlebec'
		self.repo_owner3 = 'YangCatalog'
		self.repo_owner4 = 'XangXatalog'

		logger = logging.getLogger(__name__)
		f_handler = logging.FileHandler('test_repoutil.log')
		f_handler.setLevel(logging.ERROR)
		f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		f_handler.setFormatter(f_format)
		logger.addHandler(f_handler)

		self.repo1 = RepoUtil(repourl1)
		self.repo2 = RepoUtil(repourl2)
		self.repo3 = RepoUtil(repourl3)
		self.repo4 = RepoUtil(repourl4)
		self.repo5 = RepoUtil(repourl5)

		self.assertEqual(self.repo1.repourl, repourl1)
		self.assertEqual(self.repo2.repourl, repourl2)
		self.assertEqual(self.repo3.repourl, repourl3)

		self.assertEqual(self.repo1.localdir, None)
		self.assertEqual(self.repo2.localdir, None)
		self.assertEqual(self.repo3.localdir, None)

		self.assertEqual(self.repo1.repo, None)
		self.assertEqual(self.repo2.repo, None)
		self.assertEqual(self.repo3.repo, None)

		self.assertEqual(self.repo1.logger, None)
		self.assertEqual(self.repo2.logger, None)
		self.assertEqual(self.repo3.logger, None)

		self.repo1.logger = logger
		self.repo2.logger = logger
		self.repo3.logger = logger
		self.repo4.logger = logger

		self.assertEqual(self.repo1.logger, logger)
		self.assertEqual(self.repo2.logger, logger)
		self.assertEqual(self.repo3.logger, logger)

		self.myname = 'Stanislav Chlebec'
		self.myemail = 'stanislav.chlebec@pantheon.tech'

		self.myname5 = 'Sergej Testerko'
		self.myemail5 = 'sergejtesterko@yandex.com'

	def tearDown(self):
		self.repo1.remove()
		self.repo2.remove()
		self.repo3.remove()
		self.repo4.remove()
		#self.repo5.remove()

	def test_remove(self):

		self.assertEqual(self.repo1.clone(self.myname, self.myemail), None)  
		self.assertTrue(os.path.exists(self.repo1.localdir))
		dir_be_removed = self.repo1.localdir

		self.assertEqual(self.repo1.remove(), None)  
		self.assertEqual(self.repo1.localdir, None)
		self.assertEqual(self.repo1.repo, None)
		self.assertFalse(os.path.exists(dir_be_removed))
		
		# try to remove already removed repo
		self.assertEqual(self.repo1.remove(), None)  

	def test_clone(self):

		self.assertRaises(TypeError, self.repo1.clone, 1)

		self.assertEqual(self.repo1.clone(self.myname, self.myemail), None)  
		localdir = self.repo1.localdir
		self.assertTrue(os.path.exists(localdir))
		self.assertIsNotNone(self.repo1.repo)
		with self.repo1.repo.config_reader() as config:
			self.assertEqual(config.get_value('user','email'), self.myemail)
			self.assertEqual(config.get_value('user','name'), self.myname)
		#print('Repo1 cloned into: ' + self.repo1.localdir)

		self.assertEqual(self.repo2.clone(self.myname, self.myemail), None)  
		localdir = self.repo2.localdir
		self.assertTrue(os.path.exists(localdir))
		self.assertIsNotNone(self.repo2.repo)
		with self.repo2.repo.config_reader() as config:
			self.assertEqual(config.get_value('user','email'), self.myemail)
			self.assertEqual(config.get_value('user','name'), self.myname)
		#print('Repo2 cloned into: ' + self.repo2.localdir)

		self.assertEqual(self.repo3.clone(self.myname, self.myemail), None)  
		localdir = self.repo3.localdir
		self.assertTrue(os.path.exists(localdir))
		self.assertIsNotNone(self.repo3.repo)
		with self.repo3.repo.config_reader() as config:
			self.assertEqual(config.get_value('user','email'), self.myemail)
			self.assertEqual(config.get_value('user','name'), self.myname)
		#print('Repo3 cloned into: ' + self.repo3.localdir)

		with self.assertRaises(GitCommandError):
			self.repo4.clone(self.myname, self.myemail)


	def test_get_repo_dir(self):

		self.assertEqual(self.repo1.clone(self.myname, self.myemail), None)  
		self.assertEqual(self.repo2.clone(self.myname, self.myemail), None)  
		self.assertEqual(self.repo3.clone(self.myname, self.myemail), None)  

		repodir1 = self.repo1.get_repo_dir()
		repodir2 = self.repo2.get_repo_dir()
		repodir3 = self.repo3.get_repo_dir()

		msg = 'git clone would strip the suffix .git while cloning the repo'
		self.assertEqual(repodir1, get_repo_dir_without_git_suffix(self.repo1.repourl), msg)
		self.assertEqual(repodir2, get_repo_dir_without_git_suffix(self.repo2.repourl), msg)
		self.assertEqual(repodir3, get_repo_dir_without_git_suffix(self.repo3.repourl), msg)

		repodir21 = self.repo1.localdir + '/' + repodir1
		repodir22 = self.repo2.localdir + '/' + repodir2
		repodir23 = self.repo3.localdir + '/' + repodir3

		msg = 'Folder does not exist: ' 
		self.assertTrue(os.path.exists(repodir21), msg + repodir21)
		self.assertTrue(os.path.exists(repodir22), msg + repodir22)
		self.assertTrue(os.path.exists(repodir23), msg + repodir23)
		
		#print('Repo1 dir:' + self.repo1.localdir + '/' + repodir1)
		#print('Repo2 dir:' + self.repo2.localdir + '/' + repodir2)
		#print('Repo3 dir:' + self.repo3.localdir + '/' + repodir3)

	def test_get_repo_owner(self):

		self.assertEqual(self.repo1.get_repo_owner(), self.repo_owner1)
		self.assertEqual(self.repo2.get_repo_owner(), self.repo_owner2)
		self.assertEqual(self.repo3.get_repo_owner(), self.repo_owner3)


	def test_updateSubmodule(self):

		# repo without submodules
		self.assertEqual(self.repo1.clone(self.myname, self.myemail), None)  
		self.assertEqual(self.repo1.updateSubmodule(), None)  
		self.assertEqual(self.repo1.updateSubmodule(True, True), None)  
		self.assertEqual(self.repo1.updateSubmodule(False, True), None)  
		self.assertEqual(self.repo1.updateSubmodule(True, False), None)  
		self.assertEqual(self.repo1.updateSubmodule(False, False), None)  
		
		# the repo repo5 is with submodules
		self.assertEqual(self.repo5.clone(self.myname5, self.myemail5), None)  
		repodir25 = self.repo5.localdir + '/'
		self.assertTrue(os.path.isfile(repodir25 + '.gitmodules'))

		config = configparser.ConfigParser()
		config.read(repodir25 + '.gitmodules')
		# use rmdir to ascertain that submodules' folders are present and empty
		for module in config.sections():
			self.assertTrue(os.path.exists(repodir25 + config[module]['path']), repodir25)
			os.rmdir(repodir25 + config[module]['path'])
		# recreate previously deleted submodules' folders
		for module in config.sections():
			self.assertFalse(os.path.exists(repodir25 + config[module]['path']), repodir25)
			os.mkdir(repodir25 + config[module]['path'])
			self.assertTrue(os.path.exists(repodir25 + config[module]['path']), repodir25)

		# Init = False; should not update submodules
		self.assertEqual(self.repo5.updateSubmodule(True, False), None)  
		self.assertEqual(self.repo5.updateSubmodule(False, False), None)  

		# use rmdir to ascertain that submodules' folders are present and empty
		for module in config.sections():
			self.assertTrue(os.path.exists(repodir25 + config[module]['path']), repodir25)
			os.rmdir(repodir25 + config[module]['path'])
		# recreate previously deleted submodules' folders
		for module in config.sections():
			self.assertFalse(os.path.exists(repodir25 + config[module]['path']), repodir25)
			os.mkdir(repodir25 + config[module]['path'])
			self.assertTrue(os.path.exists(repodir25 + config[module]['path']), repodir25)

		# the key test - how updateSubmodule works ...
		self.assertEqual(self.repo5.updateSubmodule(), None)  

		# use rmdir to ascetain that after update the submodules' folders are present and contains git repos - it is expected that rmdir would fail if it is applied on non empty folder
		for module in config.sections():
			self.assertTrue(os.path.exists(repodir25 + config[module]['path']), repodir25)
			with self.assertRaises(OSError):
				os.rmdir(repodir25 + config[module]['path'])

			self.assertTrue(repodir25 + config[module]['path'] + '/.git')

		self.assertEqual(self.repo5.updateSubmodule(True, True), None)  
		self.assertEqual(self.repo5.updateSubmodule(False, True), None)  
			
	def test_get_commit_hash(self):
		# the repo repo5 is with submodules
		self.assertEqual(self.repo5.clone(self.myname5, self.myemail5), None)  
		repodir25 = self.repo5.localdir + '/'
		self.assertTrue(os.path.isfile(repodir25 + '.gitmodules'))
		
		self.assertEqual(self.repo5.get_commit_hash(), '007fdc8e7d9c6ff70f2c9624c68aa83ef993b45a')
		self.assertEqual(self.repo5.get_commit_hash(None, 'master'), '007fdc8e7d9c6ff70f2c9624c68aa83ef993b45a')
		self.assertEqual(self.repo5.get_commit_hash('backend','master'), 'd1196aa44777fea39890a453d676a8775f4b53dc')
		self.assertEqual(self.repo5.get_commit_hash('bottle-yang-extractor-validator','master'), '902b3ce35694e71a9b87f00375300e6df5e1e399')

	def test_pull(self):

		# the repo repo5 is with submodules
		self.assertEqual(self.repo5.clone(self.myname5, self.myemail5), None)  
		self.assertEqual(repoutil.pull(self.repo5.localdir), None)

if __name__ == '__main__':
	unittest.main()
