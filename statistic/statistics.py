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
This script will find all the sdos and vendors and creates a
html file with statistics for specific organizations.

The statistics include the number of modules on github,
number of modules in the catalog, percentage that passes
compilation, and for Cisco we have information about
what platforms are supported for specific versions
of specific OS-types.

The html file also contains general statistics like
the number of vendor yang files, the number of unique yang files,
the number of yang files in yang-catalog...
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'


import fnmatch
import io
import json
import os
import shutil
import time
import typing as t
from contextlib import redirect_stdout

import jinja2

import utility.log as log
from parseAndPopulate.resolvers.basic import BasicResolver
from parseAndPopulate.resolvers.namespace import NamespaceResolver
from parseAndPopulate.resolvers.organization import OrganizationResolver
from parseAndPopulate.resolvers.revision import RevisionResolver
from statistic import runYANGallstats as all_stats
from utility import repoutil, yangParser
from utility.create_config import create_config
from utility.fetch_modules import fetch_modules
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.staticVariables import MISSING_ELEMENT, NAMESPACE_MAP, github_url
from utility.util import job_log

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME]['args'],
    arglist=None if __name__ == '__main__' else [],
)


def render(tpl_path: str, context: dict) -> str:
    """Render jinja html template

    Arguments:
        :param tpl_path:    (str) path to a file
        :param context:     (dict) dictionary containing data to render jinja
            template file
        :return:            (str) string containing rendered html file
    """

    path, filename = os.path.split(tpl_path)
    return jinja2.Environment(loader=jinja2.FileSystemLoader(path or './')).get_template(filename).render(context)


def list_yang_modules_recursive(srcdir: str) -> t.List[str]:
    """
    Returns the list of paths of YANG Modules (.yang) in all sub-directories

    Arguments
        :param srcdir:  (str) root directory to search for yang files
        :return:        (list)list of YANG files
    """
    ll = []
    for root, _, files in os.walk(srcdir):
        for file in files:
            if file.endswith('.yang'):
                ll.append(os.path.join(root, file))
    return ll


def get_total_and_passed(directory: str) -> t.Tuple[int, int]:
    """Get the number of yang files in a specified directory and the
    number that passed compilation.

    Argument:
        :param directory: (str) path to the directory where to search for yang files
        :return: tuple containing the number of yang files and the number that passed compilation respectively
    """
    passed = 0
    num_in_catalog = 0
    yang_modules = list_yang_modules_recursive(directory)
    num_of_modules = len(yang_modules)
    checked = {}
    for i, module_path in enumerate(yang_modules, start=1):
        filename = os.path.basename(module_path)
        LOGGER.debug(f'{i} out of {num_of_modules}: {filename}')
        if filename in checked.keys():
            passed += checked[filename]['passed']
            num_in_catalog += checked[filename]['in-catalog']
            continue
        checked[filename] = {'passed': False, 'in-catalog': False}
        revision = None
        try:
            parsed_yang = yangParser.parse(os.path.abspath(module_path))
        except (yangParser.ParseException, FileNotFoundError):
            continue
        name = filename.split('.')[0].split('@')[0]
        revision = RevisionResolver(parsed_yang, LOGGER).resolve()
        belongs_to = BasicResolver(parsed_yang, 'belongs_to').resolve()
        namespace = NamespaceResolver(parsed_yang, LOGGER, f'{name}@{revision}', belongs_to).resolve()
        organization = OrganizationResolver(parsed_yang, LOGGER, namespace).resolve()
        mod = f'{name}@{revision}_{organization}'
        data = all_modules_data_unique.get(mod)
        if data is not None:
            if 'passed' == data.get('compilation-status'):
                passed += 1
                checked[filename]['passed'] = True
            checked[filename]['in-catalog'] = True
            num_in_catalog += 1
        else:
            LOGGER.error(f'module {mod} does not exist')
    return num_in_catalog, passed


def match_organization(namespace: str, found: t.Optional[str]) -> str:
    for ns, org in NAMESPACE_MAP:
        if ns in namespace:
            return org
    if found is None:
        if 'cisco' in namespace:
            return 'cisco'
        elif 'ietf' in namespace:
            return 'ietf'
        elif 'urn:' in namespace:
            return namespace.split('urn:')[1].split(':')[0]
        else:
            return MISSING_ELEMENT
    else:
        return found


