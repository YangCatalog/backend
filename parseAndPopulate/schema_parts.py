import os
import typing as t
from dataclasses import dataclass

from utility.staticVariables import GITHUB_RAW


@dataclass
class SchemaParts:
    repo_owner: str
    repo_name: str
    commit_hash: str
    submodule_name: t.Optional[str] = None

    @property
    def schema_base(self) -> str:
        return os.path.join(GITHUB_RAW, self.repo_owner, self.repo_name)

    @property
    def schema_base_hash(self) -> str:
        return os.path.join(self.schema_base, self.commit_hash)
