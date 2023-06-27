import logging
import os
import typing as t

from pyang.statements import Statement

from parseAndPopulate.resolvers.resolver import Resolver
from utility import yangParser
from utility.staticVariables import MISSING_ELEMENT
from utility.util import get_yang

"""
This resolver resolves yang module 'namespace' property.
Default value: 'missing element'
"""


class NamespaceResolver(Resolver):
    def __init__(
        self,
        parsed_yang: Statement,
        logger: logging.Logger,
        name_revision: str,
        belongs_to: t.Optional[str],
    ) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.property_name = 'namespace'
        self.name_revision = name_revision
        self.belongs_to = belongs_to

    def resolve(self) -> str:
        module_type = self.parsed_yang.keyword
        if module_type == 'submodule':
            return self._resolve_submodule_namespace()
        return self._resolve_module_namespace()

    def _resolve_submodule_namespace(self) -> str:
        """If the model is a submodule, then it is necessary to get a namespace from its parent."""
        if not self.belongs_to:
            self.logger.error(f'Belongs to not defined - unable to resolve namespace - {self.name_revision}')
            return MISSING_ELEMENT

        yang_file = get_yang(self.belongs_to)
        if yang_file is None:
            self.logger.error(f'Parent module not found - unable to resolve namespace - {self.name_revision}')
            return MISSING_ELEMENT

        try:
            parsed_yang_parent = yangParser.parse(os.path.abspath(yang_file))
            return parsed_yang_parent.search(self.property_name)[0].arg
        except IndexError:
            self.logger.error(f'Cannot parse out {self.property_name} property - {self.name_revision}')
            return MISSING_ELEMENT

    def _resolve_module_namespace(self) -> str:
        try:
            return self.parsed_yang.search(self.property_name)[0].arg
        except IndexError:
            self.logger.error(f'Cannot parse out {self.property_name} property -  - {self.name_revision}')
            return MISSING_ELEMENT
