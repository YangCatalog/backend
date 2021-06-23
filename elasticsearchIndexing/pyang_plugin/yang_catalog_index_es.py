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

from pyang import plugin, statements
from datetime import datetime

import json
import optparse
import re
import dateutil.parser
import hashlib
from pyang.util import get_latest_revision

_yang_catalog_index_fd = None
_yang_catalog_index_values = []
_values = {'yindex': []}
_ctx = None

NS_MAP = {
    "http://cisco.com/": "cisco",
    "http://www.huawei.com/netconf": "huawei",
    "http://openconfig.net/yang": "openconfig",
    "http://tail-f.com/": "tail-f",
    "http://yang.juniper.net/": "juniper"
}

def pyang_plugin_init():
    plugin.register_plugin(IndexerPlugin())


class IndexerPlugin(plugin.PyangPlugin):

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['yang-catalog-index_es'] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--yang-index-no-schema-es",
                                 dest="yang_index_no_schema_es",
                                 action="store_true",
                                 help="""Do not include SQL schema in output"""),
            optparse.make_option("--yang-index-schema-only-es",
                                 dest="yang_index_schema_only_es",
                                 action="store_true",
                                 help="""Only include the SQL schema in output"""),
            optparse.make_option("--yang-index-make-module-table-es",
                                 dest="yang_index_make_module_table_es",
                                 action="store_true",
                                 help="""Generate a modules table that includes various aspects about the modules themselves""")
        ]

        g = optparser.add_option_group("YANG Catalog Index specific options")
        g.add_options(optlist)

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        global _values
        global _belongs_to
        _values = {'yindex': []}
        emit_index(ctx, modules, fd)


def emit_index(ctx, modules, fd):
    global  _yang_catalog_index_values
    global  _values
    global  _ctx

    _ctx = ctx
    if not ctx.opts.yang_index_schema_only_es:
        _yang_catalog_index_values = []
        mods = []
        for module in modules:
            if module in mods:
                continue
            mods.append(module)
        for module in mods:
            non_chs = list(module.i_typedefs.values()) + list(module.i_features.values()) + list(module.i_identities.values()) + \
                list(module.i_groupings.values()) + list(module.i_extensions.values())
            for augment in module.search('augment'):
                if (hasattr(augment, 'i_target_node') and
                        hasattr(augment.i_target_node, 'i_module') and
                        augment.i_target_node.i_module not in mods):
                    for child in augment.i_children:
                        statements.iterate_i_children(child, index_printer)
            for nch in non_chs:
                index_printer(nch)
            for child in module.i_children:
                statements.iterate_i_children(child, index_printer)
        fd.write(json.dumps(_values))


def index_escape_json(s):
    return s.replace("\\", r"\\").replace("'", r"''").replace("\n", r"\n").replace("\t", r"\t").replace("\"", r"\"")


def flatten_keyword(k):
    if type(k) is tuple:
        k = ':'.join(map(str, k))

    return k


def index_get_other(stmt):
    a = stmt.arg
    k = flatten_keyword(stmt.keyword)
    if a:
        a = index_escape_json(a)
    else:
        a = ''
    child = {k: {'value': a, 'has_children': False}}
    child[k]['children'] = []
    for ss in stmt.substmts:
        child[k]['has_children'] = True
        child[k]['children'].append(index_get_other(ss))
    return child


def index_printer(stmt):
    global _yang_catalog_index_values
    global _values
    global  _ctx

    if stmt.arg is None:
        return

    skey = flatten_keyword(stmt.keyword)

    module = stmt.i_module
    rev = get_latest_revision(module)
    revision = ''

    path = mk_path_str(stmt, True)
    descr = stmt.search_one('description')
    dstr = ''
    if descr:
        dstr = descr.arg
        dstr = dstr.replace("'", "''")
    subs = []
    if rev == 'unknown':
        revision = '1970-01-01'
    else:
        revision = rev
    try:
        dateutil.parser.parse(revision)
    except Exception as e:
        if revision[-2:] == '29' and revision[-5:-3] == '02':
            revision = revision.replace('02-29', '02-28')
        else:
            revision = '1970-01-01'
    rev_parts = revision.split('-')
    revision = datetime(int(rev_parts[0]), int(rev_parts[1]), int(rev_parts[2])).date().isoformat()
    for i in stmt.substmts:
        a = i.arg
        k = i.keyword

        k = flatten_keyword(k)

        if i.keyword not in statements.data_definition_keywords:
            subs.append(index_get_other(i))
        else:
            has_children = hasattr(i, 'i_children') and len(i.i_children) > 0
            if not a:
                a = ''
            else:
                a = index_escape_json(a)
            subs.append(
                {k: {'value': a, 'has_children': has_children, 'children': []}})
    vals = {}
    vals['module'] = module.arg
    vals['revision'] = revision
    vals['organization'] = resolve_organization(module)
    vals['path'] = path
    vals['statement'] = skey
    vals['argument'] = stmt.arg
    vals['description'] = dstr
    vals['properties'] = json.dumps(subs)

    text = '{} {} {} {} {} {} {} {}'.format(vals['module'], vals['revision'], vals['organization'],
                                            vals['path'], vals['statement'], vals['argument'],
                                            vals['description'], vals['properties'])
    vals['sort-hash-id'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
    _values['yindex'].append(vals)

def mk_path_str(s, with_prefixes=False):
    """Returns the XPath path of the node"""
    def name(s):
        if with_prefixes:
            if len(s.keyword) == 2:
                return s.keyword[0] + ":" + s.arg + "?" + s.keyword[1]
            return s.i_module.i_prefix + ":" + s.arg + "?" + s.keyword
        else:
            return s.arg
    if s.parent.keyword in ['module', 'submodule']:
        return "/" + name(s)
    elif s.keyword in ['choice', 'case']:
        return mk_path_str(s.parent, with_prefixes)
    else:
        p = mk_path_str(s.parent, with_prefixes)
        return p + "/" + name(s)

def resolve_organization(module):
    if module.keyword == 'submodule':
        belongs_to_module = module.i_ctx.read_module(module.search_one('belongs-to').arg)
        mod = belongs_to_module
    else:
        mod = module

    try:
        temp_organization = mod.search('organization')[0].arg.lower()
        if 'cisco' in temp_organization:
            return 'cisco'
        elif 'ietf' in temp_organization:
            return 'ietf'
    except:
        pass
    namespace = mod.search_one('namespace')
    if namespace is None:
        return 'independent'
    namespace = namespace.arg.lower()
    for ns, org in NS_MAP.items():
        if ns in namespace:
            return org
    if 'cisco' in namespace:
        return 'cisco'
    elif 'ietf' in namespace:
        return 'ietf'
    elif 'urn:' in namespace:
        return namespace.split('urn:')[1].split(':')[0]
    return 'independent'
