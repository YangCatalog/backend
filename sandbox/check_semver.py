""" This script loops through each module twice - two phases.
Phase I - Loop through the modules and check whether
          there is a 'master' string in the schema and that it is available.
          Store available and unavailable schemas for phase II.
Phase II - Loop through the modules and check whether
           there is a 'master' string in the dependencies, dependents and submodules schemas.
           Store available and unavailable schemas
           so there will be no need to make a request for each single scheme.
Patch request to ConfD request is made for each module that has been modified.
Also reload-cache is called after each phase.
Finally, unavailable schemas are dumped into JSON file
"""
# TODO:
# If the schema is unavailable, iterate through the individual commit hashes in repository
# until you get a valid commit - GET request will return status code 200 and content of .yang module
import configparser as ConfigParser
import json

import requests
from utility import repoutil

github_raw = 'https://raw.githubusercontent.com/'
github_url = 'https://github.com/'


def check_schema_availability(schema: str, key: str, available_schemas: dict, unavailable_schemas: dict):
    available = False

    if key in unavailable_schemas:
        return False

    if key in available_schemas:
        available = True
    else:
        response = requests.get(schema)
        if response.status_code == 200:
            available = True

    return available


def get_master_commit_hash(module: dict):
    """ Try to get master branch commit hash for each repo.
    """
    schema = module.get('schema', '')
    # Get repo owner and name
    schema_part = schema.split(github_raw)[1]
    repo_owner = schema_part.split('/')[0]
    repo_name = schema_part.split('/')[1]
    repo_owner_name = '{}/{}'.format(repo_owner, repo_name)

    # Get commit hash of the master branch of currently parsed repo
    commit_hash = commit_hashes.get(repo_owner_name, None)

    # Clone repo to get the commit hash if necessary
    if commit_hash is None:
        repo_url = '{}{}/{}'.format(github_url, repo_owner, repo_name)
        repo = repoutil.RepoUtil(repo_url)
        repo.clone()
        commit_hash = repo.get_commit_hash()
        repo.remove()

        # Store commit hash for this repo
        commit_hashes[repo_owner_name] = commit_hash

    return commit_hash


def __print_patch_response(key: str, response):
    message = 'Module {} updated with code {}'.format(key, response.status_code)
    if response.text != '':
        message = '{} and text {}'.format(message, response.text)
    print(message)


