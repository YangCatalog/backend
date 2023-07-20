import logging
import typing as t

from pyang.statements import Statement

from parseAndPopulate.resolvers.resolver import Resolver

"""
This resolver resolves yang module 'module_type' property.
Allowed values are: ['module', 'submodule', None]
Default value: 'module'
"""

ALLOWED = ['module', 'submodule', None]
DEFAULT = None


class ModuleTypeResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger

    def resolve(self) -> t.Optional[str]:
        try:
            module_type = self.parsed_yang.keyword
            if module_type in ALLOWED:
                return module_type
        except AttributeError:
            self.logger.exception('Error while resolving module_type')

        return DEFAULT
