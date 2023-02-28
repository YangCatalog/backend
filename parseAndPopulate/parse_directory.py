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
Python script to start parsing all the yang files. Based on the provided directory and boolean option sdo
(default False) this script will start to look for xml files, or it will start to parse all the yang files in the
directory ignoring all the vendor metadata
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import fnmatch
import glob
import os
import shutil
import time
import typing as t
from configparser import ConfigParser
from logging import Logger

import utility.log as log
from parseAndPopulate.dumper import Dumper
from parseAndPopulate.file_hasher import FileHasher
from parseAndPopulate.groupings import IanaDirectory, SdoDirectory, VendorCapabilities, VendorYangLibrary
from parseAndPopulate.models.directory_paths import DirPaths
from redisConnections.redisConnection import RedisConnection
from utility.create_config import create_config
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.util import parse_name, parse_revision, strip_comments

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME]['args'],
    arglist=None if __name__ == '__main__' else [],
)


def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()) -> tuple[int, int]:
    args = script_conf.args

    config_path = args.config_path
    config = create_config(config_path)
    dir_paths: DirPaths = {
        'log': config.get('Directory-Section', 'logs', fallback='/var/yang/logs'),
        'private': config.get('Web-Section', 'private-directory', fallback='tests/resources/html/private'),
        'yang_models': config.get('Directory-Section', 'yang-models-dir', fallback='tests/resources/yangmodels/yang'),
        'cache': config.get('Directory-Section', 'cache', fallback='tests/resources/cache'),
        'json': args.json_dir,
        'result': args.result_html_dir,
        'save': args.save_file_dir,
    }

    logger = log.get_logger('parse_directory', f'{dir_paths["log"]}/parseAndPopulate.log')

    redis_connection = RedisConnection(config=config)

    start = time.time()
    dumper = Dumper(dir_paths['log'], 'prepare')
    file_hasher = FileHasher(
        'backend_files_modification_hashes',
        dir_paths['cache'],
        args.save_file_hash,
        dir_paths['log'],
    )

    logger.info('Saving all yang files so the save-file-dir')
    name_rev_to_path, path_to_name_rev = save_files(args.dir, dir_paths['save'])
    logger.info('Starting to iterate through files')
    if args.sdo:
        stats = parse_sdo(args.dir, dumper, file_hasher, args.api, dir_paths, path_to_name_rev, logger, config=config)
    else:
        stats = parse_vendor(
            args.dir,
            dumper,
            file_hasher,
            args.api,
            dir_paths,
            name_rev_to_path,
            logger,
            config=config,
            redis_connection=redis_connection,
        )
    dumper.dump_modules(dir_paths['json'])
    dumper.dump_vendors(dir_paths['json'])

    end = time.time()
    logger.info(f'Time taken to parse all the files {int(end - start)} seconds')

    # Dump updated hashes into temporary directory
    if len(file_hasher.updated_hashes) > 0:
        file_hasher.dump_tmp_hashed_files_list(file_hasher.updated_hashes, dir_paths['json'])

    return stats


def save_files(
    search_directory: str,
    save_file_dir: str,
) -> tuple[dict[tuple[str, str], str], dict[str, tuple[str, str]]]:
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
            save_file_path = os.path.join(save_file_dir, f'{name}@{revision}.yang')
            # To construct and save a schema url, we need the original path, module name, and revision.
            # SDO metadata only provides the path, vendor metadata only provides the name and revision.
            # We need mappings both ways to retrieve the missing data.
            name_rev_to_path[name, revision] = yang_file
            path_to_name_rev[yang_file] = name, revision
            if not os.path.exists(save_file_path):
                shutil.copy(yang_file, save_file_path)
    return name_rev_to_path, path_to_name_rev


def parse_sdo(
    search_directory: str,
    dumper: Dumper,
    file_hasher: FileHasher,
    api: bool,
    dir_paths: DirPaths,
    path_to_name_rev: dict,
    logger: Logger,
    config: ConfigParser = create_config(),
) -> tuple[int, int]:
    """Parse all yang modules in an SDO directory."""
    logger.info(f'Parsing SDO directory {search_directory}')
    if os.path.isfile(os.path.join(search_directory, 'yang-parameters.xml')):
        logger.info('Found yang-parameters.xml file, parsing IANA directory')
        grouping = IanaDirectory(search_directory, dumper, file_hasher, api, dir_paths, path_to_name_rev, config=config)
    else:
        grouping = SdoDirectory(search_directory, dumper, file_hasher, api, dir_paths, path_to_name_rev, config=config)
    return grouping.parse_and_load()


def parse_vendor(
    search_directory: str,
    dumper: Dumper,
    file_hasher: FileHasher,
    api: bool,
    dir_paths: DirPaths,
    name_rev_to_path: dict,
    logger: Logger,
    config: ConfigParser = create_config(),
    redis_connection: t.Optional[RedisConnection] = None,
) -> tuple[int, int]:
    """Parse all yang modules in a vendor directory."""
    parsed = 0
    skipped = 0
    redis_connection = redis_connection or RedisConnection(config=config)
    for root, _, files in os.walk(search_directory):
        for basename in files:
            if fnmatch.fnmatch(basename, '*capabilit*.xml'):
                path = os.path.join(root, basename)
                logger.info(f'Found xml metadata file "{path}"')
                grouping = VendorCapabilities(
                    root,
                    path,
                    dumper,
                    file_hasher,
                    api,
                    dir_paths,
                    name_rev_to_path,
                    config=config,
                    redis_connection=redis_connection,
                )
            elif fnmatch.fnmatch(basename, '*ietf-yang-library*.xml'):
                path = os.path.join(root, basename)
                logger.info(f'Found xml metadata file "{path}"')
                grouping = VendorYangLibrary(
                    root,
                    path,
                    dumper,
                    file_hasher,
                    api,
                    dir_paths,
                    name_rev_to_path,
                    config=config,
                    redis_connection=redis_connection,
                )
            else:
                continue
            try:
                dir_parsed, dir_skipped = grouping.parse_and_load()
                parsed += dir_parsed
                skipped += dir_skipped
            except Exception:
                logger.exception(f'Skipping "{path}", error while parsing')
    return parsed, skipped


if __name__ == '__main__':
    main()
