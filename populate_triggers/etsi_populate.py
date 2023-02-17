# Copyright The IETF Trust 2023, All Rights Reserved
# Copyright 2023 Cisco and its affiliates
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

"""
Cronjob tool that automatically runs populate.py for all new ETSI modules.
"""

__author__ = 'Dmytro Kyrychenko'
__copyright__ = 'Copyright 2023 Cisco and its affiliates, Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'dmytro.kyrychenko@pantheon.tech'

import json
import os
from glob import glob

import requests
from git.exc import InvalidGitRepositoryError

import utility.log as log
from utility import repoutil
from utility.create_config import create_config
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.staticVariables import github_url, json_headers
from utility.util import job_log, resolve_revision

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME]['args'],
    arglist=None if __name__ == '__main__' else [],
)


@job_log(file_basename=BASENAME)
def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()) -> list[dict[str, str]]:
    args = script_conf.args
    config_path = args.config_path
    config = create_config(config_path)
    credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
    log_directory = config.get('Directory-Section', 'logs')
    yang_models_dir = config.get('Directory-Section', 'yang-models-dir')
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    logger = log.get_logger('etsi_populate', f'{log_directory}/jobs/etsi_populate.log')
    logger.info('Starting Cron job etsi_populate pull request local')

    repo_owner = 'YangModels'
    repo_name = 'yang'
    repo_url = os.path.join(github_url, repo_owner, repo_name)
    logger.info(f'repo_url = {repo_url}')
    try:
        repo = repoutil.load(yang_models_dir, repo_url)
    except InvalidGitRepositoryError:
        repo = repoutil.RepoUtil(
            repo_url,
            clone_options={'local_dir': yang_models_dir},
            logger=logger,
        )

    modules = []
    yang_files = []
    for submodule in repo.repo.submodules:
        if 'standard/etsi' in submodule.name:
            logger.info(f'processing {submodule.name}')
            yang_files += glob(f'{submodule.abspath}/**/*.yang', recursive=True)
    logger.info(f'yang_files = {yang_files}')

    for yang_file in yang_files:
        basename = os.path.basename(yang_file)
        name = basename.split('.')[0]
        revision = resolve_revision(yang_file)
        path = yang_file.split(f'{repo.local_dir}/')[-1]
        module = {
            'generated-from': 'not-applicable',
            'module-classification': 'unknown',
            'name': name,
            'revision': revision,
            'organization': 'etsi',
            'source-file': {'owner': repo_owner, 'path': path, 'repository': repo_name},
        }
        if module not in modules:
            modules.append(module)
    data = json.dumps({'modules': {'module': modules}})

    api_path = f'{yangcatalog_api_prefix}/modules'
    response = requests.put(api_path, data, auth=(credentials[0], credentials[1]), headers=json_headers)
    logger.info(f'response.content = {response.content}')
    status_code = response.status_code
    payload = json.loads(response.text)
    if status_code < 200 or status_code > 299:
        logger.info('Job finished, but an error occured while sending PUT to /api/modules')
        raise RuntimeError(f'PUT /api/modules responsed with status code {status_code}')
    logger.info('Job finished successfully')
    return [{'label': 'Job ID', 'message': payload['job-id']}]


if __name__ == '__main__':
    main()
