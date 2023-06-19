from enum import Enum


class OpenSearchIndices(Enum):
    YINDEX = 'yindex-alias'
    MODULES = 'modules-alias'
    DRAFTS = 'drafts-alias'
    AUTOCOMPLETE = 'autocomplete-alias'
    TEST = 'test'
    TEST_SEARCH = 'test_search'
