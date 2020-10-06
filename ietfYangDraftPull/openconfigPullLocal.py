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
import time

import utility.log as log
from utility import repoutil, yangParser
from utility.util import job_log

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

class ScriptConfig():
    def __init__(self):
        self.help = 'Run populate script on all openconfig files to parse all modules and populate the' \
                    ' metadata to yangcatalog if there are any new. This runs as a daily cronjob'
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

    def get_help(self):
        ret = {}
        ret['help'] = self.help
        ret['options'] = {}
        ret['options']['config_path'] = 'Set path to config file'
        return ret


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
    start_time = int(time.time())
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
    api_protocol = config.get('General-Section', 'protocol-api')
    is_uwsgi = config.get('General-Section', 'uwsgi')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    log_directory = config.get('Directory-Section', 'logs')
    temp_dir = config.get('Directory-Section', 'temp')
    openconfig_repo_url = config.get('Web-Section', 'openconfig-models-repo-url')
    LOGGER = log.get_logger('openconfigPullLocal', log_directory + '/jobs/openconfig-pull.log')
    LOGGER.info('Starting Cron job openconfig pull request local')

    separator = ':'
    suffix = api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(api_protocol, api_ip,
                                                   separator, suffix)

    repo = None
    try:
        repo = repoutil.RepoUtil(openconfig_repo_url)

        repo.clone(config_name, config_email)
        LOGGER.info('Repository cloned to local directory {}'.format(repo.localdir))

        modules = []

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
                    modules.append(mod)
        output = json.dumps({'modules': {'module': modules}})
    except Exception as e:
        LOGGER.error('Exception found while running openconfigPullLocal script')
        job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
        if repo is not None:
            repo.remove()
        raise e
    repo.remove()
    LOGGER.debug(output)
    api_path = '{}modules'.format(yangcatalog_api_prefix)
    response = requests.put(api_path, output, auth=(credentials[0], credentials[1]),
                  headers={'Content-Type': 'application/json'})

    status_code = response.status_code
    if status_code < 200 or status_code > 299:
        e = 'PUT /api/modules responsed with status code {}'.format(status_code)
        job_log(start_time, temp_dir, error=str(e), status='Fail', filename=os.path.basename(__file__))
        LOGGER.info('Job finished, but an error occured while sending PUT to /api/modules')
    else:
        job_log(start_time, temp_dir, status='Success', filename=os.path.basename(__file__))
        LOGGER.info('Job finished successfully')


if __name__ == "__main__":
    main()
