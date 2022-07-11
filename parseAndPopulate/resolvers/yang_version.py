from parseAndPopulate.resolvers.resolver import Resolver
from pyang.statements import Statement

""" 
This resolver resolves yang module yang-version property.
Allowed values are: [1.0, 1.1]
Default value: 1.0
"""

DEFAULT = '1.0'


class YangVersionResolver(Resolver):
    def __init__(self, parsed_yang: Statement) -> None:
        self.parsed_yang = parsed_yang
        self.property_name = 'yang_version'

    def resolve(self) -> str:
        try:
            yang_version = self.parsed_yang.search(self.property_name)[0].arg
        except IndexError:
            yang_version = DEFAULT

        if yang_version == '1':
            yang_version = DEFAULT
        return yang_version
