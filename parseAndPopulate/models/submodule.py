import typing as t


class Submodule:
    def __init__(self):
        self.name: str
        self.revision: t.Optional[str] = None
        self.schema: t.Optional[str] = None
