import logging
import os
import typing as t

from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.models.submodule import Submodule
from parseAndPopulate.resolvers.resolver import Resolver
from pyang.statements import Statement
from utility import yangParser
from utility.util import find_first_file

"""
This resolver resolves yang module submodule (and partly also dependencies) property.
Default value: [] -> no submodules
"""


class SubmoduleResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger, path: str, schema: t.Optional[str]) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.path = path
        self.schema = schema
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

            pattern = '{}.yang'.format(new_submodule.name)
            if new_submodule.revision:
                pattern_with_revision = '{}@{}.yang'.format(new_submodule.name, new_submodule.revision)
            else:
                pattern_with_revision = '{}@*.yang'.format(new_submodule.name)
            directory = os.path.dirname(self.path)
            yang_file = find_first_file(directory, pattern, pattern_with_revision)
            if not yang_file:
                self.logger.error('Submodule {} can not be found'.format(new_submodule.name))
                continue

            try:
                new_submodule.revision = yangParser.parse(yang_file).search('revision')[0].arg
            except IndexError:
                new_submodule.revision = '1970-01-01'

            if self.schema:
                sub_schema = os.path.join(os.path.dirname(self.schema), os.path.basename(yang_file))
            else:
                sub_schema = None

            new_submodule.schema = new_dependency.schema = sub_schema
            dependencies.append(new_dependency)
            submodules.append(new_submodule)
        return dependencies, submodules
