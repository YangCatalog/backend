import logging
import typing as t

from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.resolvers.resolver import Resolver
from utility.staticVariables import IETF_RFC_MAP

""" 
This resolver resolves yang module 'ietf_wg' (working group) property.
ietf_wg property is specific metadata only for the IETF modules.
Default value: None
"""


class IetfWorkingGroupResolver(Resolver):
    def __init__(self, logger: logging.Logger, name_revision: str, jsons: LoadFiles) -> None:
        self.logger = logger
        self.name_revision = name_revision
        self.jsons = jsons

    def resolve(self) -> t.Optional[str]:
        self.logger.debug('Resolving working group')
        name = self.name_revision.split('@')[0]
        yang_name = '{}.yang'.format(name)
        yang_name_revision = '{}.yang'.format(self.name_revision)

        ietf_wg = self._find_between_drafts(yang_name) \
            or self._find_between_drafts(yang_name_revision) \
            or IETF_RFC_MAP.get(yang_name) \
            or IETF_RFC_MAP.get(yang_name_revision)

        return ietf_wg

    def _find_between_drafts(self, yang_name: str) -> t.Optional[str]:
        """ Try to find in IETFDraft.json with or without revision """
        try:
            datatracker_href = self.jsons.status['IETFDraft'][yang_name][0]
            return datatracker_href.split('</a>')[0].split('\">')[1].split('-')[2]
        except KeyError:
            pass
        return None