class InfoTable(t.TypedDict):
    name: str
    num_github: int
    num_catalog: int
    percentage_compile: str
    percentage_extra: str


def process_data(out: str, save_list: t.List[InfoTable], path: str, name: str):
    """Process all the data out of output from runYANGallstats and Yang files themself

    Arguments:
        :param out:         (bytes) output from runYANGallstats
        :param save_list:   (list) list to which we are saving all the informations
        :param path:        (str) path to a directory to which we are creating statistics
        :param name:        (str) name of the vendor or organization that we are creating
            statistics for
    """
    LOGGER.info(f'Getting info from {name}')
    if name == 'openconfig':
        modules = 0
    else:
        modules = int(out.split(f'{path} : ')[1].splitlines()[0])
    num_in_catalog, passed = get_total_and_passed(path)
    extra = '0.0 %' if modules == 0 else f'{repr(round((num_in_catalog / modules) * 100, 2))} %'
    compiled = '0.0 %' if num_in_catalog == 0 else f'{repr(round((passed / num_in_catalog) * 100, 2))} %'
    info_table: InfoTable = {
        'name': name,
        'num_github': modules,
        'num_catalog': num_in_catalog,
        'percentage_compile': compiled,
        'percentage_extra': extra,
    }
    save_list.append(info_table)


def solve_platforms(path: str) -> set:
    """
    Resolve all the platforms on specified path and fills the platform
    set variable with the found data

    Arguments:
        :param path         (str) path to a specific Cisco platform
    """
    platforms = set()
    matches = []
    for root, _, filenames in os.walk(path):
        for filename in fnmatch.filter(filenames, 'platform-metadata.json'):
            matches.append(os.path.join(root, filename))
    for match in matches:
        with open(match, encoding='utf-8') as f:
            try:
                js_objs = json.load(f)['platforms']['platform']
                for js_obj in js_objs:
                    platforms.add(js_obj['name'])
            except json.decoder.JSONDecodeError as e:
                LOGGER.error(f'File {match} has an invalid JSON layout, skipping it ({e})')
    return platforms


