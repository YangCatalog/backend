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

__author__ = "Slavomir Mazur"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "slavomir.mazur@pantheon.tech"

import hashlib
import json
import threading

import pyang
from utility import log


class FileHasher:
    def __init__(self, file_name: str, cache_dir: str, is_active: bool, log_directory: str):
        """
        Arguments:
            :param file_name        (str) name of the file to which the modules hashes are dumped
            :param cache_dir        (str) directory where json file with hashes is saved
            :param is_active        (bool) whether FileHasher is active or not (use hashes to skip module parsing or not)
            :param log_directory    (str) directory where the log file is saved
        """
        self.file_name = file_name
        self.cache_dir = cache_dir
        self.is_active = is_active
        self.LOGGER = log.get_logger(__name__, '{}/parseAndPopulate.log'.format(log_directory))
        self.lock = threading.Lock()
        self.validators_versions_bytes = self.get_versions()
        self.files_hashes = self.load_hashed_files_list()
        self.updated_hashes = {}

    def hash_file(self, path: str, additional_data: str = ''):
        """ Create hash from content of the given file and validators versions.
        Each time either the content of the file or the validator version change,
        the resulting hash will be different.

        Arguments:
            :param path             (str) Full path to the file to be hashed
            :param additional_data  (str) Additional data to be included in the hashing process (e.g., platform name)
            :return                 SHA256 hash of the content of the given file
            :rtype                  str
        """
        BLOCK_SIZE = 65536  # The size of each read from the file

        file_hash = hashlib.sha256()
        with open(path, 'rb') as f:
            fb = f.read(BLOCK_SIZE)
            while len(fb) > 0:
                file_hash.update(fb)
                fb = f.read(BLOCK_SIZE)

        file_hash.update(self.validators_versions_bytes)
        if additional_data != '':
            encoded_data = json.dumps(additional_data).encode('utf-8')
            file_hash.update(encoded_data)

        return file_hash.hexdigest()

    def load_hashed_files_list(self, path: str = ''):
        """ Load dumped list of files content hashes from .json file.
        Several threads can access this file at once, so locking the file while accessing is necessary.

        Argument:
            :param path  (str) Optional - Full path to the json file with dumped files hashes
        """
        if path == '':
            path = '{}/{}.json'.format(self.cache_dir, self.file_name)

        self.lock.acquire()
        try:
            with open(path, 'r') as f:
                hashed_files_list = json.load(f)
                self.LOGGER.info('Dictionary of {} hashes loaded successfully'.format(len(hashed_files_list)))
        except FileNotFoundError:
            self.LOGGER.error('{} file was not found'.format(path))
            hashed_files_list = {}
        self.lock.release()

        return hashed_files_list

    def merge_and_dump_hashed_files_list(self, files_hashes: dict, dst_dir: str = ''):
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
            with open('{}/{}.json'.format(dst_dir, self.file_name), 'r') as f:
                hashes_in_file = json.load(f)
        except FileNotFoundError:
            self.LOGGER.error('{}.json file was not found'.format(self.file_name))
            hashes_in_file = {}

        merged_files_hashes = {**hashes_in_file, **files_hashes}

        with open('{}/{}.json'.format(dst_dir, self.file_name), 'w') as f:
            json.dump(merged_files_hashes, f, indent=2, sort_keys=True)
            self.LOGGER.info('Dictionary of {} hashes successfully dumped into .json file'
                             .format(len(merged_files_hashes)))
        self.lock.release()

    def dump_tmp_hashed_files_list(self, files_hashes: dict, dst_dir: str = ''):
        """ Dump new hashes into temporary json file.

        Arguments:
            :param files_hashes (dict) Dictionary of the hashes to be dumped
            :param dst_dir      (str) Optional - directory where the .json file with hashes is saved
        """
        dst_dir = self.cache_dir if dst_dir == '' else dst_dir

        with open('{}/temp_hashes.json'.format(dst_dir), 'w') as f:
            json.dump(files_hashes, f, indent=2, sort_keys=True)
            self.LOGGER.info('{} hashes dumped into temp_hashes.json file'.format(len(files_hashes)))

    def get_versions(self):
        """ Return encoded validators versions dictionary.
        """
        validators = {}
        validators['pyang_version'] = pyang.__version__
        return json.dumps(validators).encode('utf-8')

    def should_parse_sdo_module(self, path: str):
        """ Decide whether SDO module at the given path should be parsed or not.
        Check whether file content hash has changed and keep it for the future use.

        Argument:
            :param path     (str) Full path to the file to be hashed
            :rtype           bool
        """
        hash_changed = False
        file_hash = self.hash_file(path)
        old_file_hash = self.files_hashes.get(path, None)
        if old_file_hash is None or old_file_hash != file_hash:
            self.updated_hashes[path] = file_hash
            hash_changed = True

        return True if not self.is_active else hash_changed

    def should_parse_vendor_module(self, path: str, platform: str):
        """ Decide whether vendor module at the given path should be parsed or not.
        Check whether file content hash has changed and keep it for the future use.

        Arguments:
            :param path        (str) Full path to the file to be hashed
            :param platform    (str) Name of the platform
            :rtype              bool
        """
        hash_changed = False
        file_hash = self.hash_file(path, platform)
        old_file_hash = self.files_hashes.get(path, {})
        old_file_platform_hash = old_file_hash.get(platform, None)

        if old_file_platform_hash is None or old_file_platform_hash != file_hash:
            if self.updated_hashes.get(path) is None:
                self.updated_hashes[path] = {}
            self.updated_hashes[path][platform] = file_hash
            hash_changed = True

        return True if not self.is_active else hash_changed
