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
MessageFactory class that send a automated messages to
specified rooms or people.
"""

__author__ = 'Miroslav Kovac'
__copyright__ = 'Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'miroslav.kovac@pantheon.tech'

import json
import os
import smtplib
import sys
from email.mime.text import MIMEText

from ciscosparkapi import CiscoSparkAPI

import utility.log as log
from utility.create_config import create_config

GREETINGS = 'Hello from yang-catalog'


class MessageFactory:
    """This class serves to automatically send a message to
       Webex Teams cisco admins private room and/or to send
       a message to a group of admin e-mails
    """

    def __init__(self, config_path=os.environ['YANGCATALOG_CONFIG_PATH']):
        """Setup Webex teams rooms and smtp

            Arguments:
                :param config_path: (str) path to a yangcatalog.conf file
        """
        def list_matching_rooms(a, title_match):
            return [r for r in a.rooms.list() if title_match in r.title]

        config = create_config(config_path)
        log_directory = config.get('Directory-Section', 'logs')
        token = config.get('Secrets-Section', 'webex-access-token')
        self.__email_from = config.get('Message-Section', 'email-from')
        self.__is_production = config.get('General-Section', 'is-prod')
        self.__is_production = self.__is_production == 'True'
        self.__email_to = config.get('Message-Section', 'email-to').split()
        self.__developers_email = config.get('Message-Section', 'developers-email').split()
        self._temp_dir = config.get('Directory-Section', 'temp')
        self.__me = config.get('Web-Section', 'my-uri')

        self.__api = CiscoSparkAPI(access_token=token)
        rooms = list_matching_rooms(self.__api, 'YANG Catalog admin')
        self.__me = self.__me.split('/')[-1]
        self._message_log_file = os.path.join(self._temp_dir, 'message-log.txt')
        self.LOGGER = log.get_logger(__name__, os.path.join(log_directory, 'yang.log'))
        self.LOGGER.info('Initialising Message Factory')

        if len(rooms) == 0:
            self.LOGGER.error('Need at least one room')
            sys.exit(1)
        if len(rooms) != 1:
            self.LOGGER.error('Too many rooms! Refine the name:')
            for r in rooms:
                self.LOGGER.info('{}'.format(r.title))
            sys.exit(1)

        # Ok, we should have just one room if we get here
        self.__room = rooms[0]
        self.__smtp = smtplib.SMTP('localhost')

    def __post_to_spark(self, msg: str, markdown: bool = False, files: list = None):
        """Send message to a spark room

        Arguments:
            :param msg          (str) message to send
            :param markdown     (bool) whether to use markdown. Default False
            :param files        (list) list of paths to files that need to be attache with a message. Default None
        """
        msg += '\n\nMessage sent from {}'.format(self.__me)
        if not self.__is_production:
            self.LOGGER.info('You are in local env. Skip sending message to cisco webex teams. The message was\n{}'
                             .format(msg))
            if files:
                for f in files:
                    os.remove(f)
            return
        if markdown:
            self.__api.messages.create(self.__room.id, markdown=msg, files=files)
        else:
            self.__api.messages.create(self.__room.id, text=msg, files=files)

        if files:
            for f in files:
                os.remove(f)

    def __post_to_email(self, message: str, email_to: list = None, subject: str = None, subtype: str = 'plain'):
        """Send message to an e-mail

            Arguments:
                :param message      (str) message to send
                :param email_to     (list) list of emails to send the message to
        """
        send_to = email_to if email_to else self.__email_to
        msg = MIMEText(message + '\n\nMessage sent from {}'.format(self.__me), _subtype=subtype)
        msg['Subject'] = subject if subject else 'Automatic generated message - RFC IETF'
        msg['From'] = self.__email_from
        msg['To'] = ', '.join(send_to)

        if not self.__is_production:
            self.LOGGER.info('You are in local env. Skip sending message to emails. The message format was {}'
                             .format(msg))
            self.__smtp.quit()
            return
        self.__smtp.sendmail(self.__email_from, send_to, msg.as_string())
        self.__smtp.quit()

    def send_user_reminder_message(self, users_stats):
        message = ('<DOCTYPE html>\n<html>\n<style>table, th, td {border:1px solid black;}</style><body>\n'
                   + '{}\n\nTime to review the user profiles: affiliations and capabilities'
                   '\n\n{}\n</body>\n</html>'
                   .format(GREETINGS, users_stats))

        self.__post_to_spark(message)
        self.__post_to_email(message, subtype='html')

    def send_new_rfc_message(self, new_files, diff_files):
        self.LOGGER.info('Sending notification about new IETF RFC modules')
        new_files = '\n'.join(new_files)
        diff_files = '\n'.join(diff_files)
        message = ('{}\n\nSome of the files are different'
                   ' in https://yangcatalog.org/private/IETFYANGRFC.json against'
                   ' yangModels/yang repository\n\n'
                   'Files that are missing in yangModels/yang repository: \n{} \n\n '
                   'Files that are different than in yangModels repository: \n{} '
                   .format(GREETINGS, new_files, diff_files))

        self.__post_to_spark(message)
        self.__post_to_email(message)

    def send_travis_auth_failed(self):
        self.LOGGER.info('Sending notification about travis authorization failed')
        message = ('Travis pull job not sent because patch was not sent from'
                   ' travis. Key verification failed')
        self.__post_to_spark(message)

    def send_automated_procedure_failed(self, procedure, file):
        self.LOGGER.info('Sending notification about any automated procedure failure')
        message = ('Automated procedure with arguments:\n {} \nfailed with error.'
                   ' Please see attached document'
                   .format(procedure))
        self.__post_to_spark(message, True, files=[file])

    def send_removed_temp_diff_files(self):
        # TODO send spark message about removed searched diff files
        pass

    def send_removed_yang_files(self, removed_yang_files):
        self.LOGGER.info('Sending notification about removed YANG modules')
        message = 'Files have been removed from yangcatalog.org. See attached document'
        text = ('The following files has been removed from https://yangcatalog.org'
                ' using the API: \n{}\n'.format(removed_yang_files))
        with open(self._message_log_file, 'w') as f:
            f.write(text)
        self.__post_to_spark(message, True, files=[self._message_log_file])

    def send_added_new_yang_files(self, added_yang_files):
        self.LOGGER.info('Sending notification about added yang modules')
        message = 'Files have been added to yangcatalog.org. See attached document'
        text = ('The following files have been added to https://yangcatalog.org'
                ' using the API as new modules or old modules with new '
                'revision: \n{}\n'.format(added_yang_files))
        with open(self._message_log_file, 'w') as f:
            f.write(text)
        self.__post_to_spark(message, True, files=[self._message_log_file])

    def send_new_modified_platform_metadata(self, new_files, modified_files):
        self.LOGGER.info(
            'Sending notification about new or modified platform metadata')
        new_files = '\n'.join(new_files)
        modified_files = '\n'.join(modified_files)
        message = 'Files have been modified in yangcatalog.org. See attached document'
        text = ('There were new or modified platform metadata json files '
                'added to yangModels/yang repository, that are currently'
                'being processed in following paths:\n\n'
                '\n New json files: \n {} \n\n Modified json files:\n{}\n'
                .format(new_files, modified_files))
        with open(self._message_log_file, 'w') as f:
            f.write(text)
        self.__post_to_spark(message, True, files=[self._message_log_file])

    def send_github_unavailable_schemas(self, modules_list: list):
        self.LOGGER.info('Sending notification about unavailable schemas')
        message = ('Following modules could not be retreived from GitHub '
                   'using the schema path:\n{}'.format('\n'.join(modules_list)))
        self.__post_to_email(message, self.__developers_email)

    def send_new_user(self, username: str, email: str, motivation: str):
        self.LOGGER.info('Sending notification about new user')

        subject = 'Request for access confirmation'
        msg = 'User {} with email {} is requesting access.\nMotivation: {}\nPlease go to https://yangcatalog.org/admin/users-management ' \
              'and approve or reject this request in Users tab.'.format(username, email, motivation)
        self.__post_to_email(msg, subject=subject)

    def send_confd_writing_failures(self, type: str, data: dict):
        subject = 'Following {} failed to write to ConfD'.format(type)
        self.LOGGER.info(subject)

        message = '{}\n\n'.format(subject)
        for key, error in data.items():
            message += '\n{}:\n'.format(key)
            message += json.dumps(error, indent=2)

        self.__post_to_email(message, email_to=self.__developers_email, subject=subject)
