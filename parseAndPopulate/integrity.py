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


import glob
import json
import os
import typing as t
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import date

from pyang.statements import Statement

from utility import yangParser
from utility.script_config_dict import script_config_dict
from utility.scriptConfig import ScriptConfig
from utility.staticVariables import NAMESPACE_MAP
from utility.util import find_files

BASENAME = os.path.basename(__file__)
FILENAME = BASENAME.split('.py')[0]
DEFAULT_SCRIPT_CONFIG = ScriptConfig(
    help=script_config_dict[FILENAME]['help'],
    args=script_config_dict[FILENAME]['args'],
    arglist=None if __name__ == '__main__' else [],
)
missing_revisions: t.Set[str] = set()
missing_namespaces: t.Set[str] = set()
missing_modules: t.Dict[str, t.Set[str]] = defaultdict(set)
missing_submodules: t.Dict[str, t.Set[str]] = defaultdict(set)
unused_modules: t.Dict[str, t.Set[str]] = defaultdict(set)


def check_revision(parsed_module: Statement) -> bool:
    try:
        revision = parsed_module.search('revision')[0].arg
    except (IndexError, AttributeError):
        return False
    revision_parts = [int(i) for i in revision.split('-')]
    try:
        date(*revision_parts)
    except ValueError:
        return False
    return True


def check_namespace(parsed_module: Statement) -> bool:
    try:
        namespace = parsed_module.search('namespace')[0].arg
    except (IndexError, AttributeError):
        return False
    if 'urn:cisco' in namespace:
        return False
    if 'urn:' in namespace:
        return True
    for ns, _ in NAMESPACE_MAP:
        if ns in namespace:
            return True
    return False


modules_to_check = deque()  # used for a breadth first search throught the dependency graph of vendor directories


def check_dependencies(
    dep_type: t.Literal['import', 'include'],
    parsed_module: Statement,
    directory: str,
) -> t.Tuple[t.Set[str], t.Set[str]]:
    all_modules: t.Set[str] = set()
    missing_modules: t.Set[str] = set()
    for dependency in parsed_module.search(dep_type):
        name = dependency.arg
        all_modules.add(name)
        revisions = dependency.search('revision-date')
        revision = revisions[0].arg if revisions else None
        pattern = os.path.join(directory, '{}.yang'.format(name))
        if not glob.glob(pattern):
            # TODO: if the matched filename doesn't include the revision, maybe we should check it?
            if revision is not None:
                missing_modules.add('{}@{}'.format(name, revision))
            else:
                missing_modules.add(name)
    return all_modules, missing_modules


def check(path: str, directory: str, sdo: bool):
    try:
        parsed_module = yangParser.parse(path)
    except (yangParser.ParseException, FileNotFoundError):
        return
    if not check_revision(parsed_module):
        missing_revisions.add(path)
    if not check_namespace(parsed_module):
        missing_namespaces.add(path)
    all_imports, broken_imports = check_dependencies('import', parsed_module, directory)
    if broken_imports:
        missing_modules[path] |= broken_imports
    all_includes, broken_includes = check_dependencies('include', parsed_module, directory)
    if broken_includes:
        missing_submodules[path] |= broken_includes
    if not sdo:
        all_dependencies = all_imports | all_includes
        for module in all_dependencies:
            if module in unused_modules[directory]:
                unused_modules[directory].remove(module)
                modules_to_check.append(module)


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


def main(script_conf: ScriptConfig = DEFAULT_SCRIPT_CONFIG.copy()):
    args = script_conf.args
    args.dir = args.dir.rstrip('/')
    if args.sdo:  # sdo directory
        for root, _, files in os.walk(args.dir):
            for filename in files:
                if filename.endswith('.yang'):
                    check(os.path.join(root, filename), root, sdo=True)
    else:  # vendor directory
        for root, capabilities in find_files(args.dir, '*capabilit*.xml'):
            files_in_dir = os.listdir(root)
            modules_to_check.clear()
            if root not in unused_modules:
                unused_modules[root] = {file.removesuffix('.yang') for file in files_in_dir if file.endswith('.yang')}
            modules = capabilities_to_modules(capabilities)
            for module in modules:
                filename = '{}.yang'.format(module)
                if filename not in files_in_dir:
                    missing_modules[os.path.join(root, capabilities)].add(module)
                elif module in unused_modules[root]:
                    modules_to_check.append(module)
                    unused_modules[root].remove(module)
            while modules_to_check:
                filename = '{}.yang'.format(modules_to_check.popleft())
                check(os.path.join(root, filename), root, sdo=False)

    report = {
        'missing-revisions': sorted(list(missing_revisions)),  # noqa
        'missing-namespaces': sorted(list(missing_namespaces)),  # noqa
        'missing-modules': {key: sorted(list(value)) for key, value in missing_modules.items()},  # noqa
        'missing-submodules': {key: sorted(list(value)) for key, value in missing_submodules.items()},  # noqa
        'unused-modules': {key: sorted(list(value)) for key, value in unused_modules.items()},  # noqa
    }
    with open(args.output, 'w') as f:
        json.dump(report, f)


if __name__ == '__main__':
    main()
