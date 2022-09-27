# Copyright The IETF Trust 2021, All Rights Reserved
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

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

import hashlib
import json
import os
import threading

import pyang
from utility import log

BLOCK_SIZE = 65536  # The size of each read from the file


class FileHasher:
    def __init__(self, file_name: str, cache_dir: str, is_active: bool, log_directory: str):
        """
        The format of the cache file is:
        {
            path: {
                hash: [implementations]
            }
        }

        Arguments:
            :param file_name        (str) name of the file to which the modules hashes are dumped
            :param cache_dir        (str) directory where json file with hashes is saved
            :param is_active        (bool) whether FileHasher is active or not (use hashes to skip module parsing or not)
            :param log_directory    (str) directory where the log file is saved
        """
        self.file_name = file_name
        self.cache_dir = cache_dir
        self.disabled = not is_active
        self.LOGGER = log.get_logger(__name__, os.path.join(log_directory, 'parseAndPopulate.log'))
        self.lock = threading.Lock()
        self.validators_versions_bytes = self.get_versions()
        self.files_hashes = self.load_hashed_files_list()
        self.updated_hashes = {}

    def hash_file(self, path: str) -> str:
        """ Create hash from content of the given file and validators versions.
        Each time either the content of the file or the validator version change,
        the resulting hash will be different.

        Arguments:
            :param path             (str) Full path to the file to be hashed
            :return                 SHA256 hash of the content of the given file
            :rtype                  str
        """
        file_hash = hashlib.sha256()
        try:
            with open(path, 'rb') as f:
                fb = f.read(BLOCK_SIZE)
                while len(fb) > 0:
                    file_hash.update(fb)
                    fb = f.read(BLOCK_SIZE)
        except FileNotFoundError:
            return ''
        file_hash.update(self.validators_versions_bytes)

        return file_hash.hexdigest()

    def load_hashed_files_list(self, path: str = ''):
        """ Load dumped list of files content hashes from .json file.
        Several threads can access this file at once, so locking the file while accessing is necessary.

        Argument:
            :param path  (str) Optional - Full path to the json file with dumped files hashes
        """
        if path == '':
            path = f'{self.cache_dir}/{self.file_name}.json'

        self.lock.acquire()
        try:
            with open(path, 'r') as f:
                hashed_files_list = json.load(f)
                self.LOGGER.info(f'Dictionary of {len(hashed_files_list)} hashes loaded successfully')
        except FileNotFoundError:
            self.LOGGER.error(f'{path} file was not found')
            hashed_files_list = {}
        self.lock.release()

        return hashed_files_list

    def merge_and_dump_hashed_files_list(self, new_hashes: dict, dst_dir: str = ''):
        """ Dumped updated list of files content hashes into .json file.
        Several threads can access this file at once, so locking the file while accessing is necessary.

        Arguments:
            :param files_hashes (dict) Dictionary of the hashes to be dumped
            :param dst_dir      (str) Optional - directory where the .json file with hashes is saved
        """
        dst_dir = self.cache_dir if dst_dir == '' else dst_dir

        # Load existing hashes, merge with new one, then dump all to the .json file
        self.lock.acquire()
        try:
            with open(f'{dst_dir}/{self.file_name}.json', 'r') as f:
                old_hashes = json.load(f)
        except FileNotFoundError:
            self.LOGGER.error(f'{self.file_name}.json file was not found')
            old_hashes = {}

        merged_hashes = old_hashes
        for path in new_hashes:
            file_path_cache = merged_hashes.setdefault(path, {}) # get per path cache
            for hash in new_hashes[path]:
                implementations = file_path_cache.setdefault(hash, []) # get per hash cache
                implementations.extend(new_hashes[path][hash])

        with open(f'{dst_dir}/{self.file_name}.json', 'w') as f:
            json.dump(merged_hashes, f, indent=2, sort_keys=True)
            self.LOGGER.info(f'Dictionary of {len(merged_hashes)} hashes successfully dumped into .json file')
        self.lock.release()

    def dump_tmp_hashed_files_list(self, files_hashes: dict, dst_dir: str = ''):
        """ Dump new hashes into temporary json file.

        Arguments:
            :param files_hashes (dict) Dictionary of the hashes to be dumped
            :param dst_dir      (str) Optional - directory where the .json file with hashes is saved
        """
        dst_dir = self.cache_dir if dst_dir == '' else dst_dir

        with open(os.path.join(dst_dir, 'temp_hashes.json'), 'w') as f:
            json.dump(files_hashes, f, indent=2, sort_keys=True)
            self.LOGGER.info(f'{len(files_hashes)} hashes dumped into temp_hashes.json file')

    def get_versions(self):
        """ Return encoded validators versions dictionary.
        """
        validators = {}
        validators['pyang_version'] = pyang.__version__
        return json.dumps(validators).encode('utf-8')

    def should_parse_sdo_module(self, path: str) -> bool:
        """ Decide whether SDO module at the given path should be parsed or not.
        Check whether file content hash has changed and keep it for the future use.

        Argument:
            :param path     (str) Full path to the file to be hashed
            :rtype           bool
        """
        file_hash = self.hash_file(path)
        if not file_hash:
            return False
        hashes = self.files_hashes.get(path, {})
        if file_hash not in hashes:
            self.updated_hashes.setdefault(path, {})[file_hash] = [] # empty implementations
            return True

        return self.disabled

    def should_parse_vendor_module(self, path: str, implementation_keys: list[str]) -> bool:
        """ Decide whether vendor module at the given path should be parsed or not.
        Check whether file content hash has changed and keep it for the future use.

        Arguments:
            :param path             (str) Full path to the file to be hashed
            :param platform         (str) Name of the platform
            :param software_version (str) Software version
            :rtype                  (bool)
        """
        new_implementation = False
        file_hash = self.hash_file(path)
        if not file_hash:
            return False

        existing_keys = self.files_hashes.get(path, {}).get(file_hash, [])
        for implementation_key in implementation_keys:
            if implementation_key not in existing_keys:
                self.updated_hashes.setdefault(path, {}).setdefault(file_hash, []).append(implementation_key)
                new_implementation = True
        return new_implementation or self.disabled
