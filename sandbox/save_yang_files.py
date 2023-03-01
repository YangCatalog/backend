"""
This script needs to be run once before populate.py is used.
All modules copied into the save-file-dir.
"""

import argparse
import json
import os
import shutil

from sandbox import constants
from utility.create_config import create_config
from utility.util import parse_name, parse_revision, strip_comments


def main(directory: str):
    config = create_config()
    cache_dir = config.get('Directory-Section', 'cache')
    save_file_dir = config.get('Directory-Section', 'save-file-dir')

    new_copied_modules_paths = []
    for root, _, files in os.walk(directory):
        abs_root = os.path.abspath(root)
        for file in files:
            path = os.path.join(abs_root, file)
            if not file.endswith('.yang') or os.path.islink(path):
                continue
            with open(path) as f:
                text = f.read()
                text = strip_comments(text)
                name = parse_name(text)
                revision = parse_revision(text)
            filename = f'{name}@{revision}.yang'
            save_file_path = os.path.join(save_file_dir, filename)
            if not os.path.exists(save_file_path):
                shutil.copy(path, save_file_path)
                new_copied_modules_paths.append(save_file_path)

    with open(os.path.join(cache_dir, constants.NEW_COPIED_MODULES_PATHS_FILENAME), 'w') as f:
        json.dump(new_copied_modules_paths, f)


if __name__ == '__main__':
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument(
        'directory',
        type=str,
        help='Directory to search for yang files.',
    )
    args = argument_parser.parse_args()
    main(args.directory)
