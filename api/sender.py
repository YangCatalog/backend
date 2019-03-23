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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import datetime
import uuid
import time
import pika

import utility.log as log


class Sender:
    def __init__(self, log_directory, temp_dir):
        self.LOGGER = log.get_logger('sender', log_directory + '/yang.log')
        self.LOGGER.debug('Initializing sender')
        self.__response_type = ['Failed', 'In progress',
                                'Finished successfully', 'does not exist']

        # Let try to connect to RabbitMQ until success..
        while (True):
            try:
                self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters('127.0.0.1', heartbeat=0))
                break
            except pika.exceptions.ConnectionClosed:
                self.LOGGER.debug('Cannot connect to rabbitMQ, trying after a sleep')
                time.sleep(60)
            
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='module_queue')
        self.__temp_dir = temp_dir
        self.__response_file = 'correlation_ids'
        self.LOGGER.debug('Sender initialized')

    def get_response(self, correlation_id):
        """Get response according to job_id. It can be either
        'Failed', 'In progress', 'Finished successfully' or 'does not exist'
                Arguments:
                    :param correlation_id: (str) job_id searched between
                     responses
                    :return one of the following - 'Failed', 'In progress',
                        'Finished successfully' or 'does not exist'
        """
        self.LOGGER.debug('Trying to get response from correlation ids')

        f = open('{}/{}'.format(self.__temp_dir, self.__response_file), 'r')
        lines = f.readlines()
        f.close()
        for line in lines:
            if correlation_id == line.split('- ')[1].strip():
                return line.split('- ')[-1]

        return self.__response_type[3]

    def send(self, arguments):
        """Send data to receiver queue to process
                Arguments:
                    :param arguments: (str) arguments to process in receiver
                    :return job_id
        """
        self.LOGGER.info('Sending data to queue with arguments: {}'
                    .format(arguments))
        corr_id = str(uuid.uuid4())
        self.channel.basic_publish(exchange='',
                                   routing_key='module_queue',
                                   properties=pika.BasicProperties(
                                       correlation_id=corr_id,
                                   ),
                                   body=str(arguments))
        with open('{}/{}'.format(self.__temp_dir, self.__response_file), 'a') as f:
            line = '{} -- {} - {}\n'.format(datetime.datetime.now().ctime(),
                                            corr_id, self.__response_type[1])
            f.write(line)

        return corr_id
