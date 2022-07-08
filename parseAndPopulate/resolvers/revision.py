import logging
from datetime import datetime

from parseAndPopulate.resolvers.resolver import Resolver
from pyang.statements import Statement

""" 
This resolver resolves yang module revision property.
Allowed values must be in date format "YYYY-MM-DD"
Default value: '1970-01-01'
"""
DEFAULT = '1970-01-01'

# TODO: Maybe store list of the modules with misssing/incorrect revisions somewhere


def validate_revision_format(revision: str) -> str:
    year, month, day = revision.split('-')
    try:
        revision = datetime(int(year), int(month), int(day)).date().isoformat()
    except ValueError:
        try:
            if int(day) == 29 and int(month) == 2:
                revision = datetime(int(year), int(month), 28).date().isoformat()
        except ValueError:
            revision = DEFAULT
    return revision


class RevisionResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.property_name = 'revision'

    def resolve(self) -> str:
        try:
            revision = self.parsed_yang.search('revision')[0].arg
        except IndexError:
            self.logger.exception('Error while resolving revision')
            revision = DEFAULT

        return validate_revision_format(revision)
