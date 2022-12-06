import logging
import time
import typing as t

import requests

from utility.create_config import create_config
from utility.staticVariables import json_headers


def fetch_modules(logger: logging.Logger, sleep_time: int = 30, n_retries: int = 5) -> t.Optional[t.List[dict]]:
    config = create_config()
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')
    fetch_url = f'{yangcatalog_api_prefix}/search/modules'

    for retry in range(1, n_retries + 1):  # 'n_retries' to get successful response
        logger.info(f'Requesting all the modules from {yangcatalog_api_prefix} for the {retry} time...')
        response = requests.get(fetch_url, headers=json_headers)
        if response.status_code < 200 or response.status_code > 299:
            logger.warning(f'Request {retry} failed with {response.text}')
            if retry < n_retries + 1:
                time.sleep(sleep_time)  # waiting for 'sleep_time' seconds until next retry
        else:
            modules = response.json().get('module', [])
            logger.debug(f'{len(modules)} modules fetched from {yangcatalog_api_prefix} successfully')
            return modules

    logger.error(f'All attempts to get successful request from {yangcatalog_api_prefix} have failed')
    return None


if __name__ == '__main__':
    modules = fetch_modules(logging.getLogger('fetch_modules'))
    if modules:
        print(f'Fetched {len(modules)} modules. Here is an example:\n{modules[0]}')
