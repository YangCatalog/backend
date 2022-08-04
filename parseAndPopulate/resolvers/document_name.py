import logging
import typing as t

from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.resolvers.resolver import Resolver

""" 
This resolver resolves yang module 'document_name' property.
Default value: None
"""


class DocumentNameResolver(Resolver):
    def __init__(self, logger: logging.Logger, name_revision: str, jsons: LoadFiles) -> None:
        self.logger = logger
        self.name_revision = name_revision
        self.jsons = jsons

    def resolve(self) -> t.Optional[str]:
        self.logger.debug('Resolving document name')
        name = self.name_revision.split('@')[0]
        yang_name = '{}.yang'.format(name)
        yang_name_revision = '{}.yang'.format(self.name_revision)

        document_name = self._find_between_drafts(yang_name) \
            or self._find_between_drafts(yang_name_revision) \
            or self._find_between_rfcs(yang_name_revision) \
            or self._find_between_rfcs(yang_name)

        return document_name

    def _find_between_drafts(self, yang_name: str) -> t.Optional[str]:
        """ Try to find in IETFDraft.json with or without revision """
        try:
            datatracker_href = self.jsons.status['IETFDraft'][yang_name][0]
            return datatracker_href.split('</a>')[0].split('\">')[1]
        except KeyError:
            pass
        return None

    def _find_between_rfcs(self, yang_name: str) -> t.Optional[str]:
        """ Try to find in IETFYANGRFC.json with or without revision """
        try:
            datatracker_href = self.jsons.status['IETFYANGRFC'][yang_name]
            return datatracker_href.split('</a>')[0].split('\">')[1]
        except KeyError:
            pass
        return None
