import re
import typing as t

from parseAndPopulate.resolvers.resolver import Resolver
from pyang.statements import Statement

""" 
This resolver resolves yang module semantic_version property.
Allowed values have to match following regex: [0-9]+.[0-9]+.[0-9]+
Default value: None
"""


class SemanticVersionResolver(Resolver):
    def __init__(self, parsed_yang: Statement) -> None:
        self.parsed_yang = parsed_yang
        self.property_name = 'semantic_version'

    def resolve(self) -> t.Optional[str]:
        # cisco specific modules - semver defined is inside revision
        try:
            parsed_semver = self.parsed_yang.search('revision')[0].search(('cisco-semver', 'module-version'))[0].arg
            return re.findall('[0-9]+.[0-9]+.[0-9]+', parsed_semver).pop()
        except IndexError:
            pass

        # openconfig specific modules
        try:
            parsed_semver = self.parsed_yang.search(('oc-ext', 'openconfig-version'))[0].arg
            return re.findall('[0-9]+.[0-9]+.[0-9]+', parsed_semver).pop()
        except IndexError:
            pass

        return None
