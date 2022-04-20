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

__author__ = 'Miroslav Kovac and Joe Clarke'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech, jclarke@cisco.com'

import io
import json
import logging

from elasticsearch import ConnectionError, ConnectionTimeout, RequestError
from elasticsearch.helpers import parallel_bulk
from pyang import plugin
from elasticsearchIndexing.pyang_plugin.json_tree import emit_tree
from elasticsearchIndexing.pyang_plugin.yang_catalog_index_es import IndexerPlugin
from pyang.util import get_latest_revision
from requests import ConnectionError
from utility import yangParser
from utility.util import validate_revision

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices

ES_CHUNK_SIZE = 30


def build_indices(es_manager: ESManager, module: dict, save_file_dir: str, json_ytree: str, threads: int, LOGGER: logging.Logger):
    name_revision = '{}@{}'.format(module['name'], module['revision'])

    plugin.init([])
    ctx = yangParser.create_context(save_file_dir)
    ctx.opts.lint_namespace_prefixes = []
    ctx.opts.lint_modulename_prefixes = []
    for p in plugin.plugins:
        p.setup_ctx(ctx)

    with open(module['path'], 'r') as f:
        parsed_module = ctx.add_module(module['path'], f.read())
    if parsed_module is None:
        raise Exception('Unable to pyang parse module')
    ctx.validate()

    submodules = [parsed_module]
    _find_submodules(ctx, submodules, parsed_module)

    f = io.StringIO()
    ctx.opts.yang_index_make_module_table = True
    ctx.opts.yang_index_no_schema = True
    indexerPlugin = IndexerPlugin()
    indexerPlugin.emit(ctx, [parsed_module], f)

    yindexes = json.loads(f.getvalue())

    with open('{}/{}.json'.format(json_ytree, name_revision), 'w') as f:
        try:
            emit_tree([parsed_module], f, ctx)
        except Exception:
            # create empty file so we still have access to that
            LOGGER.exception('unable to create ytree for module {}'.format(name_revision))
            f.write('')

    attempts = 3
    while attempts > 0:
        try:
            # Remove exisiting modules from all indices
            LOGGER.debug('deleting data from index: modules')
            es_manager.delete_from_indices(module)

            # Remove existing submodules from index: yindex
            for subm in submodules:
                subm_n = subm.arg
                rev = get_latest_revision(subm)
                subm_r = validate_revision(rev)
                submodule = {
                    'name': subm_n,
                    'revision': subm_r
                }
                try:
                    LOGGER.debug('deleting data from index: yindex')
                    es_manager.delete_from_index(ESIndices.YINDEX, submodule)
                except RequestError:
                    LOGGER.exception('Problem while deleting {}@{}'.format(subm_n, subm_r))

            # Bulk new modules to index: yindex
            for key in yindexes:
                chunks = [yindexes[key][i:i + ES_CHUNK_SIZE] for i in range(0, len(yindexes[key]), ES_CHUNK_SIZE)]
                for idx, chunk in enumerate(chunks, start=1):
                    LOGGER.debug('pushing data to index: yindex {} out of {}'.format(idx, len(chunks)))
                    for success, info in parallel_bulk(es_manager.es, chunk, thread_count=threads, index='yindex',
                                                       request_timeout=40):
                        if not success:
                            LOGGER.error('A elasticsearch document failed with info: {}'.format(info))

            # Index new modules to index: modules
            LOGGER.debug('pushing data to index: modules')
            es_manager.index_module(ESIndices.MODULES, module)
            # Index new modules to index: autocomplete
            LOGGER.debug('pushing data to index: autocomplete')
            es_manager.index_module(ESIndices.AUTOCOMPLETE, module)
            break
        except (ConnectionTimeout, ConnectionError) as e:
            attempts -= attempts
            if attempts > 0:
                LOGGER.warning('module {} timed out'.format(name_revision))
            else:
                LOGGER.exception('module {} timed out too many times failing'.format(name_revision))
                raise e


def _find_submodules(ctx, submodules, module):
    for i in module.search('include'):
        r = i.search_one('revision-date')
        if r is None:
            subm = ctx.get_module(i.arg)
        else:
            subm = ctx.search_module(module.pos, i.arg, r.arg)
        if subm is not None and subm not in submodules:
            submodules.append(subm)
            _find_submodules(ctx, submodules, subm)
