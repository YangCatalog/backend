from dataclasses import dataclass


@dataclass
class Subquery:
    string: str
    must: bool
    field = 'subquery'


@dataclass
class Name(Subquery):
    regex: bool
    field = 'argument'


@dataclass
class Revision(Subquery):
    field = 'revision'


@dataclass
class Path(Subquery):
    field = 'path'


@dataclass
class ModuleName(Subquery):
    regex: bool
    field = 'module'


@dataclass
class Organization(Subquery):
    field = 'organization'


@dataclass
class Description(Subquery):
    case_insensitive: bool
    use_synonyms: bool
    regex: bool
    field = 'description'


@dataclass
class Maturity(Subquery):
    field = 'maturity'


@dataclass
class SearchParams:
    include_mibs: bool
    latest_revision: bool
    include_drafts: bool
    subqueries: list[Subquery]
    yang_versions: list[str]
    schema_types: list[str]
    output_columns: list[str]
    # maturity: t.Optional[str] = None
