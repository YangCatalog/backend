import logging

from pyang.statements import Statement

from parseAndPopulate.resolvers.resolver import Resolver
from utility.util import validate_revision

"""
This resolver resolves yang module 'revision' property.
Allowed values must be in date format "YYYY-MM-DD"
Default value: '1970-01-01'
"""
DEFAULT = '1970-01-01'

# TODO: Maybe store list of the modules with misssing/incorrect revisions somewhere


class RevisionResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger

    def resolve(self) -> str:
        self.logger.debug('Resolving revision')
        try:
            revision = self.parsed_yang.search('revision')[0].arg
        except IndexError:
            self.logger.exception('Error while resolving revision')
            revision = DEFAULT

        return validate_revision(revision)
