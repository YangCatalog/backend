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
