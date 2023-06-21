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

__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2023, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilincik@pantheon.tech'

import os
import time
import unittest
import uuid

from jobs.app import BackendCeleryApp
from jobs.jobs_information import get_response
from jobs.status_messages import StatusMessage

celery_app = BackendCeleryApp('celery_app')
celery_app.config_from_object('jobs.celery_configuration')


@celery_app.task
def example_task(file: str):
    open(file, 'w').close()
    return


class TestCeleryAppBaseClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources_path = os.path.join(os.environ['BACKEND'], 'tests/resources')

    def test_success(self):
        file = os.path.join(self.resources_path, str(uuid.uuid4()))
        task_id = example_task.s(file=file).apply_async().id
        time.sleep(1)
        self.assertEqual(get_response(celery_app, task_id)[0], StatusMessage.SUCCESS.value)
        self.assertTrue(os.path.exists(file))

    def test_fail(self):
        file = os.path.join('/', str(uuid.uuid4()))
        task_id = example_task.s(file=file).apply_async().id
        time.sleep(1)
        self.assertEqual(get_response(celery_app, task_id)[0], StatusMessage.FAIL.value)
