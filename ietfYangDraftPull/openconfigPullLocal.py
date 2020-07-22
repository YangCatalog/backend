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
This python script is a tool to parse and populate
all new openconfig modules.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
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

class ScriptConfig():
    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--config-path', type=str,
                            default='/etc/yangcatalog/yangcatalog.conf',
                            help='Set path to config file')
        self.args = parser.parse_args()
        self.defaults = [parser.get_default(key) for key in self.args.__dict__.keys()]

    def get_args_list(self):
        args_dict = {}
        keys = [key for key in self.args.__dict__.keys()]
        types = [type(value).__name__ for value in self.args.__dict__.values()]

        i = 0
        for key in keys:
            args_dict[key] = dict(type=types[i], default=self.defaults[i])
            i += 1
        return args_dict

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


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args

    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    api_ip = config.get('Web-Section', 'ip')
    api_port = int(config.get('Web-Section', 'api-port'))
    credentials = config.get('Secrets-Section', 'confd-credentials').strip('"').split(' ')
    token = config.get('Secrets-Section', 'yang-catalog-token')
    username = config.get('General-Section', 'repository-username')
    api_protocol = config.get('General-Section', 'protocol-api')
    is_uwsgi = config.get('General-Section', 'uwsgi')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    openconfig_models_forked_url = config.get('Web-Section', 'openconfig-models-forked-repo-url')
    openconfig_models_url_suffix = config.get('Web-Section', 'openconfig-models-repo-url-suffix')
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

    requests.delete('{}/public'.format(openconfig_models_forked_url), headers={'Authorization': 'token ' + token})
    LOGGER.info('Forking repository')
    response = requests.post('https://' + github_credentials + openconfig_models_url_suffix)
    repo_name = response.json()['name']

    repo = None
    try:
        repo = repoutil.RepoUtil('https://' + token + '@github.com/' + username + '/{}.git'.format(repo_name))

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
    except Exception as e:
        LOGGER.error("Exception found while running openconfigPullLocal script running")
        requests.delete('{}/{}'.format(openconfig_models_forked_url, repo_name),
                        headers={'Authorization': 'token ' + token})
        if repo is not None:
            repo.remove()
        raise e
    LOGGER.info('Removing {}/{} repository'.format(openconfig_models_forked_url, repo_name))
    requests.delete('{}/{}'.format(openconfig_models_forked_url, repo_name),
                    headers={'Authorization': 'token ' + token})
    repo.remove()
    LOGGER.debug(output)
    api_path = '{}modules'.format(yangcatalog_api_prefix)
    requests.put(api_path, output, auth=(credentials[0], credentials[1]),
                  headers={'Content-Type': 'application/json'})
    LOGGER.info("Job finished successfully")


if __name__ == "__main__":
    main()
