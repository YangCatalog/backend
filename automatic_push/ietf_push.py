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
Script automatically pushes new IETF RFC and draft yang modules to the GitHub repository:
https://github.com/yang-catalog/yang. Old ones are removed and their naming is corrected to <name>@<revision>.yang.
An e-mail with information about local update of new RFCs is sent to yangcatalog admin users if
there are files to update. Message about new RFC yang modules is also sent to the Cisco Webex Teams,
room: YANG Catalog Admin.
"""

__author__ = 'Bohdan Konovalenko'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bohdan.konovalenko@pantheon.tech'

import filecmp
import glob
import json
import os
import shutil
import typing as t
from configparser import ConfigParser
from dataclasses import dataclass

import requests

import ietfYangDraftPull.draftPullUtility as dpu
import utility.log as log
from automatic_push.utils import get_forked_repository
from utility import message_factory, repoutil
from utility.create_config import create_config
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.util import JobLogMessage, job_log

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
    ietf_push = IetfPush(config, args.send_message)
    ietf_push()


class IetfPush:
    @dataclass
    class RFCsCommitResult:
        commit_successful: bool
        message: str

    def __init__(self, config: ConfigParser = create_config(), send_message: bool = False):
        self.send_message = send_message

        self.config = config
        self.rfc_exceptions_file_path = self.config.get('Directory-Section', 'rfc-exceptions')
        self.verified_commits_file_path = self.config.get('Directory-Section', 'commit-dir')
        self.ietf_rfc_url = self.config.get('Web-Section', 'ietf-RFC-tar-private-url')
        self.ietf_draft_url = config.get('Web-Section', 'ietf-draft-private-url')
        self.my_uri = config.get('Web-Section', 'my-uri')
        self.domain_prefix = config.get('Web-Section', 'domain-prefix')
        ietf_directory = self.config.get('Directory-Section', 'ietf-directory')
        self.rfc_directory = os.path.join(ietf_directory, 'YANG-rfc')
        self.is_production = self.config.get('General-Section', 'is-prod') == 'True'
        log_directory = self.config.get('Directory-Section', 'logs')
        self.logger = log.get_logger('ietf_push', f'{log_directory}/jobs/ietf-push.log')

        self.repo: t.Optional[repoutil.ModifiableRepoUtil] = None

    @job_log(file_basename=BASENAME)
    def __call__(self) -> list[JobLogMessage]:
        self.logger.info('Starting job to push IETF modules')
        self.repo = get_forked_repository(self.config, self.logger)
        self._configure_file_paths()
        try:
            ietf_tar_extracted_successfully = self._extract_ietf_modules_tar()
            if ietf_tar_extracted_successfully:
                new_files, diff_files = self._get_new_and_diff_rfc_files()
                self._update_rfc_files_locally(new_files, diff_files)
            self._download_and_check_experimental_drafts()
            push_result = repoutil.push_untracked_files(
                self.repo,
                'Cronjob - daily check of IETF modules.',
                self.logger,
                self.verified_commits_file_path,
                self.is_production,
            )
            if push_result.is_successful:
                messages = [JobLogMessage(label='Push is successful', message=push_result.detail)]
                self.logger.info('Job finished successfully')
            else:
                messages = [JobLogMessage(label='Push is unsuccessful', message=push_result.detail)]
                self.logger.info('Job finished unsuccessfully, push failed')
            return messages
        except Exception as e:
            self.logger.exception('Exception found while running ietf_push script')
            raise e

    def _configure_file_paths(self):
        self.tgz_path = os.path.join(self.repo.local_dir, 'rfc.tgz')
        self.temp_rfc_dir = os.path.join(self.repo.local_dir, 'standard/ietf/RFCtemp')
        self.rfc_dir = os.path.join(self.repo.local_dir, 'standard/ietf/RFC')
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

    def _update_rfc_files_locally(self, new_files: list[str], diff_files: list[str]):
        try:
            with open(self.rfc_exceptions_file_path, 'r') as exceptions_file:
                remove_from_new = exceptions_file.read().split('\n')
        except FileNotFoundError:
            open(self.rfc_exceptions_file_path, 'w').close()
            os.chmod(self.rfc_exceptions_file_path, 0o664)
            remove_from_new = []
        new_files = [file_name for file_name in new_files if file_name not in remove_from_new]
        if not new_files and not diff_files:
            return
        cwd = os.getcwd()
        os.chdir(self.rfc_dir)
        for filename in new_files + diff_files:
            file_path = os.path.join(self.rfc_directory, filename)
            filename_without_revision = f'{filename.split("@")[0]}.yang'
            if not os.path.exists(file_path):
                continue
            shutil.copy2(file_path, filename)
            if filename not in new_files:
                continue
            if os.path.islink(filename_without_revision):
                os.unlink(filename_without_revision)
            os.symlink(filename, filename_without_revision)
        os.chdir(cwd)
        if self.send_message:
            self.logger.info('new or modified RFC files found. Sending an E-mail')
            mf = message_factory.MessageFactory()
            for _ in self.repo.repo.index.diff(None, paths=self.rfc_dir):
                local_files_update_message = (
                    'RFC files are updated locally, changes must be pushed in the repo soon, '
                    'and a PullRequest must be created after successful run of GitHub Actions.'
                )
                break
            else:
                local_files_update_message = 'RFC files are not updated locally'
            mf.send_new_rfc_message(new_files, diff_files, local_files_update_message)

    def _download_and_check_experimental_drafts(self):
        self.logger.info('Updating IETF drafts download links')
        self._download_draft_modules_content()

        self.logger.info(f'Checking module filenames without revision in {self.experimental_path}')
        dpu.check_name_no_revision_exist(self.experimental_path, self.logger)

        self.logger.info(f'Checking for early revision in {self.experimental_path}')
        dpu.check_early_revisions(self.experimental_path, self.logger)

    def _download_draft_modules_content(self):
        response = requests.get(self.ietf_draft_url)
        try:
            ietf_draft_json = response.json()
        except json.decoder.JSONDecodeError:
            self.logger.error(f'Unable to get content of {os.path.basename(self.ietf_draft_url)} file')
            ietf_draft_json = {}
        for key in ietf_draft_json:
            file_path = os.path.join(self.experimental_path, key)
            yang_download_link = (
                ietf_draft_json[key]['compilation_metadata'][2]
                .split(
                    'href="',
                )[1]
                .split('">Download')[0]
            )
            yang_download_link = yang_download_link.replace(self.domain_prefix, self.my_uri)
            try:
                file_content_response = requests.get(yang_download_link)
            except ConnectionError:
                self.logger.error(f'Unable to retrieve content of: {key} - {yang_download_link}')
                continue
            if 'text/html' in file_content_response.headers['content-type']:
                self.logger.error(f'The content of "{key}" file is a broken html, download link: {yang_download_link}')
                if not os.path.exists(file_path):
                    continue
                with open(file_path, 'r') as possibly_broken_module:
                    lines = possibly_broken_module.readlines()
                    module_is_broken = '<html>' in lines[1] and '</html>' in lines[-1]
                if module_is_broken:
                    self.logger.info(f'Deleted the file because of broken content: {key} - {yang_download_link}')
                    os.remove(file_path)
                continue
            with open(file_path, 'w') as yang_file:
                yang_file.write(file_content_response.text)


if __name__ == '__main__':
    main()
