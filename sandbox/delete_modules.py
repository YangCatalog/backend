""" This script will completly delete the modules from YangCatalog.
Code might need to be updated everytime to filter out the modules which are
meant to be deleted (currently set to organization = Huawei).
"""
import configparser as ConfigParser
import json
import os

import redis
import requests

if __name__ == '__main__':
    config_path = '/etc/yangcatalog/yangcatalog.conf'
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    api_protocol = config.get('General-Section', 'protocol-api', fallback='http')
    ip = config.get('Web-Section', 'ip', fallback='localhost')
    api_port = int(config.get('Web-Section', 'api-port', fallback=5000))
    is_uwsgi = config.get('General-Section', 'uwsgi', fallback='True')
    delete_cache = config.get('Directory-Section', 'delete-cache', fallback='/var/yang/yang2_repo_deletes.dat')
    temp_dir = config.get('Directory-Section', 'temp', fallback='/var/yang/tmp')
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='user password').strip('"').split()
    confd_ip = config.get('Web-Section', 'confd-ip', fallback='yc-confd')
    confd_port = int(config.get('Web-Section', 'confd-port', fallback=8008))
    confd_protocol = config.get('General-Section', 'protocol-confd', fallback='http')
    redis_host = config.get('DB-Section', 'redis-host', fallback='localhost')
    redis_port = config.get('DB-Section', 'redis-port', fallback='6379')

    redis = redis.Redis(host=redis_host, port=redis_port)

    separator = ':'
    suffix = api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'

    confd_prefix = '{}://{}:{}'.format(confd_protocol, confd_ip, confd_port)
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(api_protocol, ip, separator, suffix)

    # Get either all the modules from Yangcatalog, or search for specific modules based on condition
    # Currently set to select all Huawei modules
    url = '{}search/organization/huawei'.format(yangcatalog_api_prefix)
    response = requests.get(url, headers={'Accept': 'application/json'})
    modules_list = response.json().get('yang-catalog:modules', {}).get('module', [])

    deleted_list = []
    for module in modules_list:
        key = '{}@{}/{}'.format(module['name'], module['revision'], module['organization'])
        deleted_list.append(key)

        # Delete module from ConfD
        url = '{}/restconf/data/yang-catalog:catalog/modules/module={},{},{}'.format(
            confd_prefix, module['name'], module['revision'], module['organization'])

        response = requests.delete(url, auth=(credentials[0], credentials[1]),
                                   headers={'Content-Type': 'application/yang-data+json',
                                            'Accept': 'application/yang-data+json'})
        if response.status_code == 204:
            print('{} deleted from ConfD successfully'.format(key))
        else:
            print('{} failed to remove from ConfD'.format(key))

        # Delete yang file from /all_modules directory
        try:
            all_modules_path = '{}/{}@{}.yang'.format(save_file_dir, module['name'], module['revision'])
            os.remove(all_modules_path)
            print('{} deleted from path {}'.format(key, all_modules_path))
        except OSError:
            pass

    # Reload cache after removing the modules - this should also remove data from Redis
    if len(deleted_list) > 0:
        url = '{}load-cache'.format(yangcatalog_api_prefix)
        response = requests.post(url, None, auth=(credentials[0], credentials[1]))
        print('Cache loaded with status {}'.format(response.status_code))

    # Dump modules list to the yang2_repo_deletes.dat file to delete modules from Elasticsearch
    with open(delete_cache, 'w') as f:
        f.write(json.dumps(deleted_list))
