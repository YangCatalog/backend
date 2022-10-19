import logging
import re
import typing as t

from pyang.statements import Statement

from parseAndPopulate.resolvers.resolver import Resolver

"""
This resolver resolves yang module 'semantic_version' property.
Allowed values have to match following regex: [0-9]+.[0-9]+.[0-9]+
Default value: None
"""

VERSION_REGEX = r'[0-9]+\.[0-9]+\.[0-9]+'


class SemanticVersionResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger

    def resolve(self) -> t.Optional[str]:
        self.logger.debug('Resolving semantic version')
        # cisco specific modules - semver defined is inside revision - cisco-semver:module-version
        try:
            parsed_semver = self.parsed_yang.search('revision')[0].search(('cisco-semver', 'module-version'))[0].arg
            return re.findall(VERSION_REGEX, parsed_semver).pop()
        except IndexError:
            pass

        # cisco specific modules - semver defined is inside revision - reference
        try:
            parsed_semver = self.parsed_yang.search('revision')[0].search('reference')[0].arg
            return re.findall(VERSION_REGEX, parsed_semver).pop()
        except IndexError:
            pass

        # openconfig specific modules
        try:
            parsed_semver = self.parsed_yang.search(('oc-ext', 'openconfig-version'))[0].arg
            return re.findall(VERSION_REGEX, parsed_semver).pop()
        except IndexError:
            pass

        return None
