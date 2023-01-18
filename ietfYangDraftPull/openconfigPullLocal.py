# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
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
Cronjob tool that automatically runs populate.py for all new openconfig modules.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import json
import os
import typing as t
from glob import glob

import requests

import utility.log as log
from ietfYangDraftPull import draftPullUtility
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.staticVariables import json_headers
from utility.util import job_log, resolve_revision

current_file_basename = os.path.basename(__file__)


class ScriptConfig(BaseScriptConfig):
    def __init__(self):
        help = (
            'Run populate script on all openconfig files to parse all modules and populate the'
            ' metadata to yangcatalog if there are any new. This runs as a daily cronjob'
        )
        args: t.List[Arg] = [
            {
                'flag': '--config-path',
                'help': 'Set path to config file',
                'type': str,
                'default': os.environ['YANGCATALOG_CONFIG_PATH'],
            },
        ]
        super().__init__(help, args, None if __name__ == '__main__' else [])


@job_log(file_basename=current_file_basename)
def main(script_conf: BaseScriptConfig = ScriptConfig()) -> list[dict[str, str]]:
    args = script_conf.args

    config_path = args.config_path
    config = create_config(config_path)
    credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    openconfig_repo_url = config.get('Web-Section', 'openconfig-models-repo-url')
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    logger = log.get_logger('openconfigPullLocal', f'{log_directory}/jobs/openconfig-pull.log')
    logger.info('Starting Cron job openconfig pull request local')

    commit_author = {'name': config_name, 'email': config_email}
    repo = draftPullUtility.clone_forked_repository(openconfig_repo_url, commit_author, logger)
    assert repo
    modules = []
    try:
        yang_files = glob(f'{repo.local_dir}/release/models/**/*.yang', recursive=True)
        for yang_file in yang_files:
            basename = os.path.basename(yang_file)
            name = basename.split('.')[0].split('@')[0]
            revision = resolve_revision(yang_file)
            path = yang_file.split(f'{repo.local_dir}/')[-1]
            module = {
                'generated-from': 'not-applicable',
                'module-classification': 'unknown',
                'name': name,
                'revision': revision,
                'organization': 'openconfig',
                'source-file': {'owner': 'openconfig', 'path': path, 'repository': 'public'},
            }
            modules.append(module)
        data = json.dumps({'modules': {'module': modules}})
    except Exception as e:
        logger.exception('Exception found while running openconfigPullLocal script')
        raise e
    api_path = f'{yangcatalog_api_prefix}/modules'
    response = requests.put(api_path, data, auth=(credentials[0], credentials[1]), headers=json_headers)

    status_code = response.status_code
    payload = json.loads(response.text)
    if status_code < 200 or status_code > 299:
        logger.info('Job finished, but an error occured while sending PUT to /api/modules')
        raise RuntimeError(f'PUT /api/modules responsed with status code {status_code}')
    logger.info('Job finished successfully')
    return [{'label': 'Job ID', 'message': payload['job-id']}]


if __name__ == '__main__':
    main()
