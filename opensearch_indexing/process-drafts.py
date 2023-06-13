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

"""
Script for adding new drafts to the DRAFTS index in OpenSearch, so they can be searched in our system.
"""

__author__ = 'Dmytro Kyrychenko'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'dmytro.kyrychenko@pantheon.tech'

import logging
import os

from opensearch_indexing.models.opensearch_indices import OpenSearchIndices
from opensearch_indexing.opensearch_manager import OpenSearchManager
from utility import log
from utility.create_config import create_config
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.util import JobLogMessage, job_log

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME].get('args'),
    arglist=None if __name__ == '__main__' else [],
)


@job_log(file_basename=BASENAME)
def main(script_config: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()) -> list[JobLogMessage]:
    config = create_config(script_config.args.config_path)
    is_prod = config.get('General-Section', 'is-prod')
    log_directory = config.get('Directory-Section', 'logs')

    if is_prod:
        ietf_drafts_dir = config.get('Directory-Section', 'ietf-archive-drafts')
    else:
        ietf_drafts_dir = config.get('Directory-Section', 'ietf-drafts')

    logger = log.get_logger('process_drafts', os.path.join(log_directory, 'process-drafts.log'))
    logger.info('Starting process-drafts.py script')

    drafts = [filename[:-4] for filename in os.listdir(ietf_drafts_dir) if filename[-4:] == '.txt']

    logger.info('Trying to initialize OpenSearch indices')
    opensearch_manager = OpenSearchManager()
    if not opensearch_manager.index_exists(OpenSearchIndices.DRAFTS):
        error_message = 'Drafts index has not been created yet.'
        logger.error(error_message)
        raise RuntimeError(error_message)

    logging.getLogger('opensearch').setLevel(logging.ERROR)

    done = 0
    for i, draft_name in enumerate(drafts, 1):
        draft = {'draft': draft_name}

        logger.info(f'Indexing draft {draft_name} - draft {i} out of {len(drafts)}')

        try:
            if not opensearch_manager.document_exists(OpenSearchIndices.DRAFTS, draft):
                opensearch_manager.index_module(OpenSearchIndices.DRAFTS, draft)
                logger.info(f'added {draft_name} to index')
                done += 1
            else:
                logger.info(f'skipping - {draft_name} is already in index')
        except Exception:
            logger.exception(f'Problem while processing draft {draft_name}')
    logger.info('Job finished successfully')
    return [JobLogMessage(label='Successful', message=f'Added {done} drafts to Opensearch')]


if __name__ == '__main__':
    main()
