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
from git import Repo
import subprocess

test_repo_dir = '~/work/yang'

def get_repo_dir(repourl, without_git_suffix=False):
	repo_name = os.path.basename(repourl) 
	if repo_name.endswith('.git') and without_git_suffix:
		return repo_name[:-4]
	return repo_name


class TestRepoutil(unittest.TestCase):

	def setUp(self):
		repourl1 = 'https://github.com/stanislav-chlebec/docs'
		repourl2 = 'https://github.com/stanislav-chlebec/docker-kafka'
		repourl3 = 'https://github.com/YangCatalog/backend.git'
		repourl4 = 'https://sergej-testerko:40163869885ca113ce4b7f10d070aaa155b755a3@github.com/XangXatalog/Xackend.XXX' # does not exist
		repourl5 = 'https://sergej-testerko:40163869885ca113ce4b7f10d070aaa155b755a3@github.com/Sergej-Testerko/deployment'

		self.repo_owner1 = 'stanislav-chlebec'
		self.repo_owner2 = 'stanislav-chlebec'
		self.repo_owner3 = 'YangCatalog'
		self.repo_owner4 = 'XangXatalog'
		self.repo_owner5 = 'Sergej-Testerko'

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
		self.repo1.remove()

		self.assertEqual(self.repo1.clone(self.myname, self.myemail), None)  
		localdir = self.repo1.localdir
		self.assertTrue(os.path.exists(localdir))
		self.assertIsNotNone(self.repo1.repo)
		with self.repo1.repo.config_reader() as config:
			self.assertEqual(config.get_value('user','email'), self.myemail)
			self.assertEqual(config.get_value('user','name'), self.myname)

		self.assertEqual(self.repo2.clone(self.myname, self.myemail), None)  
		localdir = self.repo2.localdir
		self.assertTrue(os.path.exists(localdir))
		self.assertIsNotNone(self.repo2.repo)
		with self.repo2.repo.config_reader() as config:
			self.assertEqual(config.get_value('user','email'), self.myemail)
			self.assertEqual(config.get_value('user','name'), self.myname)

		self.assertEqual(self.repo3.clone(self.myname, self.myemail), None)  
		localdir = self.repo3.localdir
		self.assertTrue(os.path.exists(localdir))
		self.assertIsNotNone(self.repo3.repo)
		with self.repo3.repo.config_reader() as config:
			self.assertEqual(config.get_value('user','email'), self.myemail)
			self.assertEqual(config.get_value('user','name'), self.myname)

		with self.assertRaises(GitCommandError):
			self.repo4.clone(self.myname, self.myemail)

		self.repo1.remove()
		self.repo2.remove()
		self.repo3.remove()
		self.repo4.remove()

	def test_get_repo_dir(self):
		self.assertEqual(self.repo1.clone(self.myname, self.myemail), None)  
		self.assertEqual(self.repo2.clone(self.myname, self.myemail), None)  
		self.assertEqual(self.repo3.clone(self.myname, self.myemail), None)  

		repodir1 = self.repo1.get_repo_dir()
		repodir2 = self.repo2.get_repo_dir()
		repodir3 = self.repo3.get_repo_dir()

		#"git clone" would strip the suffix .git while cloning the repo
		#function get_repo_dir simply takes last part of URI
		#this will result in not ommiting the .git extension !!!
		self.assertEqual(repodir1, get_repo_dir(self.repo1.repourl))
		self.assertEqual(repodir2, get_repo_dir(self.repo2.repourl))
		self.assertEqual(repodir3, get_repo_dir(self.repo3.repourl))

		self.repo1.remove()
		self.repo2.remove()
		self.repo3.remove()

	def test_get_repo_owner(self):
		self.assertEqual(self.repo1.get_repo_owner(), self.repo_owner1)
		self.assertEqual(self.repo2.get_repo_owner(), self.repo_owner2)
		self.assertEqual(self.repo3.get_repo_owner(), self.repo_owner3)
		self.assertEqual(self.repo5.get_repo_owner(), self.repo_owner5)

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

		self.repo1.remove()
		self.repo5.remove()
			
	def test_get_commit_hash(self):
		# the repo repo5 is with submodules
		self.assertEqual(self.repo5.clone(self.myname5, self.myemail5), None)  
		repodir25 = self.repo5.localdir + '/'
		self.assertTrue(os.path.isfile(repodir25 + '.gitmodules'))
		
		self.assertEqual(self.repo5.get_commit_hash(), '007fdc8e7d9c6ff70f2c9624c68aa83ef993b45a')
		self.assertEqual(self.repo5.get_commit_hash(None, 'master'), '007fdc8e7d9c6ff70f2c9624c68aa83ef993b45a')
		self.assertEqual(self.repo5.get_commit_hash('backend','tests'), 'd7d499416b443f2e0d7594cad0b13b551d90dd3a')
		self.assertEqual(self.repo5.get_commit_hash('bottle-yang-extractor-validator','tests'), 'd1ec44dbe8995f282355d5d30402c5e6fa13a477')

		self.repo5.remove()

	def test_pull(self):
		# the repo repo5 is with submodules
		self.assertEqual(self.repo5.clone(self.myname5, self.myemail5), None)  
		self.assertEqual(repoutil.pull(self.repo5.localdir), None)

		self.repo5.remove()

	def test_add_all_untracked(self):
		# the repo repo5 is with submodules
		self.assertEqual(self.repo5.clone(self.myname5, self.myemail5), None)
		repodir = self.repo5.localdir
		repo5 = Repo(repodir)

		# let us create a new file
		myfile = "a_new_file"
		f = open(repodir + "/" + myfile,"w+")
		f.write("This is a new file")
		f.close()

		self.assertEqual(myfile, repo5.untracked_files[0])
		self.assertEqual(self.repo5.add_all_untracked(), None)
		self.assertFalse(repo5.untracked_files, "should be empty after succesful adding")
		bashCommand = 'cd ' + repodir  + ' && git status | grep -q "new file:.*' + myfile + '"'
		self.assertEqual(subprocess.call(bashCommand, shell = True), 0)

		# let us modify some file
		myfile = "README.md"
		f = open(repodir + "/" + myfile,"a+")
		f.write("This is added to the end of README.md file")
		f.close()

		self.assertEqual(self.repo5.add_all_untracked(), None)
		bashCommand = 'cd ' + repodir  + ' && git status | grep -q "modified:.*' + myfile + '"'
		self.assertEqual(subprocess.call(bashCommand, shell = True), 0)

		# let us delete some file
		myfile = "LICENSE"
		os.remove(repodir + '/' + myfile)

		self.assertEqual(self.repo5.add_all_untracked(), None)
		bashCommand = 'cd ' + repodir  + ' && git status | grep -q "deleted:.*' + myfile + '"'
		self.assertEqual(subprocess.call(bashCommand, shell = True), 0)

		# let us move some file
		myfile = "docker-compose.yml"
		newdir = "DOK"
		os.mkdir(repodir + '/' + newdir)
		os.rename(repodir + '/' + myfile, repodir + '/' + newdir  + '/' + myfile)

		self.assertEqual(self.repo5.add_all_untracked(), None)
		bashCommand = 'cd ' + repodir  + ' && git status | grep -q "renamed:.*' + myfile + '.*->.*' + newdir + '/' + myfile + '"'
		self.assertEqual(subprocess.call(bashCommand, shell = True), 0)

		self.repo5.remove()

if __name__ == '__main__':
	unittest.main()
