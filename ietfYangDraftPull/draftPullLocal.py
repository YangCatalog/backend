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
This python script is set as automatic cronjob
tool to parse and populate all new ietf DRAFT
and RFC modules.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import os
import subprocess
import sys
import tarfile
from datetime import datetime

import requests

import utility.log as log
from utility import repoutil, yangParser

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


def get_latest_revision(f, LOGGER):
    """
    Search for revision in yang file
    :param f: yang file
    :return: revision of the file "f"
    """
    stmt = yangParser.parse(f)
    if stmt is None: # In case of invalid YANG syntax, None is returned
        LOGGER.info('Cannot yangParser.parse ' + f)
        return None
    rev = stmt.search_one('revision')
    if rev is None:
        return None

    return rev.arg


def check_name_no_revision_exist(directory, LOGGER_temp):
    """
    This function checks the format of all the modules filename.
    If it contains module with a filename without revision,
    we check if there is a module that has revision in
    its filename. If such module exists, then module with no revision
    in filename will be removed.
    :param directory: (str) path to directory with yang modules
    """
    LOGGER = LOGGER_temp
    LOGGER.debug('Checking revision for directory: {}'.format(directory))
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if '@' in basename:
                yang_file_name = basename.split('@')[0] + '.yang'
                revision = basename.split('@')[1].split('.')[0]
                exists = os.path.exists(directory + yang_file_name)
                if exists:
                    compared_revision = get_latest_revision(os.path.abspath(directory + yang_file_name), LOGGER)
                    if compared_revision is None:
                        continue
                    if revision == compared_revision:
                        os.remove(directory + yang_file_name)


