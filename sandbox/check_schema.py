""" This script loops through each module twice - two phases.
Phase I - Loop through the modules and check whether
          there is a 'master' string in the schema and also that if it is still available.
          Store available and unavailable schemas for phase II - to avoid making duplicate requests.
Phase II - Loop through the modules and check whether
           there is a 'master' string in the dependencies, dependents and submodules schemas.
           Store available and unavailable schemas
           so there will be no need to make a request for each single schema.
Patch request to ConfD request is made for each module that has been modified.
Also, reload-cache is called after each phase.
Finally, unavailable schemas are dumped into JSON file.
"""
import json
import os.path

import requests

import utility.log as log
from utility import repoutil
from utility.confdService import ConfdService
from utility.create_config import create_config
from utility.fetch_modules import fetch_modules
from utility.staticVariables import GITHUB_RAW, github_url
from utility.util import parse_revision, strip_comments


def get_repo_owner_name(schema: str):
    schema_part = schema.split(GITHUB_RAW)[1]
    repo_owner = schema_part.split('/')[1]
    repo_name = schema_part.split('/')[2]

    return repo_owner, repo_name


def get_branch_from_schema(schema: str):
    splitted_schema = schema.split('/')
    branch = splitted_schema[5]  # NBSP5 is the position of the hash in URL path

    return branch


def get_available_commit_hash(module: dict, commit_hash_list: list) -> str:
    """Return the hash of a commit which contains the specified revision of a module.

    Arguments:
        :param module               (dict) dictionary with the module's information
        :param commit_hash_list     (list) a list of commit hashes to try
        :return                     (str) The first matching commit hash out of the list.
            If there are no matches, an empty string is returned."""
    name = module.get('name')
    schema = module.get('schema', '')
    revision = module.get('revision')

    branch = get_branch_from_schema(schema)

    available_commit_hash = ''
    for commit_hash in commit_hash_list:
        new_schema = schema.replace(branch, commit_hash)
        if new_schema in requests_done:
            continue
        requests_done.append(new_schema)
        response = requests.get(new_schema)
        if response.status_code != 200:
            continue
        module_text = response.text
        module_revision = parse_revision(strip_comments(module_text))
        key = f'{name}@{module_revision}'
        available_schemas[key] = new_schema
        if revision == module_revision:
            available_commit_hash = commit_hash
            break

    return available_commit_hash


def check_schema_availability(module: dict) -> str:
    """Check if the module's schema can be retrieved from GitHub."""
    schema = module.get('schema', '')
    repo_owner, repo_name = get_repo_owner_name(schema)
    repo_owner_name = f'{repo_owner}/{repo_name}'
    commit_hash_list = commit_hash_history.get(repo_owner_name, [])

    if '/master/' in schema:
        available_commit_hash = get_available_commit_hash(module, commit_hash_list)
    else:
        response = requests.head(schema)
        if response.status_code == 200:
            available_commit_hash = get_branch_from_schema(schema)
        else:
            available_commit_hash = get_available_commit_hash(module, commit_hash_list)

    return available_commit_hash


def get_commit_hash_history(module: dict):
    """Try to get list of commit hashes of master branch for each Git repository."""
    # Get repo owner and name
    schema = module.get('schema', '')
    repo_owner, repo_name = get_repo_owner_name(schema)
    repo_owner_name = f'{repo_owner}/{repo_name}'

    commit_hash = commit_hash_history.get(repo_owner_name, None)

    # Clone repo to get the commit hashes history for repository
    if commit_hash is None:
        repo_url = f'{github_url}/{repo_owner}/{repo_name}'
        LOGGER.info(f'Cloning repo from {repo_url}')
        repo = repoutil.ModifiableRepoUtil(repo_url)

        # Get list of all historic hashes
        commit_hash_history[repo_owner_name] = [commit.hexsha for commit in repo.repo.iter_commits('master')]


def __print_patch_response(key: str, response):
    message = f'Module {key} updated with code {response.status_code}'
    if response.text != '':
        message = f'{message} and text {response.text}'
    LOGGER.info(message)


