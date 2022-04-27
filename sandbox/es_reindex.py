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

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

"""
This script contains functionality,
which re-index Elasticsearch indices
after ES update from version 6.8 to
version 7.10 (done in April 2022).
"""

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices


def main():
    # ----------------------------------------------------------------------------------------------
    # INIT ALL INDICES
    # ----------------------------------------------------------------------------------------------
    es_manager = ESManager()
    for index in ESIndices:
        if index == ESIndices.TEST:
            continue
        if not es_manager.index_exists(index):
            create_result = es_manager.create_index(index)
            print(create_result)
    # ----------------------------------------------------------------------------------------------
    # GET ALL MODULES FROM 'modules' INDEX
    # ----------------------------------------------------------------------------------------------
    all_es_modules = es_manager.match_all(ESIndices.MODULES)
    print('Total number of modules retreived from "modules" index: {}'.format(len(all_es_modules)))
    # ----------------------------------------------------------------------------------------------
    # FILL 'autocomplete' INDEX
    # ----------------------------------------------------------------------------------------------
    for query in all_es_modules.values():
        es_manager.delete_from_index(ESIndices.AUTOCOMPLETE, query)
        index_result = es_manager.index_module(ESIndices.AUTOCOMPLETE, query)
        if index_result['result'] != 'created':
            print(index_result)


if __name__ == '__main__':
    main()
