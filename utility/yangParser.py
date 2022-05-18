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

"""Utility belt for working with ``pyang`` and ``pyangext``."""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import json
import typing as t
from os.path import isfile

from pyang.context import Context
from pyang.error import error_codes
from pyang.repository import FileRepository
from pyang.statements import Statement
from pyang.yang_parser import YangParser

from utility.create_config import create_config

DEFAULT_OPTIONS = {
    'path': [],
    'deviations': [],
    'features': [],
    'format': 'yang',
    'keep_comments': True,
    'no_path_recurse': False,
    'trim_yin': False,
    'yang_canonical': False,
    'yang_remove_unused_imports': False,
    # -- errors
    'ignore_error_tags': [],
    'ignore_errors': [],
    'list_errors': True,
    'print_error_code': False,
    'errors': [],
    'warnings': [code for code, desc in error_codes.items() if desc[0] > 4],
    'verbose': True,
}
"""Default options for pyang command line"""

_COPY_OPTIONS = [
    'canonical',
    'max_line_len',
    'max_identifier_len',
    'trim_yin',
    'lax_xpath_checks',
    'strict',
]
"""copy options to pyang context options"""


class objectify(object):  # pylint: disable=invalid-name
    """Utility for providing object access syntax (.attr) to dicts"""

    features: list
    deviations: list

    def __init__(self, *args, **kwargs):
        for arg in args:
            self.__dict__.update(arg)
        self.__dict__.update(kwargs)

    def __getattr__(self, _):
        return None

    def __setattr__(self, attr, value):
        self.__dict__[attr] = value


class OptsContext(Context):
    opts: objectify


def _parse_features_string(feature_str: str) -> t.Tuple[str, t.List[str]]:
    if feature_str.find(':') == -1:
        return (feature_str, [])

    [module_name, rest] = feature_str.split(':', 1)
    if rest == '':
        return (module_name, [])

    features = rest.split(',')
    return (module_name, features)


def create_context(path: str = '.') -> OptsContext:
    """Generates a pyang context.

    The dict options and keyword arguments are similar to the command
    line options for ``pyang``. For ``plugindir`` use env var
    ``PYANG_PLUGINPATH``. For ``path`` option use the argument with the
    same name, or ``PYANG_MODPATH`` env var.

    Arguments:
        path (str): location of YANG modules.
            (Join string with ``os.pathsep`` for multiple locations).
            Default is the current working dir.

    Keyword Arguments:
        print_error_code (bool): On errors, print the error code instead
            of the error message. Default ``False``.
        warnings (list): If contains ``error``, treat all warnings
            as errors, except any other error code in the list.
            If contains ``none``, do not report any warning.
        errors (list): Treat each error code container as an error.
        ignore_error_tags (list): Ignore error code.
            (For a list of error codes see ``pyang --list-errors``).
        ignore_errors (bool): Ignore all errors. Default ``False``.
        canonical (bool): Validate the module(s) according to the
            canonical YANG order. Default ``False``.
        yang_canonical (bool): Print YANG statements according to the
            canonical order. Default ``False``.
        yang_remove_unused_imports (bool): Remove unused import statements
            when printing YANG. Default ``False``.
        trim_yin (bool): In YIN input modules, trim whitespace
            in textual arguments. Default ``False``.
        lax_xpath_checks (bool): Lax check of XPath expressions.
            Default ``False``.
        strict (bool): Force strict YANG compliance. Default ``False``.
        max_line_len (int): Maximum line length allowed. Disabled by default.
        max_identifier_len (int): Maximum identifier length allowed.
            Disabled by default.
        features (list): Features to support, default all.
            Format ``<modname>:[<feature>,]*``.
        keep_comments (bool): Do not discard comments. Default ``True``.
        no_path_recurse (bool): Do not recurse into directories
            in the yang path. Default ``False``.

    Returns:
        pyang.Context: Context object for ``pyang`` usage
    """
    # deviations (list): Deviation module (NOT CURRENTLY WORKING).

    opts = objectify(DEFAULT_OPTIONS)
    repo = FileRepository(path, no_path_recurse=opts.no_path_recurse)

    ctx = OptsContext(repo)
    ctx.opts = opts

    for attr in _COPY_OPTIONS:
        setattr(ctx, attr, getattr(opts, attr))

    # make a map of features to support, per module (taken from pyang bin)
    for feature_name in opts.features:
        (module_name, features) = _parse_features_string(feature_name)
        ctx.features[module_name] = features

    # apply deviations (taken from pyang bin)
    for file_name in opts.deviations:
        with open(file_name) as fd:
            module = ctx.add_module(file_name, fd.read())
            if module is not None:
                ctx.deviation_modules.append(module)

    return ctx


class ParseException(Exception):

    def __init__(self, path: t.Optional[str]):
        if path is not None:
            config = create_config()
            var_path = config.get('Directory-Section', 'var')
            self.msg = 'Failed to parse module on path {}'.format(path)
            try:
                with open('{}/unparsable-modules.json'.format(var_path), 'r') as f:
                    modules = json.load(f)
            except (FileNotFoundError, json.decoder.JSONDecodeError):
                modules = []
            module = path.split('/')[-1]
            if module not in modules:
                modules.append(module)
            with open('{}/unparsable-modules.json'.format(var_path), 'w') as f:
                json.dump(modules, f)


def parse(text: str) -> Statement:
    """Parse a YANG statement into an Abstract Syntax subtree.

    Arguments:
        text (str): file name for a YANG module or text

    Returns:
        pyang.statements.Statement: Abstract syntax subtree

    Note:
        The ``parse`` function can be used to parse small amounts of text.
        If yout plan to parse an entire YANG (sub)module, please use instead::

            ast = ctx.add_module(module_name, text_contet)

        It is also well known that ``parse`` function cannot solve
        YANG deviations yet.
    Note II:
        pyang.Context removed as optional parameter as it was not used anymore.
    """
    parser = YangParser()  # Similar names, but, this one is from PYANG library

    filename = 'parser-input'

    ctx_ = create_context()

    if isfile(text):
        filename = text
        with open(filename) as f:
            text = f.read()

    # ensure reported errors are just from parsing
    # old_errors = ctx_.errors
    ctx_.errors = []

    ast = parser.parse(ctx_, filename, text)
    if ast is None:
        raise ParseException(filename if filename != 'parser-input' else None)

    ctx_.internal_reset()

    return ast
