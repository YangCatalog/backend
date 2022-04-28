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
import time
import typing as t
import xml.etree.ElementTree as ET
from shutil import copy2

import utility.log as log
from git.exc import GitCommandError
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.util import job_log

from ietfYangDraftPull import draftPullUtility


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        help = 'Pull the latest IANA-maintained files and add them to the Github if there are any new.'
        args: t.List[Arg] = [{
            'flag': '--config-path',
            'help': 'Set path to config file',
            'type': str,
            'default': os.environ['YANGCATALOG_CONFIG_PATH']
        }]
        super().__init__(help, args, None if __name__ == '__main__' else [])


def main(scriptConf=None):
    start_time = int(time.time())
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args

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
    is_production = config.get('General-Section', 'is-prod')
    is_production = is_production == 'True'
    LOGGER = log.get_logger('ianaPull', '{}/jobs/iana-pull.log'.format(log_directory))
    LOGGER.info('Starting job to pull IANA-maintained modules')

    repo_name = 'yang'
    repourl = 'https://{}@github.com/{}/{}.git'.format(token, username, repo_name)
    commit_author = {
        'name': config_name,
        'email': config_email
    }

    draftPullUtility.update_forked_repository(yang_models, LOGGER)
    repo = draftPullUtility.clone_forked_repository(repourl, commit_author, LOGGER)

    if not repo:
        error_message = 'Failed to clone repository {}/{}'.format(username, repo_name)
        job_log(start_time, temp_dir, error=error_message, status='Fail', filename=os.path.basename(__file__))
        sys.exit()

    try:
        iana_temp_path = os.path.join(temp_dir, 'iana')
        if os.path.exists(iana_temp_path):
            shutil.rmtree(iana_temp_path)
        # call rsync to sync with rsync.iana.org::assignments/yang-parameters/
        subprocess.call(['rsync', '-avzq', '--delete', 'rsync.iana.org::assignments/yang-parameters/', iana_temp_path])
        draftPullUtility.set_permissions(iana_temp_path)
        iana_standard_path = os.path.join(repo.local_dir, 'standard/iana')
        if not os.path.exists(iana_standard_path):
            os.makedirs(iana_standard_path)
        xml_path = os.path.join(iana_temp_path, 'yang-parameters.xml')
        copy2(xml_path, '{}/standard/iana/yang-parameters.xml'.format(repo.local_dir))

        # Parse yang-parameters.xml file
        root = ET.parse(xml_path).getroot()
        tag = root.tag
        namespace = tag.split('registry')[0]
        modules = root.iter('{}record'.format(namespace))

        for module in modules:
            data = module.attrib
            for attributes in module:
                prop = attributes.tag.split(namespace)[-1]
                data[prop] = attributes.text or ''

            if data.get('iana') == 'Y' and 'file' in data:
                src = '{}/{}'.format(iana_temp_path, data['file'])
                dst = '{}/standard/iana/{}'.format(repo.local_dir, data['file'])
                copy2(src, dst)

        LOGGER.info('Checking module filenames without revision in {}'.format(iana_standard_path))
        draftPullUtility.check_name_no_revision_exist(iana_standard_path, LOGGER)

        LOGGER.info('Checking for early revision in {}'.format(iana_standard_path))
        draftPullUtility.check_early_revisions(iana_standard_path, LOGGER)

        messages = []
        try:
            # Add commit and push to the forked repository
            LOGGER.info('Adding all untracked files locally')
            untracked_files = repo.repo.untracked_files
            repo.add_untracked_remove_deleted()
            LOGGER.info('Committing all files locally')
            repo.commit_all('Cronjob - every day pull of iana yang files')
            LOGGER.info('Pushing files to forked repository')
            commit_hash = repo.repo.head.commit
            LOGGER.info('Commit hash {}'.format(commit_hash))
            with open(commit_dir, 'w+') as f:
                f.write('{}\n'.format(commit_hash))
            if is_production:
                LOGGER.info('Pushing untracked and modified files to remote repository')
                repo.push()
            else:
                LOGGER.info('DEV environment - not pushing changes into remote repository')
                LOGGER.debug('List of all untracked and modified files:\n{}'.format('\n'.join(untracked_files)))
        except GitCommandError as e:
            message = 'Error while pushing procedure - git command error: \n {} \n git command out: \n {}'.format(e.stderr, e.stdout)
            if 'Your branch is up to date' in e.stdout:
                LOGGER.warning(message)
                messages = [
                    {'label': 'Pull request created', 'message': 'False - branch is up to date'}
                ]
            else:
                LOGGER.exception('Error while pushing procedure - Git command error')
                raise e
        except Exception as e:
            LOGGER.exception(
                'Error while pushing procedure {}'.format(sys.exc_info()[0]))
            raise type(e)('Error while pushing procedure')
    except Exception as e:
        LOGGER.exception('Exception found while running draftPull script')
        job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
        raise e

    # Remove tmp folder
    LOGGER.info('Removing tmp directory')

    if len(messages) == 0:
        messages = [
            {'label': 'Pull request created', 'message': 'True - {}'.format(commit_hash)} # pyright: ignore
        ]
    job_log(start_time, temp_dir, messages=messages, status='Success', filename=os.path.basename(__file__))
    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
