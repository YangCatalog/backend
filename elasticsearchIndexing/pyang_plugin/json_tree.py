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

"""JSONTree output plugin
Generates a JSON-formatted output of the data node
hierarchy of the YANG module(s).  This is based on the
jstree output plugin.
"""

import json

from pyang import plugin
from pyang import statements
from pyang import util


def pyang_plugin_init():
    plugin.register_plugin(JSONTreePlugin())


class JSONTreePlugin(plugin.PyangPlugin):

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['json-tree'] = self

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        emit_tree(modules, fd, ctx)


def emit_tree(modules, fd, ctx):
    for module in modules:
        mod_out = {}
        bstr = ""
        b = module.search_one('belongs-to')
        if b is not None:
            mod_out['belongs_to'] = b.arg
        ns = module.search_one('namespace')
        if ns is not None:
            mod_out['namespace'] = ns.arg
        pr = module.search_one('prefix')
        if pr is not None:
            mod_out['prefix'] = pr.arg
        else:
            mod_out['prefix'] = ''

        mod_out['name'] = module.arg
        mod_out['type'] = module.keyword

        chs = [ch for ch in module.i_children
               if ch.keyword in statements.data_definition_keywords]
        mod_out['children'] = get_children(chs, module, mod_out['prefix'], ctx)

        mods = [module]
        for i in module.search('include'):
            subm = ctx.get_module(i.arg)
            if subm is not None:
                mods.append(subm)
        maugs = []
        for m in mods:
            for augment in m.search('augment'):
                try:
                    hasattr(augment.i_target_node, 'i_module')
                except:
                    continue
                aug = {}
                aug['augment_children'] = []
                aug['augment_path'] = augment.arg
                if (hasattr(augment.i_target_node, 'i_module') and
                        augment.i_target_node.i_module not in modules + mods):
                    aug['augment_children'].extend(get_children(
                        augment.i_children, module, ' ', ctx))
                maugs.append(aug)

        if len(maugs) > 0:
            mod_out['augments'] = maugs

        rpcs = module.search('rpc')
        if len(rpcs) > 0:
            mod_out['rpcs'] = get_children(rpcs, module, ' ', ctx)

        notifs = module.search('notification')
        if len(notifs) > 0:
            mod_out['notifications'] = get_children(notifs, module, ' ', ctx)

        fd.write(json.dumps(mod_out, indent=4))


def get_children(i_children, module, prefix, ctx):
    children = []
    for ch in i_children:
        children.append(get_node(ch, module, prefix, ctx))
    return children


def get_node(s, module, prefix, ctx):
    child = {}
    child['status'] = get_status_str(s)
    options = ''
    if s.i_module.i_modulename == module.i_modulename:
        name = s.arg
    else:
        name = s.i_module.i_prefix + ':' + s.arg

    child['name'] = name

    pr = module.search_one('prefix')
    if pr is not None:
        child['prefix'] = pr.arg
    else:
        child['prefix'] = ""

    descr = s.search_one('description')
    child['description'] = "No description"
    if descr is not None:
        child['description'] = json_escape(descr.arg)
    child['flags'] = get_flags(s)
    if s.keyword == 'list':
        pass
    elif s.keyword == 'container':
        p = s.search_one('presence')
        if p is not None:
            child['presence'] = p.arg
            options = "Presence"
    elif s.keyword == 'choice':
        m = s.search_one('mandatory')
        if m is None or m.arg == 'false':
            child['name'] = '(' + s.arg + ')'
            options = 'Choice'
        else:
            child['name'] = '(' + s.arg + ')'
    elif s.keyword == 'case':
        child['name'] = ':(' + s.arg + ')'
    elif s.keyword == 'input':
        pass
    elif s.keyword == 'output':
        pass
    elif s.keyword == 'rpc':
        pass
    elif s.keyword == 'notification':
        pass
    else:
        if s.keyword == 'leaf-list':
            options = '*'
        elif s.keyword == 'leaf' and not hasattr(s, 'i_is_key'):
            m = s.search_one('mandatory')
            if m is None or m.arg == 'false':
                options = '?'
        child['type'] = get_typename(s)

    if s.keyword == 'list' and s.search_one('key') is not None:
        child['list_key'] = s.search_one('key').arg

    child['path'] = mk_path_str(s, True)
    child['schema_type'] = s.keyword
    child['options'] = options

    if s.keyword == ('tailf-common', 'action'):
        child['class'] = "action"
        child['type_info'] = action_params(s)
        child['schema_type'] = "action"
    elif s.keyword == 'rpc' or s.keyword == 'notification':
        child['class'] = "folder"
        child['type_info'] = action_params(s)
    else:
        child['class'] = s.keyword
        child['type_info'] = typestring(s)

    if hasattr(s, 'i_children'):
        if s.keyword in ['choice', 'case']:
            child['children'] = get_children(s.i_children, module, prefix, ctx)
        else:
            child['children'] = get_children(s.i_children, module, prefix, ctx)

    return child


