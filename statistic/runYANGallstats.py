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
This script counts all yang modules on provided path
with or without duplicates.
"""

__author__ = 'Benoit Claise'
__copyright__ = 'Copyright(c) 2018, Cisco Systems, Inc., Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bclaise@cisco.com'

import os

from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME]['args'],
    arglist=None if __name__ == '__main__' else [],
)


def list_of_yang_modules_in_subdir(srcdir: str, debug_level: int) -> list:
    """
    Returns the list of YANG Modules (.yang) in all sub-directories

    Arguments:
        :param srcdir:      (str) root directory to search for yang files
        :param debug_level: (int) If > 0 print some debug statements to the console
        :return:            (list) list of YANG files
    """
    ll = []
    for root, _, files in os.walk(srcdir):
        for f in files:
            if f.endswith('.yang'):
                if debug_level > 0:
                    print(os.path.join(root, f))
                ll.append(os.path.join(root, f))
    return ll


def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()):
    args = script_conf.args

    # equivalent shell commands (without the de-duplication function)
    # rootdir:
    # find /home/bclaise/yanggithub/ -name "*.yang" -print | wc -l
    # excludedir
    # find /home/bclaise/yanggithub/ -name "*.yang" -print | grep -v "vendor/cisco" | wc -l
    # excludekeyword
    # find /home/bclaise/yanggithub/ -name "*.yang" -print | grep -v "vendor/cisco" | grep -i show | wc -l
    # find /home/bclaise/yanggithub/ -name "*.yang" -print | grep -v "vendor/cisco" | grep -iv show | wc -l

    # runYANGallstats.py --rootdir /home/bclaise/yanggithub/ --excludekeyword "show" --removedup=True
    # --------------------------
    # Number of YANG data models in /home/bclaise/yanggithub/ : 6699
    # Number of YANG data models in /home/bclaise/yanggithub/ (duplicates removed): 1914
    # Number of YANG data models in /home/bclaise/yanggithub/ (without the keyword show):1785
    #
    # runYANGallstats.py --rootdir /home/bclaise/yanggithub/ --excludekeyword "show" --excludedir "vendor"
    # --------------------------
    # Number of YANG data models in /home/bclaise/yanggithub/ : 673
    # Number of YANG data models in /home/bclaise/yanggithub/ (without the keyword show):673

    yang_list = list_of_yang_modules_in_subdir(args.rootdir, args.debug)

    if args.debug > 0:
        print('yang_list content: ')
        print(yang_list)

    # Remove the entries corresponding to exludedir option
    temp_list = []
    if args.excludedir:
        for yang_file in yang_list:
            if args.excludedir not in yang_file:
                temp_list.append(yang_file)
        yang_list = temp_list

    print('--------------------------')
    print(f'Number of YANG data models in {args.rootdir} : {len(yang_list)}')

    # Remove duplicates and count the YANG modules
    if args.removedup:
        yang_module_count_removed_dup = 0
        yang_list_removed_dup = []
        for yang_file in yang_list:
            yang_file_without_path = os.path.basename(yang_file)
            if args.debug > 0:
                print(f'yang_list_removed_dup content: {yang_file_without_path}')
            if yang_file_without_path not in yang_list_removed_dup:
                yang_list_removed_dup.append(yang_file_without_path)
                yang_module_count_removed_dup += 1
        print(f'Number of YANG data models in {args.rootdir} (duplicates removed): {yang_module_count_removed_dup}')
        if args.debug > 0:
            print('yang_list_removed_dup content: ')
            print(yang_list_removed_dup)
        yang_list = yang_list_removed_dup

    # Remove the excludekeyword
    yang_module_count_removed_dup_removed_keyword = 0
    yang_list_removed_dup_removed_keyword = []
    if args.excludekeyword:
        for yang_file_without_path in yang_list:
            if args.excludekeyword not in yang_file_without_path:
                yang_list_removed_dup_removed_keyword.append(yang_file_without_path)
                yang_module_count_removed_dup_removed_keyword += 1
        print(
            f'Number of YANG data models in {args.rootdir} (without the keyword {args.excludekeyword}):'
            f'{yang_module_count_removed_dup_removed_keyword}',
        )


if __name__ == '__main__':
    main()
