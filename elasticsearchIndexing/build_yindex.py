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

__author__ = "Miroslav Kovac and Joe Clarke"
__copyright__ = "Copyright The IETF Trust 2021, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech, jclarke@cisco.com"

import io
import json
import logging
import subprocess
import traceback
from datetime import datetime

import dateutil.parser
from elasticsearch import ConnectionError, ConnectionTimeout, Elasticsearch, NotFoundError
from elasticsearch.helpers import parallel_bulk
from pyang import plugin
from pyang.plugins.json_tree import emit_tree
from pyang.plugins.name import emit_name
from pyang.plugins.yang_catalog_index_es import IndexerPlugin, resolve_organization
from pyang.util import get_latest_revision

from utility.util import get_curr_dir
from utility.yangParser import create_context


def __run_pyang_commands(commands, output_only=True, decode=True):
    pyang_args = ['pyang']
    pyang_args.extend(commands)
    pyang = subprocess.Popen(pyang_args,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    stdout, stderr = pyang.communicate()
    if decode:
        stdout = stdout.decode(encoding='utf-8', errors='strict')
        stderr = stderr.decode(encoding='utf-8', errors='strict')
    if output_only:
        return stdout
    else:
        return stdout, stderr


def build_yindex(ytree_dir, modules, LOGGER, save_file_dir, es_host, es_port, es_aws, elk_credentials,
                 threads, log_file, failed_changes_dir, temp_dir, processes):
    if es_aws:
        es = Elasticsearch([es_host], http_auth=(elk_credentials[0], elk_credentials[1]), scheme="https", port=443)
    else:
        es = Elasticsearch([{'host': '{}'.format(es_host), 'port': es_port}])
    initialize_body_yindex = json.load(open('{}/../api/json/es/initialize_yindex_elasticsearch.json'.format(get_curr_dir(
        __file__)), 'r'))
    initialize_body_modules = json.load(open('{}/../api/json/es/initialize_module_elasticsearch.json'.format(get_curr_dir(
        __file__)), 'r'))

    es.indices.create(index='yindex', body=initialize_body_yindex, ignore=400)
    es.indices.create(index='modules', body=initialize_body_modules, ignore=400)

    logging.getLogger('elasticsearch').setLevel(logging.ERROR)
    x = 0
    modules_copy = modules.copy()
    for module in modules:
        try:
            modules_copy.remove(module)
            x += 1
            LOGGER.info('yindex on module {}. module {} out of {}'.format(module.split('/')[-1], x, len(modules)))
            # split to module with path and organization
            m_parts = module.split(":")
            m = m_parts[0]
            plugin.init([])
            ctx = create_context('{}'.format(save_file_dir))
            ctx.opts.lint_namespace_prefixes = []
            ctx.opts.lint_modulename_prefixes = []
            for p in plugin.plugins:
                p.setup_ctx(ctx)
            with open(m, 'r') as f:
                parsed_module = ctx.add_module(m, f.read())
            ctx.validate()

            if parsed_module is None:
                raise Exception('Unable to pyang parse module')
            f = io.StringIO()
            ctx.opts.print_revision = True
            emit_name(ctx, [parsed_module], f)
            name_revision = f.getvalue().strip()

            mods = [parsed_module]

            find_submodules(ctx, mods, parsed_module)

            f = io.StringIO()
            ctx.opts.yang_index_make_module_table = True
            ctx.opts.yang_index_no_schema = True
            indexerPlugin = IndexerPlugin()
            indexerPlugin.emit(ctx, [parsed_module], f)

            yindexes = json.loads(f.getvalue())
            name_revision = name_revision.split('@')
            if len(name_revision) > 1:
                name = name_revision[0]
                revision = name_revision[1].split(' ')[0]
            else:
                name = name_revision[0]
                revision = '1970-01-01'
            if 'belongs-to' in name:
                name = name.split(' ')[0]
            try:
                dateutil.parser.parse(revision)
            except Exception as e:
                if revision[-2:] == '29' and revision[-5:-3] == '02':
                    revision = revision.replace('02-29', '02-28')
                else:
                    revision = '1970-01-01'
            rev_parts = revision.split('-')
            try:
                revision = datetime(int(rev_parts[0]), int(rev_parts[1]), int(rev_parts[2])).date().isoformat()
            except Exception:
                revision = '1970-01-01'

            retry = 3
            while retry > 0:
                try:
                    for m in mods:
                        n = m.arg
                        rev = get_latest_revision(m)
                        if rev == 'unknown':
                            r = '1970-01-01'
                        else:
                            r = rev

                        try:
                            dateutil.parser.parse(r)
                        except Exception as e:
                            if r[-2:] == '29' and r[-5:-3] == '02':
                                r = r.replace('02-29', '02-28')
                            else:
                                r = '1970-01-01'
                        rev_parts = r.split('-')
                        r = datetime(int(rev_parts[0]), int(rev_parts[1]), int(rev_parts[2])).date().isoformat()
                        try:
                            query = \
                                {
                                    "query": {
                                        "bool": {
                                            "must": [{
                                                "match_phrase": {
                                                    "module.keyword": {
                                                        "query": n
                                                    }
                                                }
                                            }, {
                                                "match_phrase": {
                                                    "revision": {
                                                        "query": r
                                                    }
                                                }
                                            }]
                                        }
                                    }
                                }
                            LOGGER.debug('deleting data from yindex')
                            es.delete_by_query(index='yindex', body=query, doc_type='modules', conflicts='proceed',
                                               request_timeout=40)
                        except NotFoundError as e:
                            pass
                    for key in yindexes:
                        j = -1
                        for j in range(0, int(len(yindexes[key]) / 30)):
                            LOGGER.debug('pushing new data to yindex {} of {}'.format(j, int(len(yindexes[key]) / 30)))
                            for success, info in parallel_bulk(es, yindexes[key][j * 30: (j * 30) + 30],
                                                               thread_count=int(threads), index='yindex',
                                                               doc_type='modules', request_timeout=40):
                                if not success:
                                    LOGGER.error('A elasticsearch document failed with info: {}'.format(info))
                        LOGGER.debug('pushing rest of data to yindex')
                        for success, info in parallel_bulk(es, yindexes[key][(j * 30) + 30:],
                                                           thread_count=int(threads), index='yindex',
                                                           doc_type='modules', request_timeout=40):
                            if not success:
                                LOGGER.error('A elasticsearch document failed with info: {}'.format(info))

                    rev = get_latest_revision(parsed_module)
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
                    query = \
                        {
                            "query": {
                                "bool": {
                                    "must": [{
                                        "match_phrase": {
                                            "module.keyword": {
                                                "query": name
                                            }
                                        }
                                    }, {
                                        "match_phrase": {
                                            "revision": {
                                                "query": revision
                                            }
                                        }
                                    }]
                                }
                            }
                        }
                    LOGGER.debug('deleting data from modules index')
                    total = es.delete_by_query(index='modules', body=query, doc_type='modules', conflicts='proceed',
                                               request_timeout=40)['deleted']
                    if total > 1:
                        LOGGER.info('{}@{}'.format(name, revision))

                    query = {}
                    query['module'] = name
                    query['organization'] = resolve_organization(parsed_module)
                    query['revision'] = revision
                    query['dir'] = parsed_module.pos.ref
                    LOGGER.debug('pushing data to modules index')
                    es.index(index='modules', doc_type='modules', body=query, request_timeout=40)
                    break
                except (ConnectionTimeout, ConnectionError) as e:
                    retry = retry - 1
                    if retry > 0:
                        LOGGER.warning('module {}@{} timed out'.format(name, revision))
                    else:
                        LOGGER.error('module {}@{} timed out too many times failing'.format(name, revision))
                        raise e

            with open('{}/{}@{}.json'.format(ytree_dir, name, revision), 'w') as f:
                try:
                    emit_tree([parsed_module], f, ctx)
                except Exception as e:
                    # create empty file so we still have access to that
                    LOGGER.warning('unable to create ytree for module {}@{} creating empty file')
                    f.write("")
            with open('{}/rest-of-elk-data.json'.format(temp_dir), 'w') as f:
                json.dump(modules_copy, f)

        except Exception as e:
            with open(log_file, 'a') as f:
                traceback.print_exc(file=f)
            m_parts = module.split(":")
            key = '{}/{}'.format(m_parts[0].split('/')[-1][:-5], m_parts[1])
            val = m_parts[0]
            with open(failed_changes_dir, 'r') as f:
                failed_mods = json.load(f)
            if key not in failed_mods:
                failed_mods[key] = val
            with open(failed_changes_dir, 'w') as f:
                json.dump(failed_mods, f)


def find_submodules(ctx, mods, module):
    for i in module.search('include'):
        r = i.search_one('revision-date')
        if r is None:
            subm = ctx.get_module(i.arg)
        else:
            subm = ctx.search_module(module.pos, i.arg, r.arg)
        if subm is not None and subm not in mods:
            mods.append(subm)
            find_submodules(ctx, mods, subm)
