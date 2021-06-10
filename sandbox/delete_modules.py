""" This script will completly delete the modules from YangCatalog.
Code might need to be updated everytime to filter out the modules which are
meant to be deleted (currently set to organization = Huawei).
"""
import configparser as ConfigParser
import json
import os

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
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='user password').strip('"').split()

    separator = ':'
    suffix = api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'

    yangcatalog_api_prefix = '{}://{}{}{}/'.format(api_protocol, ip, separator, suffix)

    # Get either all the modules from Yangcatalog, or search for specific modules based on condition
    # Currently set to select all Huawei modules
    url = '{}search/organization/huawei'.format(yangcatalog_api_prefix)
    response = requests.get(url, headers={'Accept': 'application/json'})
    modules_list = response.json().get('yang-catalog:modules', {}).get('module', [])

    to_delete_list = []
    for module in modules_list:
        key = '{}@{}/{}'.format(module['name'], module['revision'], module['organization'])
        to_delete_module = {}
        to_delete_module['name'] = module.get('name')
        to_delete_module['revision'] = module.get('revision')
        to_delete_module['organization'] = module.get('organization')
        to_delete_list.append(to_delete_module)

        # Delete yang file from /all_modules directory
        try:
            all_modules_path = '{}/{}@{}.yang'.format(save_file_dir, module['name'], module['revision'])
            os.remove(all_modules_path)
            print('{} deleted from path {}'.format(key, all_modules_path))
        except OSError:
            pass

    # Send DELETE request to /api/modules
    body = {'input': {'modules': to_delete_list}}
    url = '{}modules'.format(yangcatalog_api_prefix)
    response = requests.delete(url, json=body, auth=(credentials[0], credentials[1]))

    print('Delete request responded with status code {}'.format(response.status_code))
    print(response.text)
