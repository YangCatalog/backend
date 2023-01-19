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

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'

import argparse
import typing as t
from copy import deepcopy


class Help(t.TypedDict):
    help: str
    options: t.Dict[str, str]


class BaseArg(t.TypedDict):
    flag: str
    help: str
    default: t.Any


class Arg(BaseArg, total=False):
    type: type
    action: t.Literal['store_true', 'store_false']
    nargs: int
    choices: t.List[str]


class ScriptConfig:
    """
    A class for setting configuration options
    for scripts which can be run from the admin UI.
    """

    def __init__(
        self,
        help: str,
        args: t.Optional[list[Arg]],
        arglist: t.Optional[list[str]],
        mutually_exclusive_args: t.Optional[list[list[Arg]]] = None,
    ):
        self.copy_info = {
            'help': deepcopy(help),
            'args': deepcopy(args),
            'arglist': deepcopy(arglist),
            'mutually_exclusive_args': deepcopy(mutually_exclusive_args),
        }

        # We need to make copies of data, so that we don't affect the original info,
        # that we used for ScriptConfig initialization.
        help = deepcopy(help)
        args = deepcopy(args)
        arglist = deepcopy(arglist)
        mutually_exclusive_args = deepcopy(mutually_exclusive_args)

        self.parser = argparse.ArgumentParser(description=help)
        self.help: Help = {'help': help, 'options': {}}
        self.args_dict = {}
        self.mutually_exclusive_arg_flags = set()
        if mutually_exclusive_args:
            self._add_mutually_exclusive_args(mutually_exclusive_args)
        if args:
            self._add_args(args)
        self.args = self.parser.parse_args(arglist)
        self.defaults = [self.parser.get_default(key) for key in self.args.__dict__.keys()]

    def _add_mutually_exclusive_args(self, mutually_exclusive_args: list[list[Arg]]):
        for mutually_exclusive_args_list in mutually_exclusive_args:
            group = self.parser.add_mutually_exclusive_group()
            for arg in mutually_exclusive_args_list:
                flag = arg.pop('flag')
                argument = group.add_argument(flag, **arg)
                self.mutually_exclusive_arg_flags.add(flag)
                self._add_argument_to_args_dict(argument.dest, arg)
            group_arg_names = tuple(map(lambda arg: arg.dest, group._group_actions))
            for arg_name in group_arg_names:
                self._update_argument_in_args_dict(
                    arg_name,
                    mutually_exclusive_with=[
                        another_arg_name for another_arg_name in group_arg_names if another_arg_name != arg_name
                    ],
                )

    def _add_args(self, args: list[Arg]):
        for arg in args:
            flag = arg.pop('flag')
            if flag in self.mutually_exclusive_arg_flags:
                continue
            argument = self.parser.add_argument(flag, **arg)
            self._add_argument_to_args_dict(argument.dest, arg)

    def _add_argument_to_args_dict(self, arg_name: str, arg: Arg):
        # some args with the 'store_true' action do not specify a type
        # NOTE: maybe we should just specify it everywhere?
        self.args_dict[arg_name] = {'type': type(arg['default']).__name__, 'default': arg['default']}
        if 'help' in arg:
            self.help['options'][arg_name] = arg['help']

    def _update_argument_in_args_dict(self, arg_name: str, **kwargs):
        self.args_dict[arg_name].update(**kwargs)

    def get_args_list(self) -> t.Dict:
        return self.args_dict

    def get_help(self) -> Help:
        return self.help

    def copy(self):
        return ScriptConfig(**self.copy_info)
