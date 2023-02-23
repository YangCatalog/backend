# Copyright The IETF Trust 2023, All Rights Reserved
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
Script automatically pushes new IETF draft yang modules to the GitHub repository: https://github.com/yang-catalog/yang.
Old ones are removed and their naming is corrected to <name>@<revision>.yang. New IETF RFC modules are checked and
automatically pushed too. An e-mail with information about pushing new RFCs is sent to yangcatalog admin users if
such a thing occurs. Message about new RFC or DRAFT yang modules is also sent to the Cisco Webex Teams,
room: YANG Catalog Admin.
"""

__author__ = 'Bohdan Konovalenko'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bohdan.konovalenko@pantheon.tech'

import filecmp
import glob
import os
import shutil
import typing as t
from configparser import ConfigParser

import requests

import ietfYangDraftPull.draftPullUtility as dpu
import utility.log as log
from automatic_push.rfc_push import push_new_rfcs
from automatic_push.utility import download_draft_modules_content, push_untracked_files, update_forked_repository
from utility import message_factory, repoutil
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


def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()):
    args = script_conf.args
    config = create_config(args.config_path)
    draft_push = DraftPush(config, args.send_message)
    draft_push()


class DraftPush:
    def __init__(self, config: ConfigParser = create_config(), send_message: bool = False):
        self.send_message = send_message

        self.config = config
        self.rfc_exceptions_file_path = self.config.get('Directory-Section', 'rfc-exceptions')
        self.verified_commits_file_path = self.config.get('Directory-Section', 'commit-dir')
        self.ietf_rfc_url = self.config.get('Web-Section', 'ietf-RFC-tar-private-url')
        self.is_production = self.config.get('General-Section', 'is-prod') == 'True'
        log_directory = self.config.get('Directory-Section', 'logs')
        self.logger = log.get_logger('draft_push', f'{log_directory}/jobs/draft-push.log')

        self.repo: t.Optional[repoutil.ModifiableRepoUtil] = None

    @job_log(file_basename=BASENAME)
    def __call__(self):
        self.logger.info('Starting Cron job IETF pull request')
        self._get_repo()
        self._configure_file_paths()
        try:
            ietf_tar_extracted_successfully = self._extract_ietf_modules_tar()
            if ietf_tar_extracted_successfully:
                new_files, diff_files = self._get_new_and_diff_rfc_files()
                self._push_rfc_files(new_files, diff_files)
            self._populate_and_check_experimental_drafts()
            messages = push_untracked_files(self.repo, self.logger, self.verified_commits_file_path, self.is_production)
            self.logger.info('Job finished successfully')
            return messages
        except Exception as e:
            self.logger.exception('Exception found while running draft_push script')
            raise e

    def _get_repo(self):
        repo_name = 'yang'
        repo_token = self.config.get('Secrets-Section', 'yang-catalog-token')
        yang_models_dir = self.config.get('Directory-Section', 'yang-models-dir')
        repo_owner = self.config.get('General-Section', 'repository-username')
        repo_config_name = self.config.get('General-Section', 'repo-config-name')
        repo_config_email = self.config.get('General-Section', 'repo-config-email')
        repo_clone_options = repoutil.RepoUtil.CloneOptions(
            config_username=repo_config_name,
            config_user_email=repo_config_email,
        )
        github_repo_url = repoutil.construct_github_repo_url(repo_owner, repo_name, repo_token)
        update_forked_repository(yang_models_dir, github_repo_url, self.logger)
        repo = repoutil.clone_repo(github_repo_url, repo_clone_options, self.logger)
        if not repo:
            raise RuntimeError(f'Failed to clone repository {repo_owner}/{repo_name}')
        self.repo = repo

    def _configure_file_paths(self):
        self.tgz_path = os.path.join(self.repo.local_dir, 'rfc.tgz')
        self.temp_rfc_dir = os.path.join(self.repo.local_dir, 'standard/ietf/RFCtemp')
        self.experimental_path = os.path.join(self.repo.local_dir, 'experimental/ietf-extracted-YANG-modules')
        os.makedirs(self.experimental_path, exist_ok=True)

    def _extract_ietf_modules_tar(self) -> bool:
        response = requests.get(self.ietf_rfc_url)
        with open(self.tgz_path, 'wb') as zfile:
            zfile.write(response.content)
        return dpu.extract_rfc_tgz(self.tgz_path, self.temp_rfc_dir, self.logger)

    def _get_new_and_diff_rfc_files(self) -> tuple[list[str], list[str]]:
        diff_files = []
        new_files = []
        temp_rfc_yang_files = glob.glob(f'{self.temp_rfc_dir}/*.yang')
        for temp_rfc_yang_file in temp_rfc_yang_files:
            file_name = os.path.basename(temp_rfc_yang_file)
            rfc_yang_file = temp_rfc_yang_file.replace('RFCtemp', 'RFC')

            if not os.path.exists(rfc_yang_file):
                new_files.append(file_name)
                continue

            files_are_identical = filecmp.cmp(rfc_yang_file, temp_rfc_yang_file)
            if not files_are_identical:
                diff_files.append(file_name)
        shutil.rmtree(self.temp_rfc_dir)
        return new_files, diff_files

    def _push_rfc_files(self, new_files: list[str], diff_files: list[str]):
        try:
            with open(self.rfc_exceptions_file_path, 'r') as exceptions_file:
                remove_from_new = exceptions_file.read().split('\n')
        except FileNotFoundError:
            open(self.rfc_exceptions_file_path, 'w').close()
            os.chmod(self.rfc_exceptions_file_path, 0o664)
            remove_from_new = []
        new_files = [file_name for file_name in new_files if file_name not in remove_from_new]
        automatic_push_result = push_new_rfcs(
            new_files=new_files,
            diff_files=diff_files,
            logger=self.logger,
            forked_repo=self.repo,
            config=self.config,
        )
        if self.send_message and (new_files or diff_files):
            self.logger.info('new or modified RFC files found. Sending an E-mail')
            mf = message_factory.MessageFactory()
            automatic_push_message = (
                f'Automatic new RFCs push '
                f'{"is successful" if automatic_push_result.push_successful else "failed"}:\n'
                f'{automatic_push_result.message}'
            )
            mf.send_new_rfc_message(new_files, diff_files, automatic_push_message)

    def _populate_and_check_experimental_drafts(self):
        self.logger.info('Updating IETF drafts download links')
        download_draft_modules_content(self.experimental_path, self.config, self.logger)

        self.logger.info(f'Checking module filenames without revision in {self.experimental_path}')
        dpu.check_name_no_revision_exist(self.experimental_path, self.logger)

        self.logger.info(f'Checking for early revision in {self.experimental_path}')
        dpu.check_early_revisions(self.experimental_path, self.logger)


if __name__ == '__main__':
    main()
