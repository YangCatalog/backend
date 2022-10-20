import logging

from pyang.statements import Statement

from parseAndPopulate.resolvers.resolver import Resolver

"""
This resolver resolves yang module 'yang_version' property.
Allowed values are: [1.0, 1.1]
Default value: 1.0
"""

DEFAULT = '1.0'


class YangVersionResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger

    def resolve(self) -> str:
        self.logger.debug('Resolving yang version')
        try:
            yang_version = self.parsed_yang.search('yang-version')[0].arg
        except IndexError:
            yang_version = DEFAULT

        if yang_version == '1':
            yang_version = DEFAULT
        return yang_version
