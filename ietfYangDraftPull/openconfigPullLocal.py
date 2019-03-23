"""
This python script is a tool to parse and populate
all new openconfig modules.
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
import json
import os
import sys

import requests

import utility.log as log
from utility import repoutil, yangParser

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


def resolve_revision(yang_file):
    """
    search for revision in file "yang_file"
    :param yang_file: yang file
    :return: revision of the yang file
    """
    try:
        parsed_yang = yangParser.parse(os.path.abspath(yang_file))
        revision = parsed_yang.search('revision')[0].arg
    except:
        revision = '1970-01-01'
    return revision


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-path', type=str,
                        default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    api_ip = config.get('DraftPullLocal-Section', 'api-ip')
    api_port = int(config.get('General-Section', 'api-port'))
    credentials = config.get('General-Section', 'credentials').split(' ')
    token = config.get('DraftPull-Section', 'yang-catalog-token')
    username = config.get('DraftPull-Section', 'username')
    api_protocol = config.get('General-Section', 'protocol-api')
    is_uwsgi = config.get('General-Section', 'uwsgi')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    openconfig_models_forked_url = config.get('General-Section', 'openconfig-models-forked-repo-url')
    openconfig_models_url_suffix = config.get('General-Section', 'openconfig-models-repo-url_suffix')
    LOGGER = log.get_logger('openconfigPullLocal', log_directory + '/jobs/openconfig-pull.log')
    LOGGER.info('Starting Cron job openconfig pull request local')

    separator = ':'
    suffix = api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(api_protocol, api_ip,
                                                   separator, suffix)
    github_credentials = ''
    if len(username) > 0:
        github_credentials = username + ':' + token + '@'

    LOGGER.info('Forking repository')
    reponse = requests.post(
        'https://' + github_credentials + openconfig_models_url_suffix)
    repo = repoutil.RepoUtil('https://' + token + '@github.com/' + username + '/public.git')

    repo.clone(config_name, config_email)
    LOGGER.info('Repository cloned to local directory {}'.format(repo.localdir))

    mods = []

    for root, dirs, files in os.walk(repo.localdir + '/release/models/'):
        for basename in files:
            if '.yang' in basename:
                mod = {}
                name = basename.split('.')[0].split('@')[0]
                mod['generated-from'] = 'not-applicable'
                mod['module-classification'] = 'unknown'
                mod['name'] = name
                mod['revision'] = resolve_revision('{}/{}'.format(root,
                                                                  basename))
                path = root.split(repo.localdir)[1].replace('/', '', 1)
                if not path.endswith('/'):
                    path += '/'
                path += basename
                mod['organization'] = 'openconfig'
                mod['source-file'] = {'owner': 'openconfig', 'path': path,
                                      'repository': 'public'}
                mods.append(mod)
    output = json.dumps({'modules': {'module': mods}})
    requests.delete(openconfig_models_forked_url,
                    headers={'Authorization': 'token ' + token})
    repo.remove()
    LOGGER.info(output)
    api_path = '{}modules'.format(yangcatalog_api_prefix)
    requests.patch(api_path, output, auth=(credentials[0], credentials[1]),
                  headers={'Content-Type': 'application/json'})