if __name__ == '__main__':
    config_path = '/etc/yangcatalog/yangcatalog.conf'
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    api_protocol = config.get('General-Section', 'protocol-api', fallback='http')
    ip = config.get('Web-Section', 'ip', fallback='localhost')
    api_port = int(config.get('Web-Section', 'api-port', fallback=5000))
    is_uwsgi = config.get('General-Section', 'uwsgi', fallback='True')
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='user password').strip('"').split()
    confd_ip = config.get('Web-Section', 'confd-ip', fallback='yc-confd')
    confd_port = int(config.get('Web-Section', 'confd-port', fallback=8008))
    confd_protocol = config.get('General-Section', 'protocol-confd', fallback='http')

    separator = ':'
    suffix = api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'

    confd_prefix = '{}://{}:{}'.format(confd_protocol, confd_ip, confd_port)
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(api_protocol, ip, separator, suffix)

    # GET all the existing modules of Yangcatalog
    response = requests.get('{}search/modules'.format(yangcatalog_api_prefix),
                            headers={'Accept': 'application/json'})
    all_existing_modules = response.json().get('module', [])

    ###
    # PHASE I - Check the schema of each module
    ###
    master_in_schema = {}
    unavailable_schemas = {}
    available_schemas = {}
    updated_modules = {}
    commit_hashes = {}

    for module in all_existing_modules:
        key = '{}@{}'.format(module.get('name'), module.get('revision'))
        schema = module.get('schema', '')
        commit_hash = get_master_commit_hash(module)

        # If there is a 'master' in the schema, try to replace it with the current master commit hash
        if '/master/' in schema:
            new_schema = schema.replace('master', commit_hash)
            schema_available = check_schema_availability(new_schema, key, available_schemas, unavailable_schemas)
            if schema_available:
                module['schema'] = new_schema
                updated_modules[key] = module
                available_schemas[key] = new_schema

                # Make patch request to ConfD to update schema
                url = '{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}' \
                    .format(confd_prefix, module['name'], module['revision'], module['organization'])
                response = requests.patch(url, json.dumps({'yang-catalog:module': module}),
                                          auth=(credentials[0], credentials[1]),
                                          headers={'Content-Type': 'application/yang-data+json',
                                                   'Accept': 'application/yang-data+json'})
                __print_patch_response(key, response)
            else:
                master_in_schema[key] = module
                unavailable_schemas[key] = schema
        else:
            schema_available = check_schema_availability(schema, key, available_schemas, unavailable_schemas)
            if schema_available:
                available_schemas[key] = schema
            else:
                master_in_schema[key] = module
                unavailable_schemas[key] = schema

    # Reload cache after checking each scheme
    if len(updated_modules) > 0:
        url = '{}load-cache'.format(yangcatalog_api_prefix)
        response = requests.post(url, None, auth=(credentials[0], credentials[1]))
        print('Cache loaded with status {}'.format(response.status_code))

    print('Numer of modules checked: {}'.format(len(all_existing_modules)))
    print('Number of available schemas: {}'.format(len(available_schemas)))
    print('Number of unavailable schemas: {}'.format(len(unavailable_schemas)))
    print('Number of updated schemas: {}'.format(len(updated_modules)))

    ###
    # PHASE II - Check the schema in dependencies, dependets and submodules for each module
    ###
    updated_modules = {}
    master_in_dependencies = {}
    master_in_dependents = {}
    master_in_submodules = {}

    for module in all_existing_modules:
        key = '{}@{}'.format(module.get('name'), module.get('revision'))
        dependencies = module.get('dependencies', [])
        dependents = module.get('dependents', [])
        submodules = module.get('submodule', [])
        updated = False

        for dependency in dependencies:
            dependency_schema = dependency.get('schema', '')
            if '/master/' in dependency_schema:
                master_in_dependencies[key] = module

        # Check the schema path of each dependent
        for dependent in dependents:
            dependent_schema = dependent.get('schema', '')
            dependent_key = '{}@{}'.format(dependent.get('name'), dependent.get('revision'))
            if '/master/' in dependent_schema:
                if dependent_key in available_schemas:
                    dependent['schema'] = available_schemas[dependent_key]
                    updated = True
                else:
                    commit_hash = get_master_commit_hash(dependent)
                    new_schema = dependent_schema.replace('master', commit_hash)
                    schema_available = check_schema_availability(new_schema, dependent_key, available_schemas, unavailable_schemas)
                    if schema_available:
                        dependent['schema'] = new_schema
                        available_schemas[dependent_key] = new_schema
                        updated = True
                    else:
                        master_in_dependents[key] = module
                        unavailable_schemas[dependent_key] = dependent_schema
            else:
                schema_available = check_schema_availability(dependent_schema, dependent_key, available_schemas, unavailable_schemas)
                if schema_available:
                    if dependent_key not in available_schemas:
                        available_schemas[dependent_key] = dependent_schema
                else:
                    if dependent_key not in unavailable_schemas:
                        unavailable_schemas[dependent_key] = dependent_schema

        # Check the schema path of each submodule
        for submodule in submodules:
            submodule_schema = submodule.get('schema', '')
            submodule_key = '{}@{}'.format(submodule.get('name'), submodule.get('revision'))
            if '/master/' in submodule_schema:
                if submodule_key in available_schemas:
                    submodule['schema'] = available_schemas[submodule_key]
                    updated = True
                else:
                    commit_hash = get_master_commit_hash(submodule)
                    new_schema = submodule_schema.replace('master', commit_hash)
                    schema_available = check_schema_availability(new_schema, submodule_key, available_schemas, unavailable_schemas)
                    if schema_available:
                        submodule['schema'] = new_schema
                        available_schemas[submodule_key] = new_schema
                        updated = True
                    else:
                        master_in_submodules[key] = module
                        unavailable_schemas[submodule_key] = submodule_schema
            else:
                schema_available = check_schema_availability(submodule_schema, submodule_key, available_schemas, unavailable_schemas)
                if schema_available:
                    if submodule_key not in available_schemas:
                        available_schemas[submodule_key] = submodule_schema
                else:
                    if submodule_key not in unavailable_schemas:
                        unavailable_schemas[submodule_key] = submodule_schema

        # # Make patch request to ConfD to update schema
        if updated == True:
            updated_modules[key] = module
            url = '{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}' \
                .format(confd_prefix, module['name'], module['revision'], module['organization'])
            response = requests.patch(url, json.dumps({'yang-catalog:module': module}),
                                      auth=(credentials[0], credentials[1]),
                                      headers={'Content-Type': 'application/yang-data+json',
                                               'Accept': 'application/yang-data+json'})
            __print_patch_response(key, response)

    # Reload cache after checking schemas in dependents and submodules
    url = '{}load-cache'.format(yangcatalog_api_prefix)
    response = requests.post(url, None, auth=(credentials[0], credentials[1]))
    print('Cache loaded with status {}'.format(response.status_code))

    print("'master' in schema: {}".format(len(master_in_schema)))
    print("'master' in dependencies: {}".format(len(master_in_dependencies)))
    print("'master' in dependents: {}".format(len(master_in_dependents)))
    print("'master' in submodules: {}".format(len(master_in_submodules)))
    print('Number of updated modules: {}'.format(len(updated_modules)))
    print('Number of unavailable schemas: {}'.format(len(unavailable_schemas)))

    # Dump unavailable schemas to JSON file
    with open('{}/unavailable_schemas.json'.format(temp_dir), 'w') as f:
        json.dump(unavailable_schemas, f, indent=2, sort_keys=True)
