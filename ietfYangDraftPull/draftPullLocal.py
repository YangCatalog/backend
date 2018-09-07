"""
This python script is set as automatic cronjob
tool to parse and populate all new ietf DRAFT
and RFC modules.
"""
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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
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
from utility import yangParser, repoutil

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


def get_latest_revision(f):
    """
    Search for revision in yang file
    :param f: yang file
    :return: revision of the file "f"
    """
    stmt = yangParser.parse(f)

    rev = stmt.search_one('revision')
    if rev is None:
        return None

    return rev.arg


def check_name_no_revision_exist(directory):
    """
    This method checks all the modules name format.
    If it contains module with name that has no revision
    we check if there is a module that has revision in
    its name. If such module exist module with no revision
    in name will be removed
    :param directory: (str) path to directory with yang modules
    """
    LOGGER.info('Checking revision for directory: {}'.format(directory))
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if '@' in basename:
                yang_file_name = basename.split('@')[0] + '.yang'
                revision = basename.split('@')[1].split('.')[0]
                exists = os.path.exists(directory + yang_file_name)
                if exists:
                    compared_revision = get_latest_revision(os.path.abspath(directory + yang_file_name))
                    if compared_revision is None:
                        continue
                    if revision == compared_revision:
                        os.remove(directory + yang_file_name)


def check_early_revisions(directory):
    """
    This method check all modules revisions and keeps only
    ones that are the newest. If there are same modules with
    two different revision, older one will be removed
    :param directory: (str) path to directory with yang modules
    """
    for f in os.listdir(directory):
        fname = f.split('.yang')[0].split('@')[0]
        files_to_delete = []
        revisions = []
        for f2 in os.listdir(directory):
            if f2.split('.yang')[0].split('@')[0] == fname:
                if f2.split(fname)[1].startswith('.') or f2.split(fname)[1].startswith('@'):
                    files_to_delete.append(f2)
                    revision = f2.split(fname)[1].split('.')[0].replace('@', '')
                    if revision == '':
                        revision = get_latest_revision(os.path.abspath(directory + f2))
                        if revision is None:
                            continue
                    year = int(revision.split('-')[0])
                    month = int(revision.split('-')[1])
                    day = int(revision.split('-')[2])
                    try:
                        revisions.append(datetime(year, month, day))
                    except Exception:
                        LOGGER.error('Failed to process revision for {}: (rev: {})'.format(f2, revision))
                        if month == 2 and day == 29:
                            revisions.append(datetime(year, month, 28))
        if len(revisions) == 0:
            continue
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
    credentials = config.get('General-Section', 'credentials').split(' ')
    result_html_dir = config.get('DraftPullLocal-Section', 'result-html-dir')
    protocol = config.get('General-Section', 'protocol-api')
    notify = config.get('DraftPullLocal-Section', 'notify-index')
    save_file_dir = config.get('Directory-Section', 'backup')
    private_credentials = config.get('General-Section', 'private-secret').split(' ')
    token = config.get('DraftPull-Section', 'yang-catalog-token')
    username = config.get('DraftPull-Section', 'username')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    ietf_models_url_suffix = config.get('General-Section', 'ietf-models-repo-url_suffix')
    ietf_draft_url = config.get('General-Section', 'ietf-draft-private-url')
    ietf_rfc_url = config.get('General-Section', 'ietf-RFC-tar-private-url')
    LOGGER = log.get_logger('draftPullLocal', log_directory + '/draft-pull-local.log')
    LOGGER.info('Starting Cron job IETF pull request local')

    github_credentials = ''
    if len(username) > 0:
        github_credentials = username + ':' + token + '@'

    # Fork and clone the repository YangModles/yang
    LOGGER.info('Forking repository')
    reponse = requests.post(
        'https://' + github_credentials + yang_models_url_suffix)
    repo = repoutil.RepoUtil(
        'https://' + token + '@github.com/' + username + '/yang.git')

    LOGGER.info('Cloning repo to local directory {}'.format(repo.localdir))
    repo.clone(config_name, config_email)

    ietf_draft_json = requests.get(ietf_draft_url
                                   , auth=(private_credentials[0], private_credentials[1])).json()
    response = requests.get(ietf_rfc_url, auth=(private_credentials[0], private_credentials[1]))
    zfile = open(repo.localdir + '/rfc.tgz', 'wb')
    zfile.write(response.content)
    zfile.close()
    tgz = tarfile.open(repo.localdir + '/rfc.tgz')
    tgz.extractall(repo.localdir + '/standard/ietf/RFC')
    tgz.close()
    os.remove(repo.localdir + '/rfc.tgz')
    check_name_no_revision_exist(repo.localdir + '/standard/ietf/RFC/')
    check_early_revisions(repo.localdir + '/standard/ietf/RFC/')
    with open("log.txt", "wr") as f:
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
            LOGGER.error('Error calling process populate.py {}'.format(e.stdout))
    for key in ietf_draft_json:
        yang_file = open(repo.localdir + '/experimental/ietf-extracted-YANG-modules/' + key, 'w+')
        yang_download_link = ietf_draft_json[key][2].split('href="')[1].split('">Download')[0]
        try:
            yang_raw = requests.get(yang_download_link).text
            yang_file.write(yang_raw)
        except:
            LOGGER.warning('{} - {}'.format(key, yang_download_link))
            yang_file.write('')
        yang_file.close()
    check_name_no_revision_exist(repo.localdir + '/experimental/ietf-extracted-YANG-modules/')
    check_early_revisions(repo.localdir + '/experimental/ietf-extracted-YANG-modules/')

    with open("log.txt", "wr") as f:
        try:
            LOGGER.info('Calling populate script')
            arguments = ["python", "../parseAndPopulate/populate.py", "--sdo", "--port", confd_port, "--ip",
                         confd_ip, "--api-protocol", protocol, "--api-port", api_port, "--api-ip", api_ip,
                         "--dir", repo.localdir + "/../../experimental/ietf-extracted-YANG-modules",
                         "--result-html-dir", result_html_dir, "--credentials", credentials[0], credentials[1],
                         "--save-file-dir", save_file_dir]
            if notify == 'True':
                arguments.append("--notify-indexing")
            subprocess.check_call(arguments, stderr=f)
        except subprocess.CalledProcessError as e:
            LOGGER.error('Error calling process populate.py {}'.format(e.stdout))
    repo.remove()
