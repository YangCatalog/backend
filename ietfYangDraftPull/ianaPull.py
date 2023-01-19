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

"""
Cronjob tool that automatically pushes new IANA-maintained
yang modules to the Github YangModels/yang repository.
Old ones are removed and naming is corrected to <name>@<revision>.yang.
"""

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'


import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from shutil import copy2

from git.exc import GitCommandError

import utility.log as log
from ietfYangDraftPull import draftPullUtility as dpu
from utility.create_config import create_config
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.util import job_log

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
    yang_models = config.get('Directory-Section', 'yang-models-dir')
    token = config.get('Secrets-Section', 'yang-catalog-token')
    username = config.get('General-Section', 'repository-username')
    commit_dir = config.get('Directory-Section', 'commit-dir')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    temp_dir = config.get('Directory-Section', 'temp')
    iana_exceptions = config.get('Directory-Section', 'iana-exceptions')
    is_production = config.get('General-Section', 'is-prod')
    is_production = is_production == 'True'
    logger = log.get_logger('ianaPull', f'{log_directory}/jobs/iana-pull.log')
    logger.info('Starting job to pull IANA-maintained modules')

    repo_name = 'yang'
    commit_author = {'name': config_name, 'email': config_email}

    github_repo_url = dpu.construct_github_repo_url(username, repo_name, token)
    dpu.update_forked_repository(yang_models, github_repo_url, logger)
    repo = dpu.clone_forked_repository(github_repo_url, commit_author, logger)

    if not repo:
        raise RuntimeError(f'Failed to clone repository {username}/{repo_name}')

    try:
        with open(iana_exceptions, 'r') as exceptions_file:
            remove_from_new = exceptions_file.read().split('\n')
    except FileNotFoundError:
        open(iana_exceptions, 'w').close()
        os.chmod(iana_exceptions, 0o664)
        remove_from_new = []

    try:
        iana_temp_path = os.path.join(temp_dir, 'iana')
        if os.path.exists(iana_temp_path):
            shutil.rmtree(iana_temp_path)
        # call rsync to sync with rsync.iana.org::assignments/yang-parameters/
        subprocess.call(['rsync', '-avzq', '--delete', 'rsync.iana.org::assignments/yang-parameters/', iana_temp_path])
        dpu.set_permissions(iana_temp_path)
        iana_standard_path = os.path.join(repo.local_dir, 'standard/iana')
        if not os.path.exists(iana_standard_path):
            os.makedirs(iana_standard_path)
        xml_path = os.path.join(iana_temp_path, 'yang-parameters.xml')
        copy2(xml_path, f'{repo.local_dir}/standard/iana/yang-parameters.xml')

        # Parse yang-parameters.xml file
        root = ET.parse(xml_path).getroot()
        tag = root.tag
        namespace = tag.split('registry')[0]
        modules = root.iter(f'{namespace}record')

        for module in modules:
            data = module.attrib
            for attributes in module:
                prop = attributes.tag.split(namespace)[-1]
                data[prop] = attributes.text or ''

            if data.get('iana') == 'Y' and data.get('file'):
                if data['file'] in remove_from_new:
                    continue
                src = os.path.join(iana_temp_path, data['file'])
                dst = os.path.join(repo.local_dir, 'standard/iana', data['file'])
                copy2(src, dst)

        logger.info(f'Checking module filenames without revision in {iana_standard_path}')
        dpu.check_name_no_revision_exist(iana_standard_path, logger)

        logger.info(f'Checking for early revision in {iana_standard_path}')
        dpu.check_early_revisions(iana_standard_path, logger)

        messages = []
        try:
            # Add commit and push to the forked repository
            logger.info('Adding all untracked files locally')
            untracked_files = repo.repo.untracked_files
            repo.add_untracked_remove_deleted()
            logger.info('Committing all files locally')
            repo.commit_all('Cronjob - every day pull of iana yang files')
            logger.info('Pushing files to forked repository')
            commit_hash = repo.repo.head.commit
            logger.info(f'Commit hash {commit_hash}')
            with open(commit_dir, 'w+') as f:
                f.write(f'{commit_hash}\n')
            if is_production:
                logger.info('Pushing untracked and modified files to remote repository')
                repo.push()
            else:
                logger.info('DEV environment - not pushing changes into remote repository')
                untracked_files_list = '\n'.join(untracked_files)
                logger.debug(f'List of all untracked and modified files:\n{untracked_files_list}')
        except GitCommandError as e:
            message = (
                f'Error while pushing procedure - git command error: \n {e.stderr} \n git command out: \n {e.stdout}'
            )
            if 'Your branch is up to date' in e.stdout:
                logger.warning(message)
                messages = [{'label': 'Pull request created', 'message': 'False - branch is up to date'}]
            else:
                logger.exception('Error while pushing procedure - Git command error')
                raise e
        except Exception as e:
            logger.exception(f'Error while pushing procedure {sys.exc_info()[0]}')
            raise type(e)('Error while pushing procedure')
    except Exception as e:
        logger.exception('Exception found while running draftPull script')
        raise e

    # Remove tmp folder
    logger.info('Removing tmp directory')

    if len(messages) == 0:
        messages = [{'label': 'Pull request created', 'message': f'True - {commit_hash}'}]  # pyright: ignore
    logger.info('Job finished successfully')
    return messages


if __name__ == '__main__':
    main()
