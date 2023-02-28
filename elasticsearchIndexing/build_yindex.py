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
import os.path

from elasticsearch import ConnectionError, ConnectionTimeout, RequestError
from pyang import plugin
from pyang.util import get_latest_revision

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices
from elasticsearchIndexing.models.index_build import BuildYINDEXModule
from elasticsearchIndexing.pyang_plugin.json_tree import emit_tree
from elasticsearchIndexing.pyang_plugin.yang_catalog_index_es import IndexerPlugin
from utility import yangParser
from utility.util import validate_revision

ES_CHUNK_SIZE = 100


def build_indices(
    es_manager: ESManager,
    module: BuildYINDEXModule,
    save_file_dir: str,
    json_ytree: str,
    logger: logging.Logger,
):
    name_revision = f'{module["name"]}@{module["revision"]}'

    plugin.init([])
    ctx = yangParser.create_context(save_file_dir)
    ctx.opts.lint_namespace_prefixes = []
    ctx.opts.lint_modulename_prefixes = []
    for plug in plugin.plugins:
        plug.setup_ctx(ctx)

    with open(module['path'], 'r') as reader:
        parsed_module = ctx.add_module(module['path'], reader.read())
    if parsed_module is None:
        raise Exception('Unable to pyang parse module')
    ctx.validate()

    submodules = [parsed_module]
    _find_submodules(ctx, submodules, parsed_module)

    f = io.StringIO()
    ctx.opts.yang_index_make_module_table = True
    ctx.opts.yang_index_no_schema = True
    indexer_plugin = IndexerPlugin()
    indexer_plugin.emit(ctx, [parsed_module], f)

    yindexes = json.loads(f.getvalue())

    with open(os.path.join(json_ytree, name_revision), 'w') as writer:
        try:
            emit_tree([parsed_module], writer, ctx)
        except Exception:
            # create empty file so we still have access to that
            logger.exception(f'Unable to create ytree for module {name_revision}')
            writer.write('')

    attempts = 3
    while attempts > 0:
        try:
            # Remove exisiting modules from all indices
            logger.debug('deleting data from index: modules')
            es_manager.delete_from_indices(module)

            # Remove existing submodules from index: yindex
            for subm in submodules:
                subm_n = subm.arg
                rev = get_latest_revision(subm)
                subm_r = validate_revision(rev)
                submodule = {'name': subm_n, 'revision': subm_r}
                try:
                    logger.debug('deleting data from index: yindex')
                    es_manager.delete_from_index(ESIndices.YINDEX, submodule)
                except RequestError:
                    logger.exception(f'Problem while deleting {subm_n}@{subm_r}')

            # Bulk new modules to index: yindex
            for key in yindexes:
                chunks = [yindexes[key][i : i + ES_CHUNK_SIZE] for i in range(0, len(yindexes[key]), ES_CHUNK_SIZE)]
                for idx, chunk in enumerate(chunks, start=1):
                    logger.debug(f'Pushing data to index: yindex {idx} out of {len(chunks)}')
                    es_manager.bulk_modules(ESIndices.YINDEX, chunk)

            # Index new modules to index: autocomplete
            logger.debug('pushing data to index: autocomplete')
            del module['path']
            es_manager.index_module(ESIndices.AUTOCOMPLETE, module)
            break
        except (ConnectionTimeout, ConnectionError) as e:
            attempts -= 1
            if attempts > 0:
                logger.warning(f'Module {name_revision} timed out')
            else:
                logger.exception(f'Module {name_revision} timed out, failed too many times')
                raise e


def _find_submodules(ctx, submodules, module):
    for i in module.search('include'):
        revision = i.search_one('revision-date')
        if revision is None:
            subm = ctx.get_module(i.arg)
        else:
            subm = ctx.search_module(module.pos, i.arg, revision.arg)
        if subm is not None and subm not in submodules:
            submodules.append(subm)
            _find_submodules(ctx, submodules, subm)