def check_early_revisions(directory, LOGGER_temp=None):
    """
    This function checks all modules revisions and keeps only
    ones that are the newest. If there are two modules with
    two different revisions, then the older one is removed.
    :param directory: (str) path to directory with yang modules
    """
    if LOGGER_temp is not None:
        LOGGER = LOGGER_temp
    for f in os.listdir(directory):
        # Extract the YANG module name from the filename
        mname = f.split('.yang')[0].split('@')[0]   # Beware of some invalid file names such as '@2015-03-09.yang'
        if mname == '':
            continue
        files_to_delete = []
        revisions = []
        for f2 in os.listdir(directory):
            # Same module name ?
            if f2.split('.yang')[0].split('@')[0] == mname:
                if f2.split(mname)[1].startswith('.') or f2.split(mname)[1].startswith('@'):
                    files_to_delete.append(f2)
                    revision = f2.split(mname)[1].split('.')[0].replace('@', '')
                    if revision == '':
                        revision = get_latest_revision(os.path.abspath(directory + f2), LOGGER)
                        if revision is None:
                            continue
                    try:
                        # Basic date extraction can fail if there are alphanumeric characters in the revision filename part
                        year = int(revision.split('-')[0])  
                        month = int(revision.split('-')[1])
                        day = int(revision.split('-')[2])
                        revisions.append(datetime(year, month, day))
                    except Exception:
                        LOGGER.error('Failed to process revision for {}: (rev: {})'.format(f2, revision))
                        if month == 2 and day == 29:
                            revisions.append(datetime(year, month, 28))
                        else:
                            continue
        # Single revision...
        if len(revisions) == 0:
            continue
        # Keep the latest (max) revision and delete the rest
        latest = revisions.index(max(revisions))
        files_to_delete.remove(files_to_delete[latest])
        for fi in files_to_delete:
            if 'iana-if-type' in fi:
                break
            os.remove(directory + fi)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    api_ip = config.get('DraftPullLocal-Section', 'api-ip')
    api_port = config.get('General-Section', 'api-port')
    confd_ip = config.get('General-Section', 'confd-ip')
    confd_port = config.get('General-Section', 'confd-port')
    credentials = config.get('General-Section', 'credentials').strip('"').split(' ')
    result_html_dir = config.get('Web-Section', 'result-html-dir')
    protocol = config.get('General-Section', 'protocol-api')
    notify = config.get('DraftPullLocal-Section', 'notify-index')
    save_file_dir = config.get('Directory-Section', 'save-file-dir')
    private_credentials = config.get('General-Section', 'private-secret').split(' ')
    token = config.get('DraftPull-Section', 'yang-catalog-token')
    username = config.get('DraftPull-Section', 'username')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    ietf_draft_url = config.get('General-Section', 'ietf-draft-private-url')
    ietf_rfc_url = config.get('General-Section', 'ietf-RFC-tar-private-url')
    yang_models_url_suffix = config.get('General-Section', 'yang-models-repo-url_suffix')
    temp_dir = config.get('Directory-Section', 'temp')
    LOGGER = log.get_logger('draftPullLocal', log_directory + '/jobs/draft-pull-local.log')
    LOGGER.info('Starting cron job IETF pull request local')

    github_credentials = ''
    if len(username) > 0:
        github_credentials = username + ':' + token + '@'

    # Fork and clone the repository YangModles/yang
    LOGGER.info('Cloning repository')
    reponse = requests.post('https://' + github_credentials + yang_models_url_suffix)
    repo = None
    try:
        repo = repoutil.RepoUtil('https://' + token + '@github.com/' + username + '/yang.git')

        repo.clone(config_name, config_email)
        LOGGER.info('Cloning repo to local directory {}'.format(repo.localdir))

        ietf_draft_json = requests.get(ietf_draft_url
                                       , auth=(private_credentials[0], private_credentials[1])).json()
        response = requests.get(ietf_rfc_url, auth=(private_credentials[0], private_credentials[1]))
        zfile = open(repo.localdir + '/rfc.tgz', 'wb')
        zfile.write(response.content)
        zfile.close()
        tar_opened = False
        tgz = ''
        try:
            tgz = tarfile.open(repo.localdir + '/rfc.tgz')
            tar_opened = True
        except tarfile.ReadError as e:
            LOGGER.warning('tarfile could not be opened. It might not have been generated yet.'
                           ' Did the sdo_analysis cron job run already?')
        if tar_opened:
            tgz.extractall(repo.localdir + '/standard/ietf/RFC')
            tgz.close()
            os.remove(repo.localdir + '/rfc.tgz')
            check_name_no_revision_exist(repo.localdir + '/standard/ietf/RFC/', LOGGER)
            check_early_revisions(repo.localdir + '/standard/ietf/RFC/', LOGGER)
            with open(temp_dir + "/log-pull-local.txt", "w") as f:
                try:
                    LOGGER.info('Calling populate script')
                    arguments = ["python", "../parseAndPopulate/populate.py", "--sdo", "--port", confd_port, "--ip",
                                 confd_ip, "--api-protocol", protocol, "--api-port", api_port, "--api-ip", api_ip,
                                 "--dir", repo.localdir + "/standard/ietf/RFC", "--result-html-dir", result_html_dir,
                                 "--credentials", credentials[0], credentials[1],
                                 "--save-file-dir", save_file_dir]
                    if notify == 'True':
                        arguments.append("--notify-indexing")
                    subprocess.check_call(arguments, stderr=f)
                except subprocess.CalledProcessError as e:
                    LOGGER.error('Error calling process populate.py {}'.format(e.cmd))
        for key in ietf_draft_json:
            yang_file = open(repo.localdir + '/experimental/ietf-extracted-YANG-modules/' + key, 'w+')
            yang_download_link = ietf_draft_json[key][2].split('href="')[1].split('">Download')[0]
            yang_download_link = yang_download_link.replace('new.yangcatalog.org', 'yangcatalog.org')

            try:
                yang_raw = requests.get(yang_download_link).text
                yang_file.write(yang_raw)
            except:
                LOGGER.warning('{} - {}'.format(key, yang_download_link))
                yang_file.write('')
            yang_file.close()
        LOGGER.info('Checking module filenames without revision in ' + repo.localdir + '/experimental/ietf-extracted-YANG-modules/')
        check_name_no_revision_exist(repo.localdir + '/experimental/ietf-extracted-YANG-modules/', LOGGER)
        LOGGER.info('Checking for early revision in ' + repo.localdir + '/experimental/ietf-extracted-YANG-modules/')
        check_early_revisions(repo.localdir + '/experimental/ietf-extracted-YANG-modules/', LOGGER)

        with open(temp_dir + "/log-pull-local2.txt", "w") as f:
            try:
                LOGGER.info('Calling populate script')
                arguments = ["python", "../parseAndPopulate/populate.py", "--sdo", "--port", confd_port, "--ip",
                             confd_ip, "--api-protocol", protocol, "--api-port", api_port, "--api-ip", api_ip,
                             "--dir", repo.localdir + "/experimental/ietf-extracted-YANG-modules",
                             "--result-html-dir", result_html_dir, "--credentials", credentials[0], credentials[1],
                             "--save-file-dir", save_file_dir]
                if notify == 'True':
                    arguments.append("--notify-indexing")
                subprocess.check_call(arguments, stderr=f)
            except subprocess.CalledProcessError as e:
                LOGGER.error('Error calling process populate.py {}'.format(e.cmd))
    except Exception as e:
        LOGGER.error("Exception found while draftPullLocal script was running")
        repo.remove()
        raise e
    repo.remove()
