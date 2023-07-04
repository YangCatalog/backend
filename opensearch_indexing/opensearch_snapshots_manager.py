# Copyright The IETF Trust 2022, All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = 'Slavomir Mazur'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'slavomir.mazur@pantheon.tech'

import os
from operator import itemgetter

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError

import utility.log as log
from opensearch_indexing.models.opensearch_indices import OpenSearchIndices
from utility.create_config import create_config


class OpenSearchSnapshotsManager:
    def __init__(self) -> None:
        config = create_config()
        log_directory = config.get('Directory-Section', 'logs')
        opensearch_aws = config.get('DB-Section', 'opensearch-aws')
        opensearch_credentials = config.get('Secrets-Section', 'opensearch-secret').strip('"').split(' ')
        self.opensearch_repo_name = config.get('General-Section', 'opensearch-repo-name')
        opensearch_host_config = {
            'host': config.get('DB-Section', 'opensearch-host', fallback='localhost'),
            'port': config.get('DB-Section', 'opensearch-port', fallback='9200'),
        }
        if opensearch_aws == 'True':
            self.opensearch = OpenSearch(
                hosts=[opensearch_host_config],
                http_auth=(opensearch_credentials[0], opensearch_credentials[1]),
                scheme='https',
            )
        else:
            self.opensearch = OpenSearch(hosts=[opensearch_host_config])
        log_file_path = os.path.join(log_directory, 'jobs', 'opensearch-manager.log')
        self.LOGGER = log.get_logger('opensearch-snapshots-manager', log_file_path)

    def create_snapshot_repository(self, compress: bool) -> dict:
        """Register a snapshot repository."""
        body = {'type': 'fs', 'settings': {'location': self.opensearch_repo_name, 'compress': compress}}
        return self.opensearch.snapshot.create_repository(repository=self.opensearch_repo_name, body=body)

    def create_snapshot(self, snapshot_name: str) -> dict:
        """Creates a snapshot with given 'snapshot_name' in a snapshot repository.

        Argument:
            :param snapshot_name    (str) Name of the snapshot to be created
        """
        index_body = {'indices': '_all'}
        return self.opensearch.snapshot.create(
            repository=self.opensearch_repo_name,
            snapshot=snapshot_name,
            body=index_body,
        )

    def get_sorted_snapshots(self) -> list:
        """Return a sorted list of existing snapshots."""
        try:
            snapshots = self.opensearch.snapshot.get(repository=self.opensearch_repo_name, snapshot='_all')
        except NotFoundError:
            self.LOGGER.exception('Snapshots not found')
            return []
        return sorted(snapshots['snapshots'], key=itemgetter('start_time_in_millis'))

    def restore_snapshot(self, snapshot_name: str) -> dict:
        """Restore snapshot which is given by 'snapshot_name'.

        Argument:
            :param snapshot_name    (str) Name of the snapshot to restore
        """
        index_body = {'indices': '_all'}
        for index in OpenSearchIndices:
            try:
                self.opensearch.indices.close(index.value)
            except NotFoundError:
                continue

        return self.opensearch.snapshot.restore(
            repository=self.opensearch_repo_name,
            snapshot=snapshot_name,
            body=index_body,
            wait_for_completion=True,
        )

    def delete_snapshot(self, snapshot_name: str) -> dict:
        """Delete snapshot which is given by 'snapshot_name'.

        Argument:
            :param snapshot_name    (str) Name of the snapshot to delete
        """
        return self.opensearch.snapshot.delete(repository=self.opensearch_repo_name, snapshot=snapshot_name)
