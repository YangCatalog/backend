import typing as t

from pyang.statements import Statement

from parseAndPopulate.resolvers.resolver import Resolver


class BasicResolver(Resolver):
    def __init__(self, parsed_yang: Statement, property_name: str) -> None:
        self.parsed_yang = parsed_yang
        self.property_name = property_name

    def resolve(self) -> t.Optional[str]:
        try:
            return self.parsed_yang.search(self.property_name.replace('_', '-'))[0].arg
        except IndexError:
            return None
