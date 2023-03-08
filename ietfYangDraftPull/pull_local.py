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
Cronjob tool that automatically runs populate.py over 3 different directories:
I. RFC .yang modules -> standard/ietf/RFC path
II. Draft .yang modules -> experimental/ietf-extracted-YANG-modules path
III. IANA maintained modules -> standard/iana path
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import logging
import os

import utility.log as log
from utility.create_config import create_config
from utility.repoutil import add_worktree, remove_worktree
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


class WorktreeManager:
    def __init__(self):
        self._worktrees = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        for worktree in self._worktrees.values():
            remove_worktree(worktree)

    def __getitem__(self, repo_dir: str):
        if repo_dir not in self._worktrees:
            self._worktrees[repo_dir] = add_worktree(repo_dir)
        return self._worktrees[repo_dir]


def run_populate_script(directory: str, notify: bool, logger: logging.Logger) -> bool:
    """
    Run populate.py script and return whether execution was successful or not.

    Arguments:
        :param directory    (str) full path to directory with yang modules
        :param notify       (str) whether to send files for indexing
        :param logger       (obj) formated logger with the specified name
    """
    successful = True
    try:
        module = __import__('parseAndPopulate', fromlist=['populate'])
        submodule = getattr(module, 'populate')
        script_conf = submodule.DEFAULT_SCRIPT_CONFIG.copy()
        script_conf.args.__setattr__('sdo', True)
        script_conf.args.__setattr__('dir', directory)
        script_conf.args.__setattr__('notify_indexing', notify)
        logger.info(f'Running populate.py script over {directory}')
        submodule.main(script_conf=script_conf)
    except Exception:
        logger.exception('Error occurred while running populate.py script')
        successful = False

    return successful


def populate_directory(directory: str, notify_indexing: bool, logger: logging.Logger):
    """
    Run the populate script on a directory and return the result.

    Arguments:
        :param directory        (str) Directory to run the populate script on
        :param notify_indexing  (bool)
        :param logger           (Logger)
        :return                 (tuple[bool, str]) First specifies whether the script ran successfully,
            second element is a corresponding text message.
    """
    success = run_populate_script(directory, notify_indexing, logger)
    message = 'Populate script finished successfully' if success else 'Error while calling populate script'
    return success, message


@job_log(file_basename=BASENAME)
def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()) -> list[JobLogMessage]:
    args = script_conf.args

    config_path = args.config_path
    config = create_config(config_path)
    notify_indexing = config.get('General-Section', 'notify-index')
    log_directory = config.get('Directory-Section', 'logs')
    yang_models_dir = config.get('Directory-Section', 'yang-models-dir')
    non_ietf_directory = config.get('Directory-Section', 'non-ietf-directory')
    openconfig_dir = os.path.join(non_ietf_directory, 'openconfig/public')
    logger = log.get_logger('pull_local', f'{log_directory}/jobs/pull-local.log')
    logger.info('Starting cron job IETF pull request local')

    messages = []
    notify_indexing = notify_indexing == 'True'
    success = True

    with WorktreeManager() as worktrees:
        try:
            for repo, path_in_repo, label in (
                (yang_models_dir, 'standard/ietf/RFC', 'Standard RFC modules'),
                (yang_models_dir, 'experimental/ietf-extracted-YANG-modules', 'Experimental modules'),
                (yang_models_dir, 'standard/iana', 'IANA modules'),
                (openconfig_dir, '', 'OpenConfig modules'),
            ):
                full_path = os.path.join(worktrees[repo], path_in_repo)
                directory_success, message = populate_directory(full_path, notify_indexing, logger)
                success &= directory_success
                messages.append({'label': label, 'message': message})
        except Exception as e:
            logger.exception('Exception found while running pull_local script')
            raise e
    if success:
        logger.info('Job finished successfully')
    else:
        logger.info('Job finished, but errors found while calling populate script')
    return messages


if __name__ == '__main__':
    main()
