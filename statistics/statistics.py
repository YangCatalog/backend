"""
This script will find all the sdos and vendors and creates a
html file with statistics for specific organizations.

The statistics include number of modules in github,
number of modules in catalog, percentage that passes
compilation and for vendor Cisco we have information
about what platforms are supported for specific version
of specific OS-type

The html file also contains general statistics like
number of vendor yang files, number of unique yang files,
number of yang files in yang-catalog...
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
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time

import jinja2
import requests

import utility.log as log
from utility import yangParser, repoutil

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

LOGGER = log.get_logger('statistics', '/home/miroslav/log/jobs/yang.log')

NS_MAP = {
    "http://cisco.com/ns/yang/": "cisco",
    "http://www.huawei.com/netconf": "huawei",
    "http://openconfig.net/yang/": "openconfig",
    "http://tail-f.com/": "tail-f",
    "http://yang.juniper.net/": "juniper"
}
MISSING_ELEMENT = 'independent'


def find_first_file(directory, pattern, pattern_with_revision):
    """Search for yang file on path
        Arguments:
            :param directory: (str) directory which should be search recursively
                for specified file.
            :param pattern: (str) name of the yang file without revision
            :param pattern_with_revision: (str) name of the yang file with
                revision
            :return path to a searched yang file
    """

    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern_with_revision):
                filename = os.path.join(root, basename)
                return filename
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                return filename


def render(tpl_path, context):
    """Render jinja html template
        Arguments:
            :param tpl_path: (str) path to a file
            :param context: (dict) dictionary containing data to render jinja
                template file
            :return: string containing rendered html file
    """

    path, filename = os.path.split(tpl_path)
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(path or './')
    ).get_template(filename).render(context)


def list_of_yang_modules_in_subdir(srcdir):
    """
    Returns the list of YANG Modules (.yang) in all sub-directories
        Arguments
            :param srcdir: (str) root directory to search for yang files
            :return: list of YANG files
    """
    ll = []
    for root, dirs, files in os.walk(srcdir):
        for f in files:
            if f.endswith(".yang"):
                ll.append(os.path.join(root, f))
    return ll


def get_specifics(path_dir):
    """Get amount of yang files in specified directory and the amount that
    passed compilation
        Arguments:
            :param path_dir: (str) path to directory where we are searching for
                yang files
            :return: list containing amount of yang files and amount that pass
                compilation respectively
    """
    passed = 0
    num_in_catalog = 0
    yang_modules = list_of_yang_modules_in_subdir(path_dir)
    yang_modules_length = len(yang_modules)
    x = 0
    for mod_git in yang_modules:
        x += 1
        LOGGER.info("{} out of {} getting specifics from {}".format(x, yang_modules_length, path_dir))
        try:
            revision = yangParser.parse(os.path.abspath(mod_git)).search('revision')[0].arg
        except:
            continue
        organization = resolve_organization(mod_git)
        name = mod_git.split('/')[-1].split('.')[0].split('@')[0]
        if revision is None:
            revision = '1970-01-01'
        if name is None or organization is None:
            continue
        if ',' in organization:
            organization = organization.replace(' ', '%20')
            path = '{}search/name/{}'.format(yangcatalog_api_prefix, name)
            module_exist = requests.get(path, auth=(auth[0], auth[1]),
                                        headers={'Accept': 'application/vnd.yang.data+json',
                                                 'Content-Type': 'application/vnd.yang.data+json'})
            if repr(module_exist.status_code).startswith('20'):
                data = module_exist.json()
                org = data['yang-catalog:modules']['module'][0]['organization']
                rev = data['yang-catalog:modules']['module'][0]['revision']
                status = data['yang-catalog:modules']['module'][0].get('compilation-status')
                if org == organization and rev == revision:
                    if 'passed' == status:
                        passed += 1
                    num_in_catalog += 1
            else:
                LOGGER.error('Could not send request with path {}'.format(path))
        else:
            organization = organization.replace(' ', '%20')
            mod = '{}@{}_{}'.format(name, revision, organization)
            data = all_modules_data_unique.get(mod)
            if data is not None:
                if 'passed' == data.get('compilation-status'):
                    passed += 1
                num_in_catalog += 1
            else:
                LOGGER.error('module does not exist '.format(mod))
    return [num_in_catalog, passed]


def resolve_organization(path):
    """Parse yang file and resolve organization out of the module. If the module
    is a submodule find it's parent and resolve its organization
            Arguments: 
                :param path: (str) path to a file to parse and resolve a organization
                :return: list containing amount of yang files and amount that pass
                    compilation respectively
    """
    organization = ''
    try:
        namespace = yangParser.parse(os.path.abspath(path)) \
            .search('namespace')[0].arg

        for ns, org in NS_MAP.items():
            if ns in namespace:
                organization = org
        if organization == '':
            if 'urn:' in namespace:
                organization = namespace.split('urn:')[1].split(':')[0]
        if organization == '':
            organization = MISSING_ELEMENT
    except:
        while True:
            try:
                belongs_to = yangParser.parse(os.path.abspath(path)) \
                    .search('belongs-to')[0].arg
            except:
                break
            try:
                yang_file = find_first_file('/'.join(path.split('/')[:-1]), belongs_to + '.yang'
                                            , belongs_to + '@*.yang')
                namespace = yangParser.parse(os.path.abspath(yang_file)).search('namespace')[0].arg
                for ns, org in NS_MAP.items():
                    if ns in namespace:
                        organization = org
                if organization == '':
                    if 'urn:' in namespace:
                        organization = namespace.split('urn:')[1].split(':')[0]
                if organization == '':
                    organization = MISSING_ELEMENT
                break
            except:
                try:
                    yang_file = find_first_file('/'.join(path.split('/')[:-2]), belongs_to + '.yang'
                                                , belongs_to + '@*.yang')
                    namespace = yangParser.parse(os.path.abspath(yang_file)).search('namespace')[0].arg
                    for ns, org in NS_MAP.items():
                        if ns in namespace:
                            organization = org
                    if organization == '':
                        if 'urn:' in namespace:
                            organization = namespace.split('urn:')[1].split(':')[0]
                    if organization == '':
                        organization = MISSING_ELEMENT
                    break
                except:
                    organization = MISSING_ELEMENT
    return organization


def process_data(out, save_list, path, name):
    """Process all the data out of output from runYANGallstats and Yang files themself
        Arguments: 
            :param out: (str) output from runYANGallstats
            :param save_list: (list) list to which we are saving all the informations 
            :param path: (str) path to a directory to which we are creating statistics
            :param name: (str) name of the vendor or organization that we are creating
                statistics for
    """
    LOGGER.info('Getting info from {}'.format(name))
    out = out.decode('utf-8')
    table_sdo = {}
    if name is 'openconfig':
        modules = 0
    else:
        modules = out.split(path + ' : ')[1].split('\n')[0]
    num_in_catalog, passed = get_specifics(path)
    table_sdo['name'] = name
    table_sdo['num_gituhub'] = modules
    table_sdo['num_catalog'] = num_in_catalog
    try:
        table_sdo['percentage_compile'] = repr(round((float(passed) / num_in_catalog) * 100, 2)) + ' %'
    except ZeroDivisionError:
        table_sdo['percentage_compile'] = 0
    table_sdo['percentage_extra'] = 'unknown'
    save_list.append(table_sdo)


def solve_platforms(path, platform):
    """
    Resolve all the platforms on specified path and fills the platform
    set variable with the found data
    :param path: (str) path to a specific Cisco platform
    :param platform: (set) empty set of platforms. This should return
        filled with platforms data on specified path
    """
    matches = []
    for root, dirnames, filenames in os.walk(path):
        for filename in fnmatch.filter(filenames, 'platform-metadata.json'):
            matches.append(os.path.join(root, filename))
    for match in matches:
        with open(match) as f:
            js_objs = json.load(f)['platforms']['platform']
            for js_obj in js_objs:
                platform.add(js_obj['name'])


if __name__ == '__main__':
    timeBefore = time.clock()
    LOGGER.info('Starting statistics')
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog.conf',
                        help='Set path to config file')
    LOGGER.info('Loading all configuration')
    args = parser.parse_args()
    config_path = os.path.abspath('.') + '/' + args.config_path
    config = ConfigParser.ConfigParser()
    config.read(config_path)
    protocol = config.get('General-Section', 'protocol-api')
    api_ip = config.get('Statistics-Section', 'api-ip')
    api_port = config.get('General-Section', 'api-port')
    credentials = config.get('General-Section', 'credentials')
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    move_to = config.get('Statistics-Section', 'file-location')
    auth = credentials.split(' ')
    is_uwsgi = config.get('General-Section', 'uwsgi')
    separator = ':'
    suffix = api_port
    if is_uwsgi == 'True':
        separator = '/'
        suffix = 'api'
    yangcatalog_api_prefix = '{}://{}{}{}/'.format(protocol, api_ip,
                                                   separator, suffix)
    LOGGER.info('Cloning the repo')
    repo = repoutil.RepoUtil('https://github.com/YangModels/yang.git')
    try:
        repo.clone(config_name, config_email)
        repo.updateSubmodule()

        xr = set()
        nx = set()
        xe = set()

        solve_platforms(repo.localdir + '/vendor/cisco/xr', xr)
        solve_platforms(repo.localdir + '/vendor/cisco/xe', xe)
        solve_platforms(repo.localdir + '/vendor/cisco/nx', nx)

        xr_versions = sorted(next(os.walk(repo.localdir + '/vendor/cisco/xr'))[1])
        nx_versions = sorted(next(os.walk(repo.localdir + '/vendor/cisco/nx'))[1])
        xe_versions = sorted(next(os.walk(repo.localdir + '/vendor/cisco/xe'))[1])
        xr_values = []
        nx_values = []
        xe_values = []

        for version in xr_versions:
            j = None
            try:
                with open(repo.localdir + '/vendor/cisco/xr/' + version + '/platform-metadata.json', 'r') as f:
                    j = json.load(f)
                    j = j['platforms']['platform']
            except:
                j = []

            values = [version]
            for value in xr:
                if version == '':
                    ver = ''
                else:
                    ver = '.'.join(version)
                found = False
                for platform in j:
                    if (platform['name'] == value and
                            platform['software-version'] == ver):
                        values.append('<i class="fa fa-check"></i>')
                        found = True
                        break
                if not found:
                    values.append('<i class="fa fa-times"></i>')
            xr_values.append(values)

        for version in xe_versions:
            j = None
            try:
                with open(repo.localdir + '/vendor/cisco/xe/' + version + '/platform-metadata.json', 'r') as f:
                    j = json.load(f)
                    j = j['platforms']['platform']
            except:
                j = []
            values = [version]
            for value in xe:
                found = False
                for platform in j:
                    if (platform['name'] == value and
                            ''.join(platform['software-version'].split('.')) == version):
                        values.append('<i class="fa fa-check"></i>')
                        found = True
                        break
                if not found:
                    values.append('<i class="fa fa-times"></i>')
            xe_values.append(values)

        for version in nx_versions:
            j = None
            try:
                with open(repo.localdir + '/vendor/cisco/nx/' + version + '/platform-metadata.json', 'r') as f:
                    j = json.load(f)
                    j = j['platforms']['platform']
            except:
                j = []
            values = [version]
            for value in nx:
                ver = version.split('-')
                try:
                    ver = '{}({}){}({})'.format(ver[0], ver[1], ver[2], ver[3])
                except IndexError:
                    LOGGER.warning("cisco-nx software version different then others. Trying another format")
                    ver = '{}({})'.format(ver[0], ver[1])
                found = False
                for platform in j:
                    if (platform['name'] == value and
                            platform['software-version'] == ver):
                        values.append('<i class="fa fa-check"></i>')
                        found = True
                        break
                if not found:
                    values.append('<i class="fa fa-times"></i>')
            nx_values.append(values)

        path = yangcatalog_api_prefix + 'search/modules'
        all_modules_data = (requests.get(path, auth=(auth[0], auth[1]),
                                         headers={'Accept': 'application/json'})
                            .json())
        all_modules_data_unique = {}
        for mod in all_modules_data['module']:
            name = mod['name']
            revision = mod['revision']
            org = mod['organization']
            all_modules_data_unique['{}@{}_{}'.format(name, revision, org)] = mod
        all_modules_data = len(all_modules_data['module'])

        # Vendors sparately
        vendor_list = []

        process = subprocess.Popen(
            ['python', '../runYANGallstats/runYANGallstats.py', '--rootdir', repo.localdir + '/vendor/cisco',
             '--removedup', 'True'], stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, vendor_list, repo.localdir + '/vendor/cisco', 'cisco')

        process = subprocess.Popen(
            ['python', '../runYANGallstats/runYANGallstats.py', '--rootdir', repo.localdir + '/vendor/ciena',
             '--removedup', 'True'], stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, vendor_list, repo.localdir + '/vendor/ciena', 'ciena')

        process = subprocess.Popen(
            ['python', '../runYANGallstats/runYANGallstats.py', '--rootdir', repo.localdir + '/vendor/juniper',
             '--removedup', 'True'], stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, vendor_list, repo.localdir + '/vendor/juniper', 'juniper')

        process = subprocess.Popen(
            ['python', '../runYANGallstats/runYANGallstats.py', '--rootdir', repo.localdir + '/vendor/huawei',
             '--removedup', 'True'], stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, vendor_list, repo.localdir + '/vendor/huawei', 'huawei')

        # Vendors all together
        process = subprocess.Popen(
            ['python', '../runYANGallstats/runYANGallstats.py', '--rootdir', repo.localdir + '/vendor',
             '--removedup', 'True'], stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = out.decode('utf-8')
        vendor_modules = out.split(repo.localdir + '/vendor : ')[1].split('\n')[0]
        vendor_modules_ndp = out.split(repo.localdir + '/vendor (duplicates removed): ')[1].split('\n')[0]

        # Standard all together
        process = subprocess.Popen(
            ['python', '../runYANGallstats/runYANGallstats.py', '--rootdir', repo.localdir + '/standard',
             '--removedup', 'True'], stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = out.decode('utf-8')
        standard_modules = out.split(repo.localdir + '/standard : ')[1].split('\n')[0]
        standard_modules_ndp = out.split(repo.localdir + '/standard (duplicates removed): ')[1].split('\n')[0]

        # Standard separately
        sdo_list = []
        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/standard/ietf/RFC', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/standard/ietf/RFC', 'IETF RFCs')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/standard/ietf/DRAFT', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/standard/ietf/DRAFT', 'IETF drafts')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/experimental/ietf-extracted-YANG-modules', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/experimental/ietf-extracted-YANG-modules',
                     'IETF experimental drafts')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/standard/bbf/standard', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/standard/bbf/standard', 'BBF standard')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/standard/bbf/draft', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/standard/bbf/draft', 'BBF draft')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/standard/ieee/802.1', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/standard/ieee/802.1', 'IEEE 802.1 with par')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/experimental/ieee/802.1', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/experimental/ieee/802.1', 'IEEE 802.1 no par')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/standard/ieee/802.3', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/standard/ieee/802.3', 'IEEE 802.3 with par')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/experimental/ieee/802.3', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/experimental/ieee/802.3', 'IEEE 802.3 no par')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/standard/ieee/draft', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/standard/ieee/draft', 'IEEE draft with par')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/standard/mef/src/model/standard', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/standard/mef/src/model/standard', 'MEF standard')

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/standard/mef/src/model/draft', '--removedup', 'True'],
                                   stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/standard/mef/src/model/draft', 'MEF draft')
        repo.remove()

        # Openconfig is from different repo that s why we need models in github zero
        LOGGER.info('Cloning the repo')
        repo = repoutil.RepoUtil('https://github.com/openconfig/public')
        repo.clone(config_name, config_email)

        process = subprocess.Popen(['python', '../runYANGallstats/runYANGallstats.py', '--rootdir',
                                    repo.localdir + '/release/models', '--removedup', 'True'], stdout=subprocess.PIPE)
        out, err = process.communicate()
        process_data(out, sdo_list, repo.localdir + '/release/models', 'openconfig')
        repo.remove()

        context = {'table_sdo': sdo_list,
                   'table_vendor': vendor_list,
                   'num_yang_files_vendor': vendor_modules,
                   'num_yang_files_vendor_ndp': vendor_modules_ndp,
                   'num_yang_files_standard': standard_modules,
                   'num_yang_files_standard_ndp': standard_modules_ndp,
                   'num_parsed_files': all_modules_data,
                   'num_unique_parsed_files': len(all_modules_data_unique),
                   'nx': nx,
                   'xr': xr,
                   'xe': xe,
                   'nx_values': nx_values,
                   'xe_values': xe_values,
                   'xr_values': xr_values,
                   'current_date': time.strftime("%d/%m/%y")}
        LOGGER.info('Rendering data')
        result = render('./template/stats.html', context)
        with open('./statistics.html', 'w+') as f:
            f.write(result)

        file_from = os.path.abspath('./statistics.html')
        file_to = os.path.abspath(move_to) + '/statistics.html'
        if move_to != './':
            if os.path.exists(file_to):
                os.remove(file_to)
            shutil.move(file_from, file_to)
        time_after = time.clock()
        total_time = time_after - timeBefore
        strin = '{} final time'.format(total_time)
        print(strin)
    except Exception as e:
        repo.remove()
        raise Exception(e)
