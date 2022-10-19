""" This script will completly delete the modules from YangCatalog.
Code might need to be updated everytime to filter out the modules which are
meant to be deleted (currently set to organization = Huawei).
"""
import os

import requests

from utility.create_config import create_config


def main():
    config = create_config()
    save_file_dir = config.get('Directory-Section', 'save-file-dir', fallback='/var/yang/all_modules')
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='user password').strip('"').split()
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    # Get either all the modules from Yangcatalog, or search for specific modules based on condition
    # Currently set to select all Huawei modules
    url = '{}/search/organization/huawei'.format(yangcatalog_api_prefix)
    response = requests.get(url, headers={'Accept': 'application/json'})
    modules_list = response.json().get('yang-catalog:modules', {}).get('module', [])

    to_delete_list = []
    for module in modules_list:
        key = '{}@{}/{}'.format(module['name'], module['revision'], module['organization'])
        to_delete_module = {
            'name': module.get('name'),
            'revision': module.get('revision'),
            'organization': module.get('organization'),
        }
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
    url = '{}/modules'.format(yangcatalog_api_prefix)
    response = requests.delete(url, json=body, auth=(credentials[0], credentials[1]))

    print('Delete request responded with status code {}'.format(response.status_code))
    print(response.text)


if __name__ == '__main__':
    main()
