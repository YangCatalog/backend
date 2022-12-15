"""
This script needs to be run once before populate.py is used. It performs 2 tasks.
All modules copied into the save-file-dir.
The output is a dictionary of `<name>@<revision>: schema_url` pairs stored in a schema_dict.json file
inside the cache directory.
"""

import argparse
import json
import os
import shutil

from git import InvalidGitRepositoryError, Repo

from sandbox import constants
from utility.create_config import create_config
from utility.staticVariables import GITHUB_RAW, github_url
from utility.util import parse_name, parse_revision, strip_comments


def construct_schema_url(repo: Repo, path: str) -> str:
    if 'SOL006-' in path:
        suffix = path.split('SOL006-')[-1]
        return f'https://forge.etsi.org/rep/nfv/SOL006/raw/{suffix}'

    repo_base_url = next(repo.remote('origin').urls).replace(github_url, GITHUB_RAW).removesuffix('.git')
    commit_hash = repo.head.commit.hexsha

    suffix = path.removeprefix(repo.working_tree_dir).strip('/')
    return os.path.join(repo_base_url, commit_hash, suffix)


def main(directory: str):
    config = create_config()
    cache_dir = config.get('Directory-Section', 'cache')
    save_file_dir = config.get('Directory-Section', 'save-file-dir')

    schema_dict_path = os.path.join(cache_dir, constants.SCHEMAS_DICT_FILENAME)
    try:
        with open(schema_dict_path) as f:
            schemas = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        schemas = {}
    new_copied_modules_paths = []
    for root, _, files in os.walk(directory):
        abs_root = os.path.abspath(root)
        try:
            repo = Repo(abs_root, search_parent_directories=True)
        except InvalidGitRepositoryError:
            repo = None
        for file in files:
            path = os.path.join(abs_root, file)
            if not file.endswith('.yang') or os.path.islink(path):
                continue
            with open(path) as f:
                text = f.read()
                text = strip_comments(text)
                name = parse_name(text)
                revision = parse_revision(text)
            name_revision = f'{name}@{revision}'
            filename = name_revision + '.yang'
            save_file_path = os.path.join(save_file_dir, filename)
            if not os.path.exists(save_file_path):
                if 'ietf-yang-types' in filename:
                    print(save_file_path)
                shutil.copy(path, save_file_path)
                new_copied_modules_paths.append(save_file_path)
            if repo and (name_revision not in schemas):
                schemas[name_revision] = construct_schema_url(repo, path)

    with open(schema_dict_path, 'w') as f:
        json.dump(schemas, f)
    with open(os.path.join(cache_dir, constants.NEW_COPIED_MODULES_PATHS_FILENAME), 'w') as f:
        json.dump(new_copied_modules_paths, f)


if __name__ == '__main__':
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument(
        'directory',
        type=str,
        help='Directory to search for yang files. All yang files must be inside cloned git repositories.',
    )
    args = argument_parser.parse_args()
    main(args.directory)
