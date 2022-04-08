""" This script loops through each module twice - two phases.
Phase I - Loop through the modules and check whether
          there is a 'master' string in the schema and also that if it is still available.
          Store available and unavailable schemas for phase II - to avoid makind duplicite requests.
Phase II - Loop through the modules and check whether
           there is a 'master' string in the dependencies, dependents and submodules schemas.
           Store available and unavailable schemas
           so there will be no need to make a request for each single scheme.
Patch request to ConfD request is made for each module that has been modified.
Also reload-cache is called after each phase.
Finally, unavailable schemas are dumped into JSON file.
"""
import json

import requests
import utility.log as log
from utility import repoutil, yangParser
from utility.confdService import ConfdService
from utility.create_config import create_config
from utility.staticVariables import github_raw, github_url


def get_repo_owner_name(schema: str):
    schema_part = schema.split(github_raw)[1]
    repo_owner = schema_part.split('/')[1]
    repo_name = schema_part.split('/')[2]

    return repo_owner, repo_name


def get_branch_from_schema(schema: str):
    splitted_schema = schema.split('/')
    branch = splitted_schema[5]  #  5 is the position of the hash in URL path

    return branch


def get_available_commit_hash(module: dict, commit_hash_list: list):
    name = module.get('name')
    schema = module.get('schema', '')
    revision = module.get('revision')

    branch = get_branch_from_schema(schema)

    available_commit_hash = ''
    for commit_hash in commit_hash_list:
        new_schema = schema.replace(branch, commit_hash)
        if new_schema not in requests_done:
            requests_done.append(new_schema)
            response = requests.get(new_schema)
            if response.status_code == 200:
                module_text = response.text
                try:
                    module_revision = yangParser.parse(module_text).search('revision')[0].arg
                except:
                    module_revision = '1970-01-01'
                key = '{}@{}'.format(name, module_revision)
                available_schemas[key] = new_schema
                if revision == module_revision:
                    available_commit_hash = commit_hash
                    break

    return available_commit_hash


def check_schema_availability(module: str):
    schema = module.get('schema', '')
    repo_owner, repo_name = get_repo_owner_name(schema)
    repo_owner_name = '{}/{}'.format(repo_owner, repo_name)
    commit_hash_list = commit_hash_history.get(repo_owner_name, [])
    available_commit_hash = ''

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
    """ Try to get list of commit hashes of master branch for each Git repository.
    """
    # Get repo owner and name
    schema = module.get('schema', '')
    repo_owner, repo_name = get_repo_owner_name(schema)
    repo_owner_name = '{}/{}'.format(repo_owner, repo_name)

    commit_hash = commit_hash_history.get(repo_owner_name, None)

    # Clone repo to get the commit hashes history for repository
    if commit_hash is None:
        repo_url = '{}/{}/{}'.format(github_url, repo_owner, repo_name)
        LOGGER.info('Cloning repo from {}'.format(repo_url))
        repo = repoutil.ModifiableRepoUtil(repo_url)

        # Get list of all historic hashes
        commit_hash_history[repo_owner_name] = [commit.hexsha for commit in repo.repo.iter_commits('master')]


def __print_patch_response(key: str, response):
    message = 'Module {} updated with code {}'.format(key, response.status_code)
    if response.text != '':
        message = '{} and text {}'.format(message, response.text)
    LOGGER.info(message)