@job_log(file_basename=BASENAME)
def main(script_conf: t.Optional[ScriptConfig] = None):
    start_time = int(time.time())
    if script_conf is None:
        script_conf = DEFAULT_SCRIPT_CONFIG.copy()
    args = script_conf.args

    config_path = args.config_path
    config = create_config(config_path)
    config_name = config.get('General-Section', 'repo-config-name')
    config_email = config.get('General-Section', 'repo-config-email')
    move_to = f'{config.get("Web-Section", "public-directory")}/.'
    yang_models = config.get('Directory-Section', 'yang-models-dir')
    log_directory = config.get('Directory-Section', 'logs')
    private_dir = config.get('Web-Section', 'private-directory')
    global yangcatalog_api_prefix
    yangcatalog_api_prefix = config.get('Web-Section', 'yangcatalog-api-prefix')

    global LOGGER
    LOGGER = log.get_logger('statistics', f'{log_directory}/statistics/yang.log')
    LOGGER.info('Starting statistics')

    repo = None

    # Fetch the list of all modules known by YangCatalog
    LOGGER.info('Fetching all of the modules from API')
    all_modules_data = fetch_modules(LOGGER, config=config)
    global all_modules_data_unique
    all_modules_data_unique = {}
    vendor_data = {}
    for module in all_modules_data:
        name = module['name']
        revision = module['revision']
        org = module['organization']
        all_modules_data_unique[f'{name}@{revision}_{org}'] = module
        for implementation in module.get('implementations', {}).get('implementation', []):
            if implementation['vendor'] != 'cisco':
                continue
            if implementation['os-type'] not in vendor_data:
                vendor_data[implementation['os-type']] = {}
            version = implementation['software-version']
            if implementation['os-type'] in ('IOS-XE', 'IOS-XR'):
                version = version.replace('.', '')
            elif implementation['os-type'] == 'NX-OS':
                version = version.replace('(', '-').replace(')', '-').rstrip('-')
            if version not in vendor_data[implementation['os-type']]:
                vendor_data[implementation['os-type']][version] = set()
            vendor_data[implementation['os-type']][version].add(implementation['platform'])

    try:
        # pull(yang_models) no need to pull https://github.com/YangModels/yang
        # as it is daily done via module-compilation module

        # function needs to be renamed to something more descriptive (I don't quite understand it's purpose)
        def process_platforms(
            versions: t.List[str],
            module_platforms,
            os_type: str,
            os_type_name: str,
        ) -> t.Tuple[list, dict]:
            platform_values = []
            json_output = {}
            for version in versions:
                path = f'{yang_models}/vendor/cisco/{os_type}/{version}/platform-metadata.json'
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        metadata_platforms = data['platforms']['platform']
                except FileNotFoundError:
                    metadata_platforms = []
                except OSError:
                    LOGGER.exception(f'Problem with opening {path}')
                    metadata_platforms = []
                values = [version]
                json_output[version] = {}
                for module_platform in module_platforms:
                    exist = '<i class="fa fa-times"></i>'
                    exist_json = False
                    if os_type_name in vendor_data:
                        if version in vendor_data[os_type_name]:
                            if module_platform in vendor_data[os_type_name][version]:
                                exist = '<i class="fa fa-check"></i>'
                                exist_json = True
                    for metadata_platform in metadata_platforms:
                        if (
                            metadata_platform['name'] == module_platform
                            and metadata_platform['software-version'] == version
                        ):
                            values.append(f'<i class="fa fa-check"></i>/{exist}')
                            json_output[version][module_platform] = {'yangcatalog': True, 'github': exist_json}
                            break
                    else:
                        values.append(f'<i class="fa fa-times"></i>/{exist}')
                        json_output[version][module_platform] = {'yangcatalog': False, 'github': exist_json}
                platform_values.append(values)
            return platform_values, json_output

        os_types = (('xr', 'IOS-XR'), ('xe', 'IOS-XE'), ('nx', 'NX-OS'))

        platforms = {os_type: solve_platforms(f'{yang_models}/vendor/cisco/{os_type}') for os_type, _ in os_types}

        versions = {}
        for os_type, _ in os_types:
            os_type_dir = os.path.join(yang_models, 'vendor/cisco', os_type)
            dirs = (dir for dir in os.listdir(os_type_dir) if os.path.isdir(os.path.join(os_type_dir, dir)))
            versions[os_type] = sorted(dirs)

        values = {}
        json_output = {}
        for os_type, name in os_types:
            values[os_type], json_output[os_type] = process_platforms(
                versions[os_type],
                platforms[os_type],
                os_type,
                name,
            )

        # Vendors separately
        vendor_list = []

        def get_output(**kwargs) -> str:
            """run runYANGallstats with the provided kwargs as command line arguments.
            removedup is set to True by default.
            """
            kwargs.setdefault('removedup', True)
            script_conf = all_stats.DEFAULT_SCRIPT_CONFIG.copy()
            for key, value in kwargs.items():
                setattr(script_conf.args, key, value)
            with redirect_stdout(io.StringIO()) as f:
                all_stats.main(script_conf=script_conf)
            return f.getvalue()

        for direc in next(os.walk(os.path.join(yang_models, 'vendor')))[1]:
            vendor_direc = os.path.join(yang_models, 'vendor', direc)
            if os.path.isdir(vendor_direc):
                LOGGER.info(f'Running runYANGallstats.py for directory {vendor_direc}')
                out = get_output(rootdir=vendor_direc)
                process_data(out, vendor_list, vendor_direc, direc)

        # Vendors all together
        out = get_output(rootdir=os.path.join(yang_models, 'vendor'))
        vendor_modules = out.split(f'{yang_models}/vendor : ')[1].splitlines()[0]
        vendor_modules_ndp = out.split(f'{yang_models}/vendor (duplicates removed): ')[1].splitlines()[0]

        # Standard all together
        out = get_output(rootdir=os.path.join(yang_models, 'standard'))
        standard_modules = out.split(f'{yang_models}/standard : ')[1].splitlines()[0]
        standard_modules_ndp = out.split(f'{yang_models}/standard (duplicates removed): ')[1].splitlines()[0]

        # Standard separately
        sdo_list = []

        def process_sdo_dir(directory: str, name: str):
            out = get_output(rootdir=os.path.join(yang_models, directory))
            process_data(out, sdo_list, os.path.join(yang_models, directory), name)

        process_sdo_dir('standard/ietf/RFC', 'IETF RFCs')
        process_sdo_dir('standard/ietf/DRAFT', 'IETF drafts')
        process_sdo_dir('experimental/ietf-extracted-YANG-modules', 'IETF experimental drafts')
        process_sdo_dir('standard/iana', 'IANA standard')
        process_sdo_dir('standard/bbf/standard', 'BBF standard')
        process_sdo_dir('standard/etsi', 'ETSI standard')

        process_sdo_dir('standard/ieee/published', 'IEEE published')
        process_sdo_dir('standard/ieee/draft', 'IEEE draft')
        process_sdo_dir('experimental/ieee', 'IEEE experimental')

        process_sdo_dir('standard/mef/src/model/standard', 'MEF standard')
        process_sdo_dir('standard/mef/src/model/draft', 'MEF draft')

        # Openconfig is from different repository so we need yang models in Github equal to zero
        LOGGER.info('Cloning the repo')
        repo = repoutil.ModifiableRepoUtil(
            os.path.join(github_url, 'openconfig/public'),
            clone_options={'config_username': config_name, 'config_user_email': config_email},
        )

        out = get_output(rootdir=os.path.join(repo.local_dir, 'release/models'))
        process_data(out, sdo_list, os.path.join(repo.local_dir, 'release/models'), 'openconfig')

        context = {
            'table_sdo': sdo_list,
            'table_vendor': vendor_list,
            'num_yang_files_vendor': vendor_modules,
            'num_yang_files_vendor_ndp': vendor_modules_ndp,
            'num_yang_files_standard': standard_modules,
            'num_yang_files_standard_ndp': standard_modules_ndp,
            'num_parsed_files': len(all_modules_data),
            'num_unique_parsed_files': len(all_modules_data_unique),
            'xr': platforms['xr'],
            'xe': platforms['xe'],
            'nx': platforms['nx'],
            'xr_values': values['xr'],
            'xe_values': values['xe'],
            'nx_values': values['nx'],
            'current_date': time.strftime('%d/%m/%y'),
        }
        LOGGER.info('Rendering data')
        with open(f'{private_dir}/stats/stats.json', 'w') as f:
            for sdo in sdo_list:
                sdo['percentage_compile'] = float(sdo['percentage_compile'].split(' ')[0])
                sdo['percentage_extra'] = float(sdo['percentage_extra'].split(' ')[0])
            for vendor in vendor_list:
                vendor['percentage_compile'] = float(vendor['percentage_compile'].split(' ')[0])
                vendor['percentage_extra'] = float(vendor['percentage_extra'].split(' ')[0])
            output = {
                'table_sdo': sdo_list,
                'table_vendor': vendor_list,
                'num_yang_files_vendor': int(vendor_modules),
                'num_yang_files_vendor_ndp': int(vendor_modules_ndp),
                'num_yang_files_standard': int(standard_modules),
                'num_yang_files_standard_ndp': int(standard_modules_ndp),
                'num_parsed_files': len(all_modules_data),
                'num_unique_parsed_files': len(all_modules_data_unique),
                'xr': json_output['xr'],
                'xe': json_output['xe'],
                'nx': json_output['nx'],
                'current_date': time.strftime('%d/%m/%y'),
            }
            json.dump(output, f)
        result = render(os.path.join(os.environ['BACKEND'], 'statistic/template/stats.html'), context)
        with open(os.path.join(os.environ['BACKEND'], 'statistic/statistics.html'), 'w+') as f:
            f.write(result)

        file_from = os.path.abspath(os.path.join(os.environ['BACKEND'], 'statistic/statistics.html'))
        file_to = os.path.join(os.path.abspath(move_to), 'statistics.html')
        resolved_path_file_to = os.path.realpath(file_to)
        if move_to != './':
            if os.path.exists(resolved_path_file_to):
                os.remove(resolved_path_file_to)
            shutil.move(file_from, resolved_path_file_to)
        end_time = int(time.time())
        total_time = end_time - start_time
        LOGGER.info(f'Final time in seconds to produce statistics {total_time}')
    except Exception as e:
        LOGGER.exception('Exception found while running statistics script')
        raise e
    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
