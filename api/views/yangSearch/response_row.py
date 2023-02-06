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

import hashlib
import typing as t
from collections import OrderedDict

from utility.staticVariables import OUTPUT_COLUMNS, SDOS


class ResponseRow:
    def __init__(self, source: dict) -> None:
        self.name = source['argument']
        self.revision = source['revision']
        self.schema_type = source['statement']
        self.path = source['path']
        self.module_name = source['module']
        self.origin = self._set_origin(source['organization'])
        self.organization = source['organization']
        self.description = source['description']
        self.maturity = 'ratified' if source.get('rfc') else ''
        self.dependents = 0
        self.compilation_status = 'unknown'

        self.row_representation = OrderedDict()
        self.output_row = {}

    def get_row_hash_by_columns(self) -> str:
        """Return hash which is created from individual row properties."""
        row_hash = hashlib.sha256()

        for value in self.output_row.values():
            row_hash.update(str(value).encode('utf-8'))

        return row_hash.hexdigest()

    def create_representation(self) -> None:
        """Create dictionary representation of row."""
        for column in OUTPUT_COLUMNS:
            underscore_column = column.replace('-', '_')
            value = self.__dict__.get(underscore_column)
            self.row_representation[column] = value

    def create_output(self, to_remove_columns: t.List['str']) -> None:
        """Create dictionary representation of row which does not contain columns
        which are passed as 'to_remove_columns' argument.

        Argument:
            :param to_remove_columns    (list) Columns which should be filtered out of final output
        """
        self.output_row = {}
        for column in OUTPUT_COLUMNS:
            if column in to_remove_columns:
                continue
            underscore_column = column.replace('-', '_')
            value = self.__dict__.get(underscore_column)
            self.output_row[column] = value

    def _set_origin(self, organization: str) -> str:
        """Set 'origin' based on the 'organization' property."""
        if organization in SDOS:
            return 'Industry Standard'
        if organization == 'N/A':
            return organization
        return 'Vendor-Specific'
