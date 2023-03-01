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
Script automatically pushes new IANA-maintained yang modules to the GitHub repository:
https://github.com/yang-catalog/yang. Old ones are removed and their naming is corrected to <name>@<revision>.yang.
"""

__author__ = 'Bohdan Konovalenko'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bohdan.konovalenko@pantheon.tech'

import os
import shutil
import subprocess
import typing as t
import xml.etree.ElementTree as ET
from configparser import ConfigParser
from shutil import copy2

import utility.log as log
from automatic_push.utils import get_forked_repository
from ietfYangDraftPull import draftPullUtility as dpu
from utility import repoutil
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
    iana_push = IanaPush(config)
    iana_push()


class IanaPush:
    def __init__(self, config: ConfigParser = create_config()):
        self.config = config
        self.verified_commits_file_path = self.config.get('Directory-Section', 'commit-dir')
        self.temp_dir = self.config.get('Directory-Section', 'temp')
        self.iana_temp_dir = os.path.join(self.temp_dir, 'iana')
        self.iana_exceptions_file_path = self.config.get('Directory-Section', 'iana-exceptions')
        self.is_production = self.config.get('General-Section', 'is-prod') == 'True'
        log_directory = self.config.get('Directory-Section', 'logs')
        self.logger = log.get_logger('iana_push', f'{log_directory}/jobs/iana-push.log')

        self.repo: t.Optional[repoutil.ModifiableRepoUtil] = None

    @job_log(file_basename=BASENAME)
    def __call__(self) -> list[JobLogMessage]:
        self.logger.info('Starting job to push IANA-maintained modules')
        self.repo = get_forked_repository(self.config, self.logger)
        self._configure_file_paths()
        self._sync_yang_parameters()
        self._parse_yang_parameters()
        self._check_iana_standard_dir()
        push_result = repoutil.push_untracked_files(
            self.repo,
            'Cronjob - daily check of IANA modules.',
            self.logger,
            self.verified_commits_file_path,
            self.is_production,
        )
        self.logger.info('Removing tmp directory')
        if os.path.exists(self.iana_temp_dir):
            shutil.rmtree(self.iana_temp_dir)
        if push_result.is_successful:
            messages = [JobLogMessage(label='Push is successful', message=push_result.detail)]
            self.logger.info('Job finished successfully')
        else:
            messages = [JobLogMessage(label='Push is unsuccessful', message=push_result.detail)]
            self.logger.info('Job finished unsuccessfully, push failed')
        return messages

    def _configure_file_paths(self):
        self.iana_standard_dir = os.path.join(self.repo.local_dir, 'standard/iana')
        os.makedirs(self.iana_standard_dir, exist_ok=True)
        self.yang_parameters_path = os.path.join(self.iana_standard_dir, 'yang-parameters.xml')
        if not os.path.exists(self.iana_exceptions_file_path):
            open(self.iana_exceptions_file_path, 'w').close()
            os.chmod(self.iana_exceptions_file_path, 0o664)

    def _sync_yang_parameters(self):
        if os.path.exists(self.iana_temp_dir):
            shutil.rmtree(self.iana_temp_dir)
        subprocess.call(
            ['rsync', '-avzq', '--delete', 'rsync.iana.org::assignments/yang-parameters/', self.iana_temp_dir],
        )
        dpu.set_permissions(self.iana_temp_dir)
        xml_path = os.path.join(self.iana_temp_dir, 'yang-parameters.xml')
        copy2(xml_path, self.yang_parameters_path)

    def _parse_yang_parameters(self):
        with open(self.iana_exceptions_file_path, 'r') as exceptions_file:
            remove_from_new = exceptions_file.read().split('\n')
        root = ET.parse(self.yang_parameters_path).getroot()
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
                src = os.path.join(self.iana_temp_dir, data['file'])
                dst = os.path.join(self.iana_standard_dir, data['file'])
                copy2(src, dst)

    def _check_iana_standard_dir(self):
        self.logger.info(f'Checking module filenames without revision in {self.iana_standard_dir}')
        dpu.check_name_no_revision_exist(self.iana_standard_dir, self.logger)

        self.logger.info(f'Checking for early revision in {self.iana_standard_dir}')
        dpu.check_early_revisions(self.iana_standard_dir, self.logger)


if __name__ == '__main__':
    main()
