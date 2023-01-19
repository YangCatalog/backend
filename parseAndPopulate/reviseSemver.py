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

import utility.log as log
from parseAndPopulate.modulesComplicatedAlgorithms import ModulesComplicatedAlgorithms
from utility.create_config import create_config
from utility.fetch_modules import fetch_modules
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.util import job_log, revision_to_date

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=None,
    arglist=[],
)


def get_older_revision(module1: dict, module2: dict):
    date1 = revision_to_date(module1['revision'])
    date2 = revision_to_date(module2['revision'])
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
    # Load dumped data from json file
    with open(path, 'r') as reader:
        return json.load(reader)


@job_log(file_basename=BASENAME)
def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()) -> list[dict[str, str]]:
    start_time = int(time.time())
    config = create_config()

    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    yang_models = config.get('Directory-Section', 'yang-models-dir', fallback='/var/yang/nonietf/yangmodels/yang')
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='test test').strip('"').split(' ')
    json_ytree = config.get('Directory-Section', 'json-ytree', fallback='/var/yang/ytrees')
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    logger = log.get_logger('sandbox', f'{log_directory}/sandbox.log')

    logger.info('Fetching all the modules from API')
    all_existing_modules = fetch_modules(logger, config=config)

    global path
    path = f'{temp_dir}/semver_prepare.json'

    all_modules = get_list_of_unique_modules(all_existing_modules)
    logger.info(f'Number of unique modules: {len(all_modules["module"])}')

    # Uncomment the next line to read data from the file semver_prepare.json
    # all_modules = load_from_json(path)

    # Initialize ModulesComplicatedAlgorithms
    direc = '/var/yang/tmp'

    num_of_modules = len(all_modules['module'])
    chunk_size = 100
    chunks = (num_of_modules - 1) // chunk_size + 1
    for i in range(chunks):
        try:
            logger.info(f'Proccesing chunk {i} out of {chunks}')
            batch = all_modules['module'][i * chunk_size : (i + 1) * chunk_size]
            batch_modules = {'module': batch}
            recursion_limit = sys.getrecursionlimit()
            sys.setrecursionlimit(50000)
            complicated_algorithms = ModulesComplicatedAlgorithms(
                log_directory,
                yangcatalog_api_prefix,
                credentials,
                save_file_dir,
                direc,
                batch_modules,
                yang_models,
                temp_dir,
                json_ytree,
            )
            complicated_algorithms.parse_semver()
            sys.setrecursionlimit(recursion_limit)
            complicated_algorithms.populate()
        except Exception:
            logger.exception('Exception occured during running ModulesComplicatedAlgorithms')
            continue

    end = time.time()
    logger.info(f'Populate took {int(end - start_time)} seconds with the main and complicated algorithm')
    logger.info('Job finished successfully')
    return [{'label': 'Number of modules checked', 'message': num_of_modules}]


if __name__ == '__main__':
    path = ''
    main()
