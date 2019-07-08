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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import sqlite3
import json
import re

DBF = '/var/yang/yang.db'


def __sqlite_regexp(pattern, buf, modifiers=re.I | re.S):
    if pattern is not None and buf is not None:
        exp = re.compile(pattern, modifiers)
        return exp.search(buf) is not None

    return False

__schema_types = [
    'typedef',
    'grouping',
    'feature',
    'identity',
    'extension',
    'rpc',
    'container',
    'list',
    'leaf-list',
    'leaf',
    'notification',
    'action'
]

__search_fields = [
    'argument',
    'description',
    'module'
]

__node_data = {
    'name': 'argument',
    'description': 'description',
    'path': 'path',
    'type': 'statement'
}


def do_search(options):
    opts = json.loads(options)
    try:
        conn = sqlite3.connect(DBF)
        conn.row_factory = sqlite3.Row
        conn.create_function('REGEXP', 2, __sqlite_regexp)
        if 'case-sensitive' in opts and opts['case-sensitive']:
            conn.execute('PRAGMA case_sensitive_like=ON')
        else:
            conn.execute('PRAGMA case_sensitive_like=OFF')

        cur = conn.cursor()

        sql = 'SELECT yi.*, MAX(mo.revision) AS latest_revision FROM yindex yi, modules mo WHERE '
        qparams = {'descr': '%' + opts['search'] + '%'}
        sts = __search_fields
        if 'search-fields' in opts:
            sts = opts['search-fields']

        wclause = []
        if 'type' in opts and opts['type'] == 'regex':
            for field in sts:
                if field in __search_fields:
                    wclause.append('REGEXP(:descr, yi.{})'.format(field))
        else:
            for field in sts:
                if field in __search_fields:
                    wclause.append('yi.{} LIKE :descr'.format(field))

        sql += '({})'.format(' OR '.join(wclause))
        if 'schema-types' in opts:
            queries = []
            sql += ' AND ('
            for st in opts['schema-types']:
                if st in __schema_types:
                    queries.append("yi.statement = '{}'".format(st))
            sql += ' OR '.join(queries)
            sql += ')'

        sql += ' AND (mo.module = yi.module) GROUP BY yi.argument, yi.module, yi.revision'
        cur.execute(sql, qparams)

        results = []
        filter_list = __node_data.keys()
        if 'filter' in opts and 'node' in opts['filter']:
            filter_list = opts['filter']['node']

        for row in cur:
            module = {'latest_revision': row['latest_revision'], 'name': row[
                'module'], 'revision': row['revision'], 'organization': row['organization']}
            result = {'module': module}
            result['node'] = {}
            for nf in filter_list:
                if nf in __node_data:
                    result['node'][nf] = row[__node_data[nf]]

            results.append(result)

        return results
    except sqlite3.Error as e:
        raise Exception("Error searching for {}: {}".format(
            opts['search'], e.args[0]))
