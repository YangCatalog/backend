import logging
import os
import typing as t

from git import InvalidGitRepositoryError
from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.models.schema_parts import SchemaParts
from parseAndPopulate.resolvers.resolver import Resolver
from pyang.statements import Statement
from utility import repoutil
from utility.staticVariables import github_url
from utility.util import get_yang

"""
This resolver resolves yang module dependecies property,
which are defined as 'import' in yang models.
Default value: [] -> no imports
"""


class ImportsResolver(Resolver):
    def __init__(self, parsed_yang: Statement, logger: logging.Logger, path: str, schema: t.Optional[str],
                 schemas: dict, yang_models_dir: str, nonietf_dir: str) -> None:
        self.parsed_yang = parsed_yang
        self.logger = logger
        self.path = path
        self.schema = schema
        self.schemas = schemas
        self.yang_models_dir = yang_models_dir
        self.nonietf_dir = nonietf_dir

    def resolve(self):
        imports = []
        parsed_imports = self.parsed_yang.search('import')
        for parsed_import in parsed_imports:
            new_dependency = Dependency()
            new_dependency.name = parsed_import.arg

            try:
                parsed_revision = parsed_import.search('revision-date')[0].arg
            except IndexError:
                parsed_revision = None
            new_dependency.revision = parsed_revision

            yang_file = get_yang(new_dependency.name, new_dependency.revision)
            if not yang_file:
                self.logger.error('Import {} can not be found'.format(new_dependency.name))
                imports.append(new_dependency)
                continue
            # This will match new_dependency.revision unless new_dependency.revision is None
            revision = new_dependency.revision or yang_file.split('@')[-1].removesuffix('.yang')  # pyright: ignore
            try:
                name_revision = '{}@{}'.format(new_dependency.name, revision)
                local_yang_file = os.path.join(os.path.dirname(self.path), '{}.yang'.format(new_dependency.name))
                if name_revision in self.schemas:
                    new_dependency.schema = self.schemas[name_revision]
                elif os.path.exists(local_yang_file) and self.schema:
                    new_dependency.schema = os.path.join(os.path.dirname(self.schema), os.path.basename(local_yang_file))
                else:
                    imports.append(new_dependency)
                    continue
            except Exception:
                self.logger.exception('Unable to resolve schema for {}@{}'.format(
                    new_dependency.name, new_dependency.revision))
            imports.append(new_dependency)

        return imports

    def _get_openconfig_schema_parts(self, yang_file: str) -> t.Optional[str]:
        """ Get SchemaParts object if imported file was found in openconfig/public repository. """
        suffix = os.path.abspath(yang_file).split('/openconfig/public/')[-1]
        # Load/clone openconfig/public repo
        repo_owner = 'openconfig'
        repo_name = 'public'
        repo_url = os.path.join(github_url, repo_owner, repo_name)
        repo_dir = os.path.join(self.nonietf_dir, 'openconfig/public')
        try:
            repo = repoutil.load(repo_dir, repo_url)
        except InvalidGitRepositoryError:
            self.logger.error('Unable to load {} repository'. format(repo_url))
            repo = repoutil.RepoUtil(repo_url, clone_options={'local_dir': repo_dir})

        new_schema_parts = SchemaParts(repo_owner=repo_owner, repo_name=repo_name,
                                       commit_hash=repo.get_commit_hash(suffix))
        return os.path.join(new_schema_parts.schema_base_hash, suffix)

    def _get_yangmodels_schema_parts(self, yang_file: str) -> t.Optional[str]:
        """ Get SchemaParts object if imported file was found in YangModels/yang repository. 
        This repository also contains several git submodules, so it is necessary to check 
        whether file is part of submodule or not. 
        """
        suffix = os.path.abspath(yang_file).split('/yangmodels/yang/')[-1]
        # Load/clone YangModels/yang repo
        repo_owner = 'YangModels'
        repo_name = 'yang'
        repo_url = os.path.join(github_url, repo_owner, repo_name)
        try:
            repo = repoutil.load(self.yang_models_dir, repo_url)
        except InvalidGitRepositoryError:
            self.logger.error('Unable to load {} repository'. format(repo_url))
            repo = repoutil.RepoUtil(repo_url, clone_options={'local_dir': self.yang_models_dir})

        # Check if repository is a submodule
        for submodule in repo.repo.submodules:
            if submodule.name in suffix:
                repo_url = submodule.url.lower()
                repo_dir = os.path.join(self.yang_models_dir, submodule.name)
                repo = repoutil.load(repo_dir, repo_url)
                repo_owner = repo.get_repo_owner()
                repo_name = repo.get_repo_dir().split('.git')[0]
                suffix = suffix.replace('{}/'.format(submodule.name), '')

        new_schema_parts = SchemaParts(repo_owner=repo_owner, repo_name=repo_name,
                                       commit_hash=repo.get_commit_hash(suffix))
        return os.path.join(new_schema_parts.schema_base_hash, suffix)
