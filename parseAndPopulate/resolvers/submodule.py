import logging
import typing as t

from pyang.statements import Statement

from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.models.submodule import Submodule
from parseAndPopulate.resolvers.resolver import Resolver
from utility.util import get_yang, yang_url

"""
This resolver resolves yang module 'submodule' (and partly also dependencies) property.
Default value: [] -> no submodules
"""


class SubmoduleResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger, domain_prefix: str) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.domain_prefix = domain_prefix

    def resolve(self) -> t.Tuple[list, list]:
        self.logger.debug('Resolving submodules')
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

            new_submodule.schema = new_dependency.schema = yang_url(
                new_submodule.name,
                new_submodule.revision,
            )
            dependencies.append(new_dependency)
            submodules.append(new_submodule)
        return dependencies, submodules
