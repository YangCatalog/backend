import logging
import typing as t

from parseAndPopulate.resolvers.resolver import Resolver

"""
This resolver resolves yang module 'generated_from' property.
Allowed values are: ['mib', 'native', 'not-applicable']
Default value: 'not-applicable'
"""

DEFAULT = 'not-applicable'


class GeneratedFromResolver(Resolver):
    def __init__(self, logger: logging.Logger, name: str, namespace: t.Optional[str]) -> None:
        self.logger = logger
        self.name = name
        self.namespace = namespace

    def resolve(self) -> str:
        if self.namespace and ':smi' in self.namespace:
            return 'mib'
        if 'cisco' in self.name.lower():
            return 'native'
        return DEFAULT