if __name__ == '__main__':
    config = create_config()
    api_protocol = config.get('General-Section', 'protocol-api', fallback='http')
    ip = config.get('Web-Section', 'ip', fallback='localhost')
    api_port = int(config.get('Web-Section', 'api-port', fallback=5000))
    is_uwsgi = config.get('General-Section', 'uwsgi', fallback='True')
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='user password').strip('"').split()

    LOGGER = log.get_logger('sandbox', '{}/sandbox.log'.format(log_directory))
    confdService = ConfdService()

    separator = ':'
    suffix = api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'

    yangcatalog_api_prefix = '{}://{}{}{}/'.format(api_protocol, ip, separator, suffix)

    # GET all the existing modules of Yangcatalog
    url = '{}search/modules'.format(yangcatalog_api_prefix)
    response = requests.get(url, headers={'Accept': 'application/json'})
    all_existing_modules = response.json().get('module', [])
    LOGGER.info('{} modules fetched from URL {}'.format(len(all_existing_modules), url))

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
        key = '{}@{}'.format(module.get('name'), module.get('revision'))
        schema = module.get('schema')

        if key in unavailable_schemas:
            LOGGER.warning('Skipping module {} - schema unavailable'.format(key))
            continue
        if schema is None:
            unavailable_schemas[key] = ''
            continue
        try:
            available_commit_hash = get_branch_from_schema(schema)
            get_commit_hash_history(module)

            LOGGER.debug('Checking schema for module {}'.format(key))
            if key in available_schemas:
                schema_available = get_branch_from_schema(available_schemas[key])
            else:
                schema_available = check_schema_availability(module)

            if schema_available == '':
                unavailable_schemas[key] = schema
                LOGGER.warning('Schema not available: {}'.format(schema))
            elif schema_available == available_commit_hash:
                if key not in available_schemas:
                    available_schemas[key] = schema
            else:
                new_schema = schema.replace('/{}/'.format(available_commit_hash), '/{}/'.format(schema_available))
                module['schema'] = new_schema
                updated_schemas += 1

                # Make patch request to ConfD to update schema
                response = confdService.patch_module(module)

                __print_patch_response(key, response)
        except:
            LOGGER.exception('Problem with module {}'.format(key))
            unavailable_schemas[key] = schema
            continue

    # Reload cache after checking each scheme
    if updated_schemas > 0:
        url = '{}load-cache'.format(yangcatalog_api_prefix)
        response = requests.post(url, None, auth=(credentials[0], credentials[1]))
        LOGGER.info('Cache loaded with status {}'.format(response.status_code))

    LOGGER.info('Number of modules checked: {}'.format(len(all_existing_modules)))
    LOGGER.info('Number of unavailable schemas: {}'.format(len(unavailable_schemas)))
    LOGGER.info('Number of updated schemas: {}'.format(updated_schemas))

    # Dump unavailable schemas to JSON file
    with open('{}/unavailable_schemas.json'.format(temp_dir), 'w') as f:
        json.dump(unavailable_schemas, f, indent=2, sort_keys=True)

    ###
    # PHASE II - Check the schema in dependencies, dependets and submodules for each module
    ###
    updated_modules = {}
    master_in_dependencies = 0

    for module in all_existing_modules:
        key = '{}@{}'.format(module.get('name'), module.get('revision'))
        dependencies = module.get('dependencies', [])
        dependents = module.get('dependents', [])
        submodules = module.get('submodule', [])
        updated = False

        LOGGER.debug('Checking dependents and submodules for module {}'.format(key))

        for dependency in dependencies:
            dependency_schema = dependency.get('schema', '')
            if '/master/' in dependency_schema:
                master_in_dependencies += 1

        # Check the schema path of each dependent
        for dependent in dependents:
            dependent_schema = dependent.get('schema', '')
            dependent_key = '{}@{}'.format(dependent.get('name'), dependent.get('revision'))
            try:
                available_commit_hash = get_branch_from_schema(dependent_schema)
                get_commit_hash_history(module)

                if dependent_key in unavailable_schemas:
                    LOGGER.warning('Skipping dependent {} - schema unavailable'.format(dependent_key))
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
                    new_schema = dependent_schema.replace('/{}/'.format(available_commit_hash), '/{}/'.format(schema_available))
                    dependent['schema'] = new_schema
                    updated = True
            except:
                unavailable_schemas[dependent_key] = dependent_schema
                LOGGER.exception('Error occured while processing dependent {}'.format(dependent_key))
                continue
        # Check the schema path of each submodule
        for submodule in submodules:
            submodule_schema = submodule.get('schema', '')
            submodule_key = '{}@{}'.format(submodule.get('name'), submodule.get('revision'))
            try:
                available_commit_hash = get_branch_from_schema(submodule_schema)
                get_commit_hash_history(module)

                if submodule_key in unavailable_schemas:
                    LOGGER.warning('Skipping submodule {} - schema unavailable'.format(submodule_key))
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
                    new_schema = submodule_schema.replace('/{}/'.format(available_commit_hash), '/{}/'.format(schema_available))
                    submodule['schema'] = new_schema
                    updated = True
            except:
                unavailable_schemas[submodule_key] = submodule_schema
                LOGGER.exception('Error occured while processing submodule {}'.format(submodule_key))
                continue

        # Make patch request to ConfD to update schema
        if updated == True:
            updated_modules[key] = module

            response = confdService.patch_module(module)

            __print_patch_response(key, response)

    # Reload cache after checking schemas in dependents and submodules
    url = '{}load-cache'.format(yangcatalog_api_prefix)
    response = requests.post(url, None, auth=(credentials[0], credentials[1]))
    LOGGER.info('Cache loaded with status {}'.format(response.status_code))

    LOGGER.info("'master' in dependencies: {}".format(master_in_dependencies))
    LOGGER.info('Number of updated modules: {}'.format(len(updated_modules)))
    LOGGER.info('Number of unavailable schemas: {}'.format(len(unavailable_schemas)))

    # Dump unavailable schemas to JSON file
    with open('{}/unavailable_schemas.json'.format(temp_dir), 'w') as f:
        json.dump(unavailable_schemas, f, indent=2, sort_keys=True)
