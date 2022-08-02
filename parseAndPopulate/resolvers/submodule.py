import logging
import os
import typing as t

from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.models.submodule import Submodule
from parseAndPopulate.resolvers.resolver import Resolver
from pyang.statements import Statement
from utility import yangParser
from utility.util import get_yang

"""
This resolver resolves yang module submodule (and partly also dependencies) property.
Default value: [] -> no submodules
"""


class SubmoduleResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger,
                 path: str, schema: t.Optional[str], schemas: dict) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.path = path
        self.schema = schema
        self.schemas = schemas
        self.property_name = 'submodule'

    def resolve(self) -> t.Tuple[list, list]:
        submodules = []
        dependencies = []
        parsed_submodules = self.parsed_yang.search('include')

        for parsed_submodule in parsed_submodules:
            new_dependency = Dependency()
            new_submodule = Submodule()
            new_submodule.name = new_dependency.name = parsed_submodule.arg

            try:
                parsed_revision = parsed_submodule.search('revision-date')[0].arg
            except IndexError:
                parsed_revision = None
            new_submodule.revision = new_dependency.revision = parsed_revision

            yang_file = get_yang(new_submodule.name, new_submodule.revision)
            if not yang_file:
                self.logger.error('Submodule {} can not be found'.format(new_submodule.name))
                continue

            new_submodule.revision = yang_file.split('@')[-1].removesuffix('.yang')
            name_revision = '{}@{}'.format(new_submodule.name, new_submodule.revision)
            local_yang_file = os.path.join(os.path.dirname(self.path), '{}.yang'.format(new_dependency.name))
            if name_revision in self.schemas:
                sub_schema = self.schemas[name_revision]
            elif os.path.exists(local_yang_file) and self.schema:
                sub_schema = os.path.join(os.path.dirname(self.schema), os.path.basename(local_yang_file))
            else:
                sub_schema = None

            new_submodule.schema = new_dependency.schema = sub_schema
            dependencies.append(new_dependency)
            submodules.append(new_submodule)
        return dependencies, submodules
