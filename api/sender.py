# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
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

"""
Rabbitmq is needed to be installed for this script to work.
This script is part of messaging algorithm works together
with receiver.py. API endpoints that take too long time to
process will send a request to process data to the receiver
with some message id. Sender is used to generate this id
and send the message with this id and some body which receiver
should understand.Once receiver is done processing data
it will send back the response using the message id.

Receiver is used to add, update or remove yang modules.
This process take a long time depending on the number
of the yang modules. This script is also used to automatically
add or update new IETF and Openconfig modules.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import datetime
import logging
import os
import time
import uuid

import pika
import pika.exceptions

import utility.log as log
from api.status_message import StatusMessage


class Sender:
    def __init__(
        self,
        log_directory,
        temp_dir,
        rabbitmq_host='127.0.0.1',
        rabbitmq_port=None,
        rabbitmq_virtual_host=None,
        rabbitmq_username='guest',
        rabbitmq_password='guest',
    ):
        self.LOGGER = log.get_logger('sender', log_directory + '/yang.log')
        logging.getLogger('pika').setLevel(logging.INFO)
        self.LOGGER.debug('Initializing sender')
        self._rabbitmq_host = rabbitmq_host
        self._rabbitmq_port = rabbitmq_port
        self._rabbitmq_virtual_host = rabbitmq_virtual_host
        self._credentials = pika.PlainCredentials(username=rabbitmq_username, password=rabbitmq_password)
        # Let try to connect to RabbitMQ until success..

        self._temp_dir = temp_dir
        self._response_file = 'correlation_ids'
        self.LOGGER.debug('Sender initialized')

    def get_response(self, correlation_id: str) -> str:
        """Get response according to job_id. It can be either
        'Failed', 'In progress', 'Finished successfully' or 'does not exist'

        Arguments:
            :param correlation_id: (str) job_id searched between
                responses
            :return                (str) one of the following - 'Failed', 'In progress',
                'Finished successfully' or 'Does not exist'
        """
        self.LOGGER.debug('Trying to get response from correlation ids')

        with open(os.path.join(self._temp_dir, self._response_file), 'r') as f:
            lines = f.readlines()
        for line in lines:
            if correlation_id == line.split('- ')[1].strip():
                return line.split('- ')[-1].strip()

        return StatusMessage.NONEXISTENT.value

    def send(self, arguments: list) -> str:
        """Send data to receiver queue to process

        Arguments:
            :param arguments: (str) arguments to process in receiver
            :return job_id
        """
        self.LOGGER.info(f'Sending data to queue with arguments: {arguments}')
        while True:
            try:
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=self._rabbitmq_host,
                        port=self._rabbitmq_port,
                        virtual_host=self._rabbitmq_virtual_host,
                        credentials=self._credentials,
                    ),
                )
                channel = connection.channel()
                channel.queue_declare(queue='module_queue')
                break
            except pika.exceptions.ConnectionClosed:
                self.LOGGER.debug('Cannot connect to rabbitMQ, trying after a sleep')
                time.sleep(3)
        corr_id = str(uuid.uuid4())
        channel.basic_publish(
            exchange='',
            routing_key='module_queue',
            body=str(arguments),
            properties=pika.BasicProperties(correlation_id=corr_id),
        )
        with open(os.path.join(self._temp_dir, self._response_file), 'a') as f:
            line = f'{datetime.datetime.now().ctime()} -- {corr_id} - {StatusMessage.IN_PROGRESS}\n'
            f.write(line)
        connection.close()
        return corr_id
