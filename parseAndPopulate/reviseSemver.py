"""
Python script that first gets all the existing modules from Yangcatalog,
then it goes through modules list and get only first revision of each
unique module.
Unique modules can be dumped into prepare json and also unique modules
can be loaded from prepare json file.
parser_semver() method is then called, which will reevaluate semver for
each module (and all of the revisions).
Lastly, populate() method will send PATCH request to ConfD and
cache will be re-loaded using api/load-cache endpoint.
"""
import json
import os
import sys
import time
from datetime import datetime

import requests
import utility.log as log
from utility.create_config import create_config
from utility.scriptConfig import BaseScriptConfig
from utility.util import job_log

from parseAndPopulate.modulesComplicatedAlgorithms import \
    ModulesComplicatedAlgorithms


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'This script gets all the existing modules from Yangcatalog, '\
            'then it goes through modules list and get only first revision of each '\
            'unique module. parser_semver() method is then called, which will reevaluate semver for '\
            'each module (and all of the revisions). '\
            'Lastly, populate() method will send PATCH request to ConfD and ' \
            'cache will be re-loaded.'

        help = 'Parse modules on given directory and generate json with module metadata that can be populated' \
               ' to confd directory'
        super().__init__(help, None, [])


def get_date(revision: str):
    rev = revision.split('-')
    try:
        date = datetime(int(rev[0]), int(rev[1]), int(rev[2]))
    except Exception:
        try:
            if int(rev[1]) == 2 and int(rev[2]) == 29:
                date = datetime(int(rev[0]), int(rev[1]), 28)
            else:
                date = datetime(1970, 1, 1)
        except Exception:
            date = datetime(1970, 1, 1)
    return date


def get_older_revision(module1: dict, module2: dict):
    date1 = get_date(module1.get('revision'))
    date2 = get_date(module2.get('revision'))
    if date1 < date2:
        return module1
    return module2


def get_list_of_unique_modules(all_existing_modules: list):
    # Get oldest revision of the each module
    unique_modules = []
    oldest_modules_dict = {}

    for module in all_existing_modules:
        module_name = module.get('name')
        oldest_module_revision = oldest_modules_dict.get(module_name, None)
        if oldest_module_revision is None:
            oldest_modules_dict[module_name] = module
        else:
            older_module = get_older_revision(module, oldest_module_revision)
            oldest_modules_dict[module_name] = older_module

    for module in oldest_modules_dict.values():
        unique_modules.append(module)

    dump_to_json(path, unique_modules)

    return {'module': unique_modules}


def dump_to_json(path: str, modules: list):
    # Create prepare.json file for possible future use
    with open(path, 'w') as writer:
        json.dump({'module': modules}, writer)


def load_from_json(path: str):
    # Load dumped data from json file
    with open(path, 'r') as reader:
        return json.load(reader)


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    config = create_config()

    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    yang_models = config.get('Directory-Section', 'yang-models-dir', fallback='/var/yang/nonietf/yangmodels/yang')
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='test test').strip('"').split(' ')
    json_ytree = config.get('Directory-Section', 'json-ytree', fallback='/var/yang/ytrees')
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    LOGGER = log.get_logger('sandbox', '{}/sandbox.log'.format(log_directory))

    url = '{}/search/modules'.format(yangcatalog_api_prefix)
    LOGGER.info('Getting all the modules from: {}'.format(url))
    response = requests.get(url, headers={'Accept': 'application/json'})

    all_existing_modules = response.json().get('module', [])

    global path
    path = '{}/semver_prepare.json'.format(temp_dir)

    all_modules = get_list_of_unique_modules(all_existing_modules)
    LOGGER.info('Number of unique modules: {}'.format(len(all_modules['module'])))

    # Uncomment the next line to read data from the file semver_prepare.json
    # all_modules = load_from_json(path)

    # Initialize ModulesComplicatedAlgorithms
    direc = '/var/yang/tmp'

    num_of_modules = len(all_modules['module'])
    chunk_size = 100
    chunks = (num_of_modules - 1) // chunk_size + 1
    for i in range(chunks):
        try:
            LOGGER.info('Proccesing chunk {} out of {}'.format(i, chunks))
            batch = all_modules['module'][i * chunk_size:(i + 1) * chunk_size]
            batch_modules = {'module': batch}
            recursion_limit = sys.getrecursionlimit()
            sys.setrecursionlimit(50000)
            complicated_algorithms = ModulesComplicatedAlgorithms(log_directory, yangcatalog_api_prefix, credentials,
                                                                  save_file_dir, direc, batch_modules, yang_models,
                                                                  temp_dir, json_ytree)
            complicated_algorithms.parse_semver()
            sys.setrecursionlimit(recursion_limit)
            complicated_algorithms.populate()
        except:
            LOGGER.exception('Exception occured during running ModulesComplicatedAlgorithms')
            continue

    messages = [
        {'label': 'Number of modules checked', 'message': num_of_modules}
    ]
    end = time.time()
    LOGGER.info('Populate took {} seconds with the main and complicated algorithm'.format(int(end - start_time)))
    filename = os.path.basename(__file__).split('.py')[0]
    job_log(start_time, temp_dir, filename, messages=messages, status='Success')
    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    path = ''
    main()