def get_status_str(s):
    status = s.search_one('status')
    if status is None or status.arg == 'current':
        return 'current'
    else:
        return status.arg


def get_flags(s):
    flags = {}
    if s.keyword == 'rpc':
        return flags
    elif s.keyword == 'notification':
        return flags
    elif s.i_config == True:
        flags['config'] = True
    else:
        flags['config'] = False
    return flags


def get_typename(s):
    t = s.search_one('type')
    if t is not None:
        return t.arg
    else:
        return ''


def json_escape(s):
    return s.replace("\\", r"\\").replace("\n", r"\n").replace("\t", r"\t").replace("\"", r"\"")


def typestring(node):

    def get_nontypedefstring(node):
        s = {}
        found = False
        t = node.search_one('type')
        if t is not None:
            s['type'] = t.arg
            if t.arg == 'enumeration':
                found = True
                s['enumeration'] = []
                for enums in t.substmts:
                    s['enumeration'].append(enums.arg)
            elif t.arg == 'leafref':
                found = True
                p = t.search_one('path')
                if p is not None:
                    s['path'] = p.arg

            elif t.arg == 'identityref':
                found = True
                b = t.search_one('base')
                if b is not None:
                    s['base'] = b.arg

            elif t.arg == 'union':
                found = True
                uniontypes = t.search('type')
                s['union'] = [uniontypes[0].arg]
                for uniontype in uniontypes[1:]:
                    s['union'].append(uniontype.arg)

            typerange = t.search_one('range')
            if typerange is not None:
                found = True
                s['type_range'] = typerange.arg
            length = t.search_one('length')
            if length is not None:
                found = True
                s['length'] = length.arg

            pattern = t.search_one('pattern')
            if pattern is not None:
                found = True
                s['pattern'] = json_escape(pattern.arg)
        return s

    s = get_nontypedefstring(node)

    if len(s) != 0:
        t = node.search_one('type')
        # chase typedef
        type_namespace = None
        i_type_name = None
        name = t.arg
        if name.find(":") == -1:
            prefix = None
        else:
            [prefix, name] = name.split(':', 1)
        if prefix is None or t.i_module.i_prefix == prefix:
            # check local typedefs
            pmodule = node.i_module
            typedef = statements.search_typedef(t, name)
        else:
            # this is a prefixed name, check the imported modules
            err = []
            pmodule = util.prefix_to_module(
                t.i_module, prefix, t.pos, err)
            if pmodule is None:
                return
            typedef = statements.search_typedef(pmodule, name)
        if typedef != None:
            s['typedef'] = get_nontypedefstring(typedef)
    return s


def action_params(action):
    s = {}
    for params in action.substmts:

        if params.keyword == 'input':
            inputs = params.search('leaf')
            inputs += params.search('leaf-list')
            inputs += params.search('list')
            inputs += params.search('container')
            inputs += params.search('anyxml')
            inputs += params.search('uses')
            s['in'] = []
            for i in inputs:
                s['in'].append(i.arg)

        if params.keyword == 'output':
            outputs = params.search('leaf')
            outputs += params.search('leaf-list')
            outputs += params.search('list')
            outputs += params.search('container')
            outputs += params.search('anyxml')
            outputs += params.search('uses')
            s['out'] = []
            for o in outputs:
                s['out'].append(o.arg)
    return s

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
