import logging
import os
import typing as t

from pyang.statements import Statement

from parseAndPopulate.resolvers.resolver import Resolver
from utility import yangParser
from utility.util import get_yang

"""
This resolver resolves yang module 'prefix' property.
Default value: None
"""
DEFAULT = None


class PrefixResolver(Resolver):
    def __init__(
        self,
        parsed_yang: Statement,
        logger: logging.Logger,
        name_revision: str,
        belongs_to: t.Optional[str],
    ) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.name_revision = name_revision
        self.belongs_to = belongs_to
        self.property_name = 'prefix'

    def resolve(self) -> t.Optional[str]:
        module_type = self.parsed_yang.keyword
        self.logger.debug('Resolving prefix of {}'.format(module_type))
        if module_type == 'submodule':
            return self._resolve_submodule_prefix()
        return self._resolve_module_prefix()

    def _resolve_submodule_prefix(self) -> t.Optional[str]:
        """If the model is a submodule, then it is necessary to get a namespace from its parent."""
        if not self.belongs_to:
            self.logger.error('Belongs to not defined - unable to resolve namespace')
            return DEFAULT

        self.logger.debug('Getting parent namespace - {} is a submodule'.format(self.name_revision))
        yang_file = get_yang(self.belongs_to)
        if yang_file is None:
            self.logger.error('Parent module not found - unable to resolve namespace')
            return DEFAULT

        try:
            parsed_yang_parent = yangParser.parse(os.path.abspath(yang_file))
            return parsed_yang_parent.search(self.property_name)[0].arg
        except IndexError:
            self.logger.error('Cannot parse out {} property'.format(self.property_name))
            return DEFAULT

    def _resolve_module_prefix(self) -> t.Optional[str]:
        try:
            return self.parsed_yang.search(self.property_name)[0].arg
        except IndexError:
            pass
        return None
