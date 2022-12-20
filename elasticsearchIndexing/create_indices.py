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

"""Create an Elasticsearch index"""

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'


import argparse
import glob
import json
import os

from elasticsearchIndexing.es_manager import ESManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--index',
        type=str,
        help='Name of the new index. If not specified, indices are created '
        'from all the initialization files found in elasticsearchIndexing/json.',
    )
    parser.add_argument(
        '--schema',
        type=str,
        help='Path to a json schema file. Only valid if an index name was provided. '
        'Defaults to elasticsearchIndexing/json/initialize_<index>_index.json.',
    )
    args = parser.parse_args()
    es = ESManager().es
    schema_dir = os.path.join(os.environ['BACKEND'], 'elasticsearchIndexing/json')
    if args.index is None:
        for index_schema_base in glob.glob('initialize_*_index.json', root_dir=schema_dir):
            index_name = index_schema_base.removeprefix('initialize_').removesuffix('_index.json')
            if es.indices.exists(index_name):
                print(f'{index_name} index already exists')
                continue
            index_schema = os.path.join(schema_dir, index_schema_base)
            with open(index_schema) as f:
                schema_contents = json.load(f)
            create_result = es.indices.create(index=index_name, body=schema_contents)
            print(create_result)
    else:
        index_name = args.index
        if es.indices.exists(index_name):
            print(f'{index_name} index already exists')
            return
        index_schema = args.schema or os.path.join(schema_dir, f'initialize_{index_name}_index.json')
        with open(index_schema) as f:
            schema_contents = json.load(f)
        create_result = es.indices.create(index=index_name, body=schema_contents, ignore=400)
        print(create_result)


if __name__ == '__main__':
    main()
