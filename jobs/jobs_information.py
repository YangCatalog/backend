# Copyright The IETF Trust 2023, All Rights Reserved
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

__author__ = 'Bohdan Konovalenko'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'bohdan.konovalenko@pantheon.tech'

from jobs.celery import BackendCeleryApp
from jobs.status_messages import StatusMessage, status_messages_mapping


def get_response(celery_app_instance: BackendCeleryApp, job_id: str) -> tuple[str, str]:
    """
    Get response according to job_id. It can be either 'Failed', 'In progress', 'Finished successfully'

    Arguments:
        :param celery_app_instance (BackendCeleryApp) instance of the celery app
        :param job_id: (str) id of the celery task
    :return (tuple[str, str]) Returns the job status which can be one of the following -
    'Failed', 'In progress', 'Finished successfully' and traceback of the job if the job has failed,
    or the return value if the job is successful, empty string otherwise
    """
    celery_app_instance.logger.debug(f'Trying to get response for task: {job_id}')
    task_result = celery_app_instance.AsyncResult(job_id)
    if not task_result.ready():
        return StatusMessage.IN_PROGRESS.value, ''
    status = status_messages_mapping.get(task_result.status, StatusMessage.IN_PROGRESS.value)
    if status == StatusMessage.FAIL:
        return status, str(task_result.traceback)
    return status, task_result.get()
