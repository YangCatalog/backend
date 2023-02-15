import logging

from pyang.statements import Statement

from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.resolvers.resolver import Resolver
from utility.util import get_yang

"""
This resolver resolves yang module dependencies property,
which are defined as 'import' in yang models.
Default value: [] -> no imports
"""


class ImportsResolver(Resolver):
    def __init__(
        self,
        parsed_yang: Statement,
        logger: logging.Logger,
        domain_prefix: str,
    ) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.domain_prefix = domain_prefix

    def resolve(self):
        imports = []
        parsed_imports = self.parsed_yang.search('import')
        for parsed_import in parsed_imports:
            new_dependency = Dependency()
            new_dependency.name = parsed_import.arg

            try:
                parsed_revision = parsed_import.search('revision-date')[0].arg
            except IndexError:
                parsed_revision = None
            new_dependency.revision = parsed_revision

            yang_file = get_yang(new_dependency.name, new_dependency.revision)
            if not yang_file:
                self.logger.error('Import {} can not be found'.format(new_dependency.name))
                imports.append(new_dependency)
                continue
            # This will match new_dependency.revision unless new_dependency.revision is None
            revision = yang_file.split('@')[-1].removesuffix('.yang')  # pyright: ignore
            new_dependency.schema = f'{self.domain_prefix}/all_modules/{new_dependency.name}@{revision}.yang'
            imports.append(new_dependency)

        return imports
