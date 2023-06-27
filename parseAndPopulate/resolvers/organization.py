import logging
import typing as t

from pyang.statements import Statement

from parseAndPopulate.resolvers.resolver import Resolver
from utility.staticVariables import NAMESPACE_MAP, ORGANIZATIONS

"""
This resolver resolves yang module 'organization' property.
Default value: 'independent'
"""

DEFAULT = 'independent'


class OrganizationResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger, namespace: t.Optional[str]) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.namespace = namespace

    def resolve(self) -> str:
        try:
            parsed_organization = self.parsed_yang.search('organization')[0].arg.lower()
            for possible_organization in ORGANIZATIONS:
                if possible_organization in parsed_organization:
                    return possible_organization
        except IndexError:
            pass

        if not self.namespace:
            return DEFAULT

        for ns, org in NAMESPACE_MAP:
            if ns in self.namespace:
                return org
        if 'cisco' in self.namespace:
            return 'cisco'
        if 'ietf' in self.namespace:
            return 'ietf'
        if 'urn:' in self.namespace:
            return self.namespace.split('urn:')[1].split(':')[0]
        return DEFAULT
