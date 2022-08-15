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

"""
Python script to start parsing all the yang files.
Based on the provided directory and boolean option
sdo (default False) this script will start to look
for xml files or it will start to parse all the yang
files in the directory ignoring all the vendor metadata
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import glob
from logging import Logger
import os
import shutil
import time
import typing as t

import utility.log as log
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.util import find_files, parse_name, parse_revision, strip_comments

from parseAndPopulate.dir_paths import DirPaths
from parseAndPopulate.dumper import Dumper
from parseAndPopulate.file_hasher import FileHasher
from parseAndPopulate.groupings import (IanaDirectory, SdoDirectory,
                                        VendorCapabilities, VendorYangLibrary)


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'Parse modules on given directory and generate json with module metadata that can be populated' \
               ' to ConfD/Redis database.'
        args: t.List[Arg] = [
            {
                'flag': '--dir',
                'help': 'Set dir where to look for hello message xml files or yang files if using "sdo" option',
                'type': str,
                'default': '/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC'
            },
            {
                'flag': '--save-file-hash',
                'help': 'if True then it will check if content of the file changed '
                        '(based on hash values) and it will skip parsing if nothing changed.',
                'action': 'store_true',
                'default': False
            },
            {
                'flag': '--api',
                'help': 'If request came from api',
                'action': 'store_true',
                'default': False
            },
            {
                'flag': '--sdo',
                'help': 'If we are processing sdo or vendor yang modules',
                'action': 'store_true',
                'default': False
            },
            {
                'flag': '--json-dir',
                'help': 'Directory where json files to populate ConfD/Redis will be stored',
                'type': str,
                'default': '/var/yang/tmp/'
            },
            {
                'flag': '--result-html-dir',
                'help': 'Set dir where to write html compilation result files',
                'type': str,
                'default': '/usr/share/nginx/html/results'
            },
            {
                'flag': '--save-file-dir',
                'help': 'Directory where the yang file will be saved',
                'type': str,
                'default': '/var/yang/all_modules'
            },
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH']
            },
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args

    config_path = args.config_path
    config = create_config(config_path)
    dir_paths: DirPaths = {
        'log': config.get('Directory-Section', 'logs', fallback='/var/yang/logs'),
        'private': config.get('Web-Section', 'private-directory', fallback='tests/resources/html/private'),
        'yang_models': config.get('Directory-Section', 'yang-models-dir', fallback='tests/resources/yangmodels/yang'),
        'cache': config.get('Directory-Section', 'cache', fallback='tests/resources/cache'),
        'json': args.json_dir,
        'result': args.result_html_dir,
        'save': args.save_file_dir
    }

    LOGGER = log.get_logger('parse_directory', '{}/parseAndPopulate.log'.format(dir_paths['log']))

    start = time.time()
    dumper = Dumper(dir_paths['log'], 'prepare')
    file_hasher = FileHasher('backend_files_modification_hashes', dir_paths['cache'],
                            args.save_file_hash, dir_paths['log'])

    LOGGER.info('Saving all yang files so the save-file-dir')
    name_rev_to_path, path_to_name_rev = save_files(args.dir, dir_paths['save'])
    LOGGER.info('Starting to iterate through files')
    if args.sdo:
        parse_sdo(args.dir, dumper, file_hasher, args.api, dir_paths, path_to_name_rev, LOGGER)
    else:
        parse_vendor(args.dir, dumper, file_hasher, args.api, dir_paths, name_rev_to_path, LOGGER)
    dumper.dump_modules(dir_paths['json'])
    dumper.dump_vendors(dir_paths['json'])

    end = time.time()
    LOGGER.info('Time taken to parse all the files {} seconds'.format(int(end - start)))

    # Dump updated hashes into temporary directory
    if len(file_hasher.updated_hashes) > 0:
        file_hasher.dump_tmp_hashed_files_list(file_hasher.updated_hashes, dir_paths['json'])


def save_files(search_directory: str, save_file_dir: str) -> t.Tuple[t.Dict[str, str], t.Dict[str, str]]:
    """
    Copy all found yang files to the save_file_dir.
    Return dicts with data containing the original locations of the files,
    which is later needed for parsing.

    Arguments:
        :param search_directory                         (str) Directory to process
        :param save_file_dir                            (str) Directory to save yang files to
        :return (name_rev_to_path, path_to_name_rev)    (Tuple[Dict[str, str], Dict[str, str]])
            name_rev_to_path: needed by parse_vendor()
            path_to_name_rev: needed by parse_sdo()
    """
    name_rev_to_path = {}
    path_to_name_rev = {}
    for yang_file in glob.glob(os.path.join(search_directory, '**/*.yang'), recursive=True):
        with open(yang_file) as f:
            text = f.read()
            text = strip_comments(text)
            name = parse_name(text)
            revision = parse_revision(text)
            save_file_path = os.path.join(save_file_dir, '{}@{}.yang'.format(name, revision))
            # To construct and save a schema url, we need the original path, module name, and revision.
            # SDO metadata only provides the path, vendor metadata only provides the name and revision.
            # We need mappings both ways to retrieve the missing data.
            name_rev_to_path[name, revision] = yang_file
            path_to_name_rev[yang_file] = name, revision
            if not os.path.exists(save_file_path):
                shutil.copy(yang_file, save_file_path)
    return name_rev_to_path, path_to_name_rev


def parse_sdo(search_directory: str, dumper: Dumper, file_hasher: FileHasher, api: bool,
              dir_paths: DirPaths, path_to_name_rev: dict, logger: Logger):
    """Parse all yang modules in an SDO directory."""
    logger.info('Parsing SDO directory {}'.format(search_directory))
    if os.path.isfile(os.path.join(search_directory, 'yang-parameters.xml')):
        logger.info('Found yang-parameters.xml file, parsing IANA directory')
        grouping = IanaDirectory(search_directory, dumper, file_hasher, api, dir_paths, path_to_name_rev)
    else:
        grouping = SdoDirectory(search_directory, dumper, file_hasher, api, dir_paths, path_to_name_rev)
    grouping.parse_and_load()


def parse_vendor(search_directory: str, dumper: Dumper, file_hasher: FileHasher, api: bool,
                 dir_paths: DirPaths, name_rev_to_path: dict, logger: Logger):
    """Parse all yang modules in a vendor directory."""
    for pattern in ['*capabilit*.xml', '*ietf-yang-library*.xml']:
        for root, basename in find_files(search_directory, pattern):
            filename = os.path.join(root, basename)
            logger.info('Found xml metadata file {}'.format(filename))
            if pattern == '*capabilit*.xml':
                grouping = VendorCapabilities(root, filename, dumper, file_hasher, api, dir_paths, name_rev_to_path)
            else:
                grouping = VendorYangLibrary(root, filename, dumper, file_hasher, api, dir_paths, name_rev_to_path)
            try:
                grouping.parse_and_load()
            except Exception:
                logger.exception('Skipping {}, error while parsing'.format(filename))


if __name__ == '__main__':
    main()
