# Copyright The IETF Trust 2022, All Rights Reserved
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

__author__ = 'Dmytro Kyrychenko'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'dmytro.kyrychenko@pantheon.tech'

import logging
import time

import requests

from utility.create_config import create_config
from utility.staticVariables import json_headers

SLEEP_TIME = 30
N_RETRIES = 5


def fetch_modules(logger: logging.Logger) -> list[dict]:
    config = create_config()
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')
    fetch_url = f'{yangcatalog_api_prefix}/search/modules'

    for retry in range(1, N_RETRIES + 1):  # 'n_retries' to get successful response
        logger.info(f'Requesting all the modules from {yangcatalog_api_prefix} for the {retry} time...')
        response = requests.get(fetch_url, headers=json_headers)
        if response.status_code < 200 or response.status_code > 299:
            logger.warning(f'Request {retry} failed with {response.text}')
            if retry < N_RETRIES + 1:
                time.sleep(SLEEP_TIME)  # waiting for 'sleep_time' seconds until next retry
        else:
            modules = response.json().get('module', [])
            logger.debug(f'{len(modules)} modules fetched from {yangcatalog_api_prefix} successfully')
            return modules

    raise RuntimeError('Failed to fetch modules from API.')


if __name__ == '__main__':
    modules = fetch_modules(logging.getLogger('fetch_modules'))
    if modules:
        print(f'Fetched {len(modules)} modules. Here is an example:\n{modules[0]}')
