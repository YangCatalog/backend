"""
WARNING: this will probably take ages
This script needs to be run once before populate.py is used.
The output is a dictionary of `<name>@<revision>: schema_url` pairs stored in /var/yang/cache/schema_dict.json.
"""

import argparse
import json
import os

from git import InvalidGitRepositoryError, Repo

from utility import yangParser
from utility.create_config import create_config
from utility.staticVariables import github_url, GITHUB_RAW


def construct_schema_url(repo: Repo, path: str) -> str:
    if 'SOL006-' in path:
        suffix = path.split('SOL006-')[-1]
        return 'https://forge.etsi.org/rep/nfv/SOL006/raw/{}'.format(suffix)

    repo_base_url = next(repo.remote('origin').urls).replace(github_url, GITHUB_RAW).removesuffix('.git')
    commit_hash = repo.head.commit.hexsha

    suffix = path.removeprefix(repo.working_tree_dir).strip('/')
    return os.path.join(repo_base_url, commit_hash, suffix)

def main():
    config = create_config()
    cache_dir = config.get('Directory-Section', 'cache')

    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument(
        'directory',
        type=str,
        help='Directory to search for yang files. All yang files must be inside cloned git repositories.'
    )
    args = argument_parser.parse_args()
    schema_dict_path = os.path.join(cache_dir, 'schema_dict.json')
    try:
        with open(schema_dict_path) as f:
            schemas = json.load(f)
    except (FileExistsError, json.JSONDecodeError):
        schemas = {}
    for root, _, files in os.walk(args.directory):
        abs_root = os.path.abspath(root)
        try:
            repo = Repo(abs_root, search_parent_directories=True)

            for file in files:
                if not file.endswith('.yang') or os.path.islink(os.path.join(abs_root, file)):
                    continue
                path = os.path.join(abs_root, file)
                try:
                    yang = yangParser.parse(path)
                except (yangParser.ParseException):
                    print("Couldn't parse {}".format(path))
                    continue
                name = yang.arg
                try:
                    revision = yang.search('revision')[0].arg
                except IndexError:
                    print("Revision not found in {}, falling back to 1970-01-01".format(path))
                    revision = '1970-01-01'
                name_revision = '{}@{}'.format(name, revision)
                schemas[name_revision] = construct_schema_url(repo, path)
        except InvalidGitRepositoryError:
            continue

    with open(schema_dict_path, 'w') as f:
        json.dump(schemas, f)

if __name__ == '__main__':
    main()
