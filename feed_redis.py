# Copyright The IETF Trust 2021, All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = "Slavomir Mazur"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "slavomir.mazur@pantheon.tech"

import json
import os
import sys
from collections import OrderedDict

import redis


def load_catalog_data():
    resources_path = '{}/tests/resources/'.format(os.path.dirname(os.path.abspath(__file__)))
    try:
        print('Loading cache file from path {}'.format(resources_path))
        with open('{}2020-12-15_00:00:00-UTC.json'.format(resources_path), 'r') as file_load:
            catalog_data = json.load(file_load, object_pairs_hook=OrderedDict)
            print('Content of cache file loaded successfully.')
    except:
        print('Failed to load data from .json file')
        sys.exit(1)

    catalog = catalog_data.get('yang-catalog:catalog')
    modules = catalog['modules']['module']
    vendors = catalog['vendors']['vendor']

    for module in modules:
        if module['name'] == 'yang-catalog' and module['revision'] == '2018-04-03':
            redis_cache.set('yang-catalog@2018-04-03/ietf', json.dumps(module))
            print('yang-catalog@2018-04-03 module set in Redis')
            break

    catalog_data_json = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(json.dumps(catalog_data))['yang-catalog:catalog']
    modules = catalog_data_json['modules']
    vendors = catalog_data_json.get('vendors', {})

    redis_cache.set('modules-data', json.dumps(modules))
    print('{} modules set in Redis.'.format(len(modules.get('module', {}))))
    redis_cache.set('vendors-data', json.dumps(vendors))
    print('{} vendors set in Redis.'.format(len(vendors.get('vendor', {}))))
    redis_cache.set('all-catalog-data', json.dumps(catalog_data))


redis_cache = redis.Redis(host='localhost', port=6379)
load_catalog_data()
