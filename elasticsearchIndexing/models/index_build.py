import typing as t


class BuildYINDEXModule(t.TypedDict):
    """Contains information needed for adding a module to the YINDEX"""

    name: str
    revision: str
    organization: str
    path: str
