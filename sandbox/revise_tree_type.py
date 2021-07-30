import configparser as ConfigParser
import sys
import time

import requests
import utility.log as log
from parseAndPopulate.modulesComplicatedAlgorithms import \
    ModulesComplicatedAlgorithms

if __name__ == '__main__':
    start = time.time()
    config_path = '/etc/yangcatalog/yangcatalog.conf'
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    api_protocol = config.get('General-Section', 'protocol-api', fallback='http')
    ip = config.get('Web-Section', 'ip', fallback='localhost')
    api_port = int(config.get('Web-Section', 'api-port', fallback=5000))
    confd_protocol = config.get('Web-Section', 'protocol', fallback='http')
    confd_ip = config.get('Web-Section', 'confd-ip', fallback='localhost')
    confd_port = int(config.get('Web-Section', 'confd-port', fallback=8008))
    is_uwsgi = config.get('General-Section', 'uwsgi', fallback=True)
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    log_directory = config.get('Directory-Section', 'logs', fallback='/var/yang/logs')
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    yang_models = config.get('Directory-Section', 'yang-models-dir', fallback='/var/yang/nonietf/yangmodels/yang')
    credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')

    LOGGER = log.get_logger('sandbox', '{}/sandbox.log'.format(log_directory))

    suffix = api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'

    yangcatalog_api_prefix = '{}://{}{}{}/'.format(api_protocol, ip, separator, suffix)
    url = '{}search/modules'.format(yangcatalog_api_prefix)
    LOGGER.info('Getting all the modules from: {}'.format(url))
    response = requests.get(url, headers={'Accept': 'application/json'})

    all_existing_modules = response.json()

    # Initialize ModulesComplicatedAlgorithms
    confd_prefix = '{}://{}:{}'.format(confd_protocol, confd_ip, repr(confd_port))
    direc = '/var/yang/tmp'

    num_of_modules = len(all_existing_modules['module'])
    chunk_size = 100
    chunks = (num_of_modules - 1) // chunk_size + 1
    for i in range(chunks):
        try:
            LOGGER.info('Proccesing chunk {} out of {}'.format(i, chunks))
            batch = all_existing_modules['module'][i * chunk_size:(i + 1) * chunk_size]
            batch_modules = {'module': batch}

            recursion_limit = sys.getrecursionlimit()
            sys.setrecursionlimit(50000)
            complicatedAlgorithms = ModulesComplicatedAlgorithms(log_directory, yangcatalog_api_prefix,
                                                                 credentials, confd_prefix, save_file_dir,
                                                                 direc, batch_modules, yang_models, temp_dir)
            complicatedAlgorithms.parse_non_requests()
            sys.setrecursionlimit(recursion_limit)
            complicatedAlgorithms.populate()
        except:
            LOGGER.exception('Exception occured during running ModulesComplicatedAlgorithms')
            continue

    end = time.time()
    LOGGER.info('Populate took {} seconds with the main and complicated algorithm'.format(int(end - start)))
