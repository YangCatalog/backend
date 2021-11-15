# Copyright The IETF Trust 2021, All Rights Reserved
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
This script is run by a cronjob and it
finds all the modules that have expiration
metadata and updates them based on a date to
expired if it is necessary
"""

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'

import argparse
import typing as t


class Help(t.TypedDict):
    help: str
    options: t.Dict[str, str]

class BaseArg(t.TypedDict):
    flag: str
    help: str
    default: t.Any

class Arg(BaseArg, total=False):
    type: type
    action: str

class BaseScriptConfig:

    def __init__(self, help, args: t.List[Arg], arglist: t.List[str]):
        parser = argparse.ArgumentParser()
        self.help: Help = {'help': help, 'options': {}}
        self.args_dict = {}
        for arg in args:
            flag = arg.pop('flag')
            parser.add_argument(flag, **arg)
            arg_name = flag.lstrip('-').replace('-', '_')
            # some args with the 'store_true' action do not specify a type
            # NOTE: maybe we should just specify it everywhere?
            self.arg_dict[arg_name] = {'type': type(arg['default']).__name__, 'default': arg['default']}
            if 'help' in arg:
                self.help['options'][arg_name] = arg['help']
        self.args = parser.parse_args(arglist)
        self.defaults = [parser.get_default(key) for key in self.args.__dict__.keys()]


    def get_args_list(self) -> t.Dict:
        return self.args_dict

    def get_help(self) -> Help:
        return self.help
