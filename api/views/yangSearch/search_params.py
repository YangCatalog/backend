from dataclasses import dataclass
from typing import List


@dataclass
class SearchParams:
    case_sensitive: bool
    use_synonyms: bool
    query_type: str
    include_mibs: bool
    latest_revision: bool
    include_drafts: bool
    searched_fields: List
    yang_versions: List
    schema_types: List
    output_columns: List
    sub_search: List