if __name__ == '__main__':
    config = create_config()
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='admin admin').strip('"').split()
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    LOGGER = log.get_logger('sandbox', os.path.join(log_directory, 'sandbox.log'))
    confdService = ConfdService()

    # GET all the existing modules of Yangcatalog
    LOGGER.info('Fetching all of the modules from API')
    all_existing_modules = fetch_modules(LOGGER, config=config)

    ###
    # PHASE I - Check the schema of each module
    ###
    updated_schemas = 0
    unavailable_schemas = {}
    available_schemas = {}
    requests_done = []
    commit_hash_history = {}
    for module in all_existing_modules:
        update = False
        key = f'{module.get("name")}@{module.get("revision")}'
        schema = module.get('schema')

        if key in unavailable_schemas:
            LOGGER.warning(f'Skipping module {key} - schema unavailable')
            continue
        if schema is None:
            unavailable_schemas[key] = ''
            continue
        try:
            available_commit_hash = get_branch_from_schema(schema)
            get_commit_hash_history(module)

            LOGGER.debug(f'Checking schema for module {key}')
            if key in available_schemas:
                schema_available = get_branch_from_schema(available_schemas[key])
            else:
                schema_available = check_schema_availability(module)

            if schema_available == '':
                unavailable_schemas[key] = schema
                LOGGER.warning(f'Schema not available: {schema}')
            elif schema_available == available_commit_hash:
                if key not in available_schemas:
                    available_schemas[key] = schema
            else:
                new_schema = schema.replace(f'/{available_commit_hash}/', f'/{schema_available}/')
                module['schema'] = new_schema
                updated_schemas += 1

                # Make patch request to ConfD to update schema
                response = confdService.patch_module(module)

                __print_patch_response(key, response)
        except Exception:
            LOGGER.exception(f'Problem with module {key}')
            unavailable_schemas[key] = schema
            continue

    # Reload cache after checking each scheme
    if updated_schemas > 0:
        url = f'{yangcatalog_api_prefix}/load-cache'
        response = requests.post(url, None, auth=(credentials[0], credentials[1]))
        LOGGER.info(f'Cache loaded with status {response.status_code}')

    LOGGER.info(f'Number of modules checked: {len(all_existing_modules)}')
    LOGGER.info(f'Number of unavailable schemas: {len(unavailable_schemas)}')
    LOGGER.info(f'Number of updated schemas: {updated_schemas}')

    # Dump unavailable schemas to JSON file
    with open(os.path.join(temp_dir, 'unavailable_schemas.json'), 'w') as f:
        json.dump(unavailable_schemas, f, indent=2, sort_keys=True)

    ###
    # PHASE II - Check the schema in dependencies, dependets and submodules for each module
    ###
    updated_modules = {}
    master_in_dependencies = 0

    for module in all_existing_modules:
        key = f'{module.get("name")}@{module.get("revision")}'
        dependencies = module.get('dependencies', [])
        dependents = module.get('dependents', [])
        submodules = module.get('submodule', [])
        updated = False

        LOGGER.debug(f'Checking dependents and submodules for module {key}')

        for dependency in dependencies:
            dependency_schema = dependency.get('schema', '')
            if '/master/' in dependency_schema:
                master_in_dependencies += 1

        # Check the schema path of each dependent
        for dependent in dependents:
            dependent_schema = dependent.get('schema', '')
            dependent_key = f'{dependent.get("name")}@{dependent.get("revision")}'
            try:
                available_commit_hash = get_branch_from_schema(dependent_schema)
                get_commit_hash_history(module)

                if dependent_key in unavailable_schemas:
                    LOGGER.warning(f'Skipping dependent {dependent_key} - schema unavailable')
                    continue

                if dependent_key in available_schemas:
                    schema_available = get_branch_from_schema(available_schemas[dependent_key])
                else:
                    schema_available = check_schema_availability(dependent)

                if schema_available == '':
                    unavailable_schemas[dependent_key] = dependent_schema
                elif schema_available == available_commit_hash:
                    if dependent_key not in available_schemas:
                        available_schemas[dependent_key] = dependent_schema
                else:
                    new_schema = dependent_schema.replace(f'/{available_commit_hash}/', f'/{schema_available}/')
                    dependent['schema'] = new_schema
                    updated = True
            except Exception:
                unavailable_schemas[dependent_key] = dependent_schema
                LOGGER.exception(f'Error occured while processing dependent {dependent_key}')
                continue
        # Check the schema path of each submodule
        for submodule in submodules:
            submodule_schema = submodule.get('schema', '')
            submodule_key = f'{submodule.get("name")}@{submodule.get("revision")}'
            try:
                available_commit_hash = get_branch_from_schema(submodule_schema)
                get_commit_hash_history(module)

                if submodule_key in unavailable_schemas:
                    LOGGER.warning(f'Skipping submodule {submodule_key} - schema unavailable')
                    continue

                if submodule_key in available_schemas:
                    schema_available = get_branch_from_schema(available_schemas[submodule_key])
                else:
                    schema_available = check_schema_availability(submodule)

                if schema_available == '':
                    unavailable_schemas[submodule_key] = submodule_schema
                elif schema_available == available_commit_hash:
                    if submodule_key not in available_schemas:
                        available_schemas[submodule_key] = submodule_schema
                else:
                    new_schema = submodule_schema.replace(f'/{available_commit_hash}/', f'/{schema_available}/')
                    submodule['schema'] = new_schema
                    updated = True
            except Exception:
                unavailable_schemas[submodule_key] = submodule_schema
                LOGGER.exception(f'Error occured while processing submodule {submodule_key}')
                continue

        # Make patch request to ConfD to update schema
        if updated:
            updated_modules[key] = module

            response = confdService.patch_module(module)

            __print_patch_response(key, response)

    # Reload cache after checking schemas in dependents and submodules
    url = f'{yangcatalog_api_prefix}/load-cache'
    response = requests.post(url, None, auth=(credentials[0], credentials[1]))
    LOGGER.info(f'Cache loaded with status {response.status_code}')

    LOGGER.info(f"'master' in dependencies: {master_in_dependencies}")
    LOGGER.info(f'Number of updated modules: {len(updated_modules)}')
    LOGGER.info(f'Number of unavailable schemas: {len(unavailable_schemas)}')

    # Dump unavailable schemas to JSON file
    with open(os.path.join(temp_dir, 'unavailable_schemas.json'), 'w') as f:
        json.dump(unavailable_schemas, f, indent=2, sort_keys=True)
