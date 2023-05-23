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

from utility.create_config import create_config

config = create_config()

_rabbitmq_host = config.get('RabbitMQ-Section', 'host', fallback='yc-rabbit')
_rabbitmq_port = config.get('RabbitMQ-Section', 'port', fallback='5672')
_rabbitmq_virtual_host = config.get('RabbitMQ-Section', 'virtual-host', fallback='/')
_rabbitmq_username = config.get('RabbitMQ-Section', 'username', fallback='guest')
_rabbitmq_password = config.get('Secrets-Section', 'rabbitmq-password', fallback='guest')

_redis_host = config.get('DB-Section', 'redis-host', fallback='yc-redis')
_redis_port = config.get('DB-Section', 'redis-port', fallback='6379')

broker_url = result_backend = f'amqp://{_rabbitmq_username}:{_rabbitmq_password}@{_rabbitmq_host}:{_rabbitmq_port}//'
# TODO: update Celery to the latest version and switch to 'rpc://' result backend when this issue is resolved:
#  https://github.com/celery/celery/issues/4084
# result_backend = 'rpc://'

task_track_started = True

# specify all folders with celery tasks for proper tasks' auto discovering, for example: ['job_runner.other_tasks']
include = []

# this setting specifies that we can have only one running task at a time (this is done intentionally)
worker_concurrency = 1

task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
enable_utc = True
