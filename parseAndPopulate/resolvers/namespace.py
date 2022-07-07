import logging
import os
import typing as t

from parseAndPopulate.resolvers.resolver import Resolver
from pyang.statements import Statement
from utility import yangParser
from utility.staticVariables import MISSING_ELEMENT
from utility.util import find_first_file

""" 
This resolver resolves yang module namespace property.
Default value: 'missing element'
"""


class NamespaceResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger, name_revision: str,
                 path: str, belongs_to: t.Optional[str]) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.property_name = 'namespace'
        self.name_revision = name_revision
        self.path = path
        self.belongs_to = belongs_to

    def resolve(self) -> str:
        module_type = self.parsed_yang.keyword
        if module_type == 'submodule':
            return self._resolve_submodule_namespace()
        return self._resolve_module_namespace()

    def _resolve_submodule_namespace(self) -> str:
        """ If the model is a submodule, then it is necessary to get a namespace from its parent. """
        if not self.belongs_to:
            self.logger.error('Belongs to not defined - unable to resolve namespace')
            return MISSING_ELEMENT

        self.logger.debug('Getting parent namespace - {} is a submodule'.format(self.name_revision))
        pattern = '{}.yang'.format(self.belongs_to)
        pattern_with_revision = '{}@*.yang'.format(self.belongs_to)
        directory = os.path.dirname(self.path)
        yang_file = find_first_file(directory, pattern, pattern_with_revision)
        if yang_file is None:
            self.logger.error('Parent module not found - unable to resolve namespace')
            return MISSING_ELEMENT

        try:
            parsed_yang_parent = yangParser.parse(os.path.abspath(yang_file))
            return parsed_yang_parent.search(self.property_name)[0].arg
        except IndexError:
            self.logger.error('Cannot parse out {} property'.format(self.property_name))
            return MISSING_ELEMENT

    def _resolve_module_namespace(self) -> str:
        try:
            return self.parsed_yang.search(self.property_name)[0].arg
        except IndexError:
            self.logger.error('Cannot parse out {} property'.format(self.property_name))
            return MISSING_ELEMENT
