# Copyright The IETF Trust 2022, All Rights Reserved
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
This script checks the integrity of yang files.
Runs on a directory containing either sdo or vendor files.
Child directories are also checked recursively.
Issues detected by this script:
- unspecified revisions in yang files
- unspecified/invalid namespaces in yang files
- missing dependencies of files
Additionally, in the case of vendor files:
- modules mentioned in capability files not present in the directory
- modules in the directory not mentioned by capability files
"""

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'


import json
import os
import typing as t
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import date

from pyang.statements import Statement

from utility import yangParser # Hopefully temporary. Think I can speed this up with regex.
from utility.create_config import create_config
from utility.scriptConfig import Arg, BaseScriptConfig
from utility.staticVariables import NS_MAP
from utility.util import find_files, find_first_file


class ScriptConfig(BaseScriptConfig):

    def __init__(self):
        config = create_config()
        help = ''
        args: t.List[Arg] = [
            {
                'flag': '--sdo',
                'help': 'If we are processing sdo or vendor yang modules',
                'action': 'store_true',
                'default': False
            },
            {
                'flag': '--dir',
                'help': 'Set directory where to look for hello message xml files',
                'type': str,
                'default': '/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC'
            },
            {
                'flag': '--output',
                'help': 'Output json file',
                'type': str,
                'default': 'integrity.json'
            }
        ]
        self.yang_models = config.get('Directory-Section', 'yang-models-dir')
        super().__init__(help, args, None if __name__ == '__main__' else [])


missing_revisions: t.Set[str] = set()
missing_namespaces: t.Set[str] = set()
missing_modules: t.Dict[str, t.Set[str]] = defaultdict(set)
missing_submodules: t.Dict[str, t.Set[str]] = defaultdict(set)
unused_modules: t.Dict[str, t.Set[str]] = defaultdict(set)


def check_revision(parsed_module: Statement) -> bool:
    try:
        revision = parsed_module.search('revision')[0].arg
    except:
        return False
    revision_parts = [int(i) for i in revision.split('-')]
    try:
        date(*revision_parts)
    except:
        if revision_parts[1:] == [2, 29]:
            revision_parts[2] = 28
            try:
                date(*revision_parts)
            except:
                return False
        else:
            return False
    return True


def check_namespace(parsed_module: Statement) -> bool:
    try:
        namespace = parsed_module.search('namespace')[0].arg
    except:
        return False
    if 'urn:cisco' in namespace:
        return False
    if 'urn:' in namespace:
        return True
    for ns, _ in NS_MAP:
        if ns in namespace:
                return True
    return False


modules_to_check = deque() # used for a breadth first search throught the dependency graph of vendor directories


def check_dependencies(dep_type: str, parsed_module: Statement, directory: str, yang_models_dir: str) -> t.Set[str]:
    missing_modules: t.Set[str] = set()
    for dependency in parsed_module.search(dep_type):
        name = dependency.arg
        revisions = dependency.search('revision-date')
        revision = revisions[0].arg if revisions else '*'
        filename = '{}.yang'.format(name)
        if directory in unused_modules: # this runs if we're checking a vendor directory
            if filename in unused_modules[directory]:
                unused_modules[directory].remove(filename)
                modules_to_check.append(filename)
        pattern_with_revision = '{}@{}.yang'.format(name, revision)
        if not find_first_file(directory, filename, pattern_with_revision, yang_models_dir):
            missing_modules.add(pattern_with_revision)
    return missing_modules


def check(path: str, directory: str, yang_models_dir: str):
    parsed_module = yangParser.parse(path)
    if parsed_module is None:
        return
    if not check_revision(parsed_module):
        missing_revisions.add(path)
    if not check_namespace(parsed_module):
        missing_namespaces.add(path)
    broken_imports = check_dependencies('import', parsed_module, directory, yang_models_dir)
    if broken_imports:
        missing_modules[path] |= broken_imports
    broken_includes = check_dependencies('include', parsed_module, directory, yang_models_dir)
    if broken_includes:
        missing_submodules[path] |= broken_includes


def capabilities_to_modules(capabilities: str) -> t.List[str]:
    modules: t.List[str] = []
    deviation_modules: t.Set[str] = set()
    root = ET.parse(capabilities).getroot()
    namespace = root.tag.split('hello')[0]
    for capability in root.iter('{}capability'.format(namespace)):
        capability.text = capability.text or ''
        if 'module=' in capability.text:
            modules.append(capability.text.split('module=')[1].split('&')[0])
        if 'deviations=' in capability.text:
            deviation_modules.update(capability.text.split('deviations=')[1].split('&')[0].split(','))
    modules += list(deviation_modules)
    return modules


def main(scriptConf: t.Optional[ScriptConfig] = None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    if args.sdo: # sdo directory
        for root, _, files in os.walk(args.dir):
            for filename in files:
                if filename.endswith('.yang'):
                    check(os.path.join(root, filename), root, scriptConf.yang_models)
    else: # vendor directory
        for root, capabilities in find_files(args.dir, '*capabilit*.xml'):
            files_in_dir = os.listdir(root)
            modules_to_check.clear()
            if root not in unused_modules:
                unused_modules[root] = {file for file in files_in_dir if file.endswith('.yang')}
            modules = capabilities_to_modules(capabilities)
            for module in modules:
                filename = '{}.yang'.format(module)
                if filename in files_in_dir:
                    modules_to_check.append(filename)
                    unused_modules[root].remove(filename)
                else:
                    missing_modules[os.path.join(root, capabilities)].add(filename)
            while modules_to_check:
                filename = modules_to_check.popleft()
                check(os.path.join(root, filename), root, scriptConf.yang_models)

    report = {
        'missing-revisions': sorted(list(missing_revisions)),
        'missing-namespaces': sorted(list(missing_namespaces)),
        'missing-modules': {key: sorted(list(value)) for key, value in missing_modules.items()},
        'missing-submodules': {key: sorted(list(value)) for key, value in missing_submodules.items()},
        'unused-modules': {key: sorted(list(value)) for key, value in unused_modules.items()}
    }
    with open(args.output, 'w') as f:
        json.dump(report, f)


if __name__ == '__main__':
    main()