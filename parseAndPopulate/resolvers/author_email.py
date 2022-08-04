import logging
import typing as t

from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.resolvers.resolver import Resolver

""" 
This resolver resolves yang module 'author_email' property.
Default value: None
"""


class AuthorEmailResolver(Resolver):
    def __init__(self, logger: logging.Logger, name_revision: str, jsons: LoadFiles) -> None:
        self.logger = logger
        self.name_revision = name_revision
        self.jsons = jsons

    def resolve(self) -> t.Optional[str]:
        self.logger.debug('Resolving author email')
        name = self.name_revision.split('@')[0]
        yang_name = '{}.yang'.format(name)
        yang_name_revision = '{}.yang'.format(self.name_revision)

        author_email = self._find_between_drafts(yang_name, 'IETFDraft') \
            or self._find_between_drafts(yang_name_revision, 'IETFDraft') \
            or self._find_between_drafts(yang_name, 'IETFDraftExample') \
            or self._find_between_drafts(yang_name_revision, 'IETFDraftExample')

        return author_email

    def _find_between_drafts(self, yang_name: str, json_name: str) -> t.Optional[str]:
        """ Try to find in IETFDraft.json or IETFDraftExample.json with or without revision """
        try:
            mailto_href = self.jsons.status[json_name][yang_name][1]
            return mailto_href.split('\">Email')[0].split('mailto:')[1]
        except KeyError:
            pass
        return None
