import logging
import typing as t

from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.resolvers.resolver import Resolver

""" 
This resolver resolves yang module 'maturity_level' property.
Allowed values are: ['ratified', 'adopted', 'initial', 'not-applicable']
Default value: None
"""


class MaturityLevelResolver(Resolver):
    def __init__(self, logger: logging.Logger, name_revision: str, jsons: LoadFiles) -> None:
        self.logger = logger
        self.name_revision = name_revision
        self.jsons = jsons

    def resolve(self) -> t.Optional[str]:
        self.logger.debug('Resolving maturity level')
        name = self.name_revision.split('@')[0]
        yang_name = '{}.yang'.format(name)
        yang_name_revision = '{}.yang'.format(self.name_revision)

        maturity_level = self._find_between_drafts(yang_name) \
            or self._find_between_drafts(yang_name_revision) \
            or self._find_between_rfcs(yang_name_revision) \
            or self._find_between_rfcs(yang_name)

        return maturity_level

    def _find_between_drafts(self, yang_name: str) -> t.Optional[str]:
        """ Try to find in IETFDraft.json with or without revision """
        try:
            datatracker_href = self.jsons.status['IETFDraft'][yang_name][0]
            maturity_level = datatracker_href.split('</a>')[0].split('\">')[1].split('-')[1]
            if 'ietf' in maturity_level:
                return 'adopted'
            return 'initial'
        except KeyError:
            pass
        return None

    def _find_between_rfcs(self, yang_name: str) -> t.Optional[str]:
        """ Try to find in IETFYANGRFC.json with or without revision """
        if self.jsons.status['IETFYANGRFC'].get(yang_name):
            return 'ratified'
        return None
