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
MessageFactory class that send automated messages to
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
        self.__me = config.get('Web-Section', 'domain-prefix')

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

    def __post_to_spark(self, msg: str, markdown: bool = False, files: list = []):
        """Send message to a spark room

        Arguments:
            :param msg          (str) message to send
            :param markdown     (bool) whether to use markdown. Default False
            :param files        (list) list of paths to files that need to be attached with the message. Default None
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
            self.__api.messages.create(self.__room.id, markdown=msg, files=files or None)
        else:
            self.__api.messages.create(self.__room.id, text=msg, files=files or None)

        if files:
            for f in files:
                os.remove(f)

    def __post_to_email(self, message: str, email_to: list = [], subject: str = '', subtype: str = 'plain'):
        """Send message to an e-mail

        Arguments:
            :param message      (str) message to send
            :param email_to     (list) list of emails to send the message to
            :param subject      (str) subject string
            :param subtype      (str) MIME text sybtype of the message. Default is "plain".
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

    def _html_user_reminder_message(self, user_data: dict):
        """Generate the user reminder message in HTML format
    
        Arguments:
            :param user_data  (dict) dictionary containing the data of approved and pending users
        """
        ret_text = '<h3>approved users</h3>'

        ret_text += '<table style="width:100%"><tr>'
        for header in ['user', 'name', 'surname', 'sdo_rights', 'vendor_rights', 'organization', 'email']:
            ret_text += '<th>{}</th>'.format(header)
        ret_text += '</tr>'

        for fields in user_data['approved']:
            ret_text += '<tr>'
            for key in ['username', 'first-name', 'last-name', 'access-rights-sdo', 'access-rights-vendor', 'models-provider', 'email']:
                ret_text += '<td>{}</td>'.format(str(fields.get(key)))
            ret_text += '</tr>'
        ret_text += '</table><br>'

        ret_text += '<h3>users pending approval</h3>'

        ret_text += '<table style="width:100%"><tr>'
        for header in ['user', 'name', 'surname', 'organization', 'email']:
            ret_text += '<th>{}</th>'.format(header)
        ret_text += '<tr>'

        for fields in user_data['temp']:
            ret_text += '<tr>'
            for key in ['username', 'first-name', 'last-name', 'models-provider', 'email']:
                ret_text += '<td>{}</td>'.format(str(fields.get(key)))
            ret_text += '</tr>'
        ret_text += '</table>'

        return ('<DOCTYPE html>\n<html>\n<style>table, th, td {border:1px solid black;}</style><body>\n'
                + '{}\n\nTime to review the user profiles: affiliations and capabilities'
                '\n\n{}\n</body>\n</html>'
                .format(GREETINGS, ret_text))

    def _markdown_user_reminder_message(self, users_stats: dict):
        """Generate the user reminder message in Markdown format
        
        Arguments:
            :param user_data  (dict) dictionary containing the data of approved and pending users
        """
        tables_text = 'approved users\n'

        tables_text += '```\n'
        headers = [('user', 25), ('name', 20), ('surname', 20), ('sdo_rights', 20),
                   ('vendor_rights', 20), ('organization', 30), ('email', 30)]
        for header, width in headers:
            tables_text += header.ljust(width)
        tables_text += '\n'

        keys = [('username', 25), ('first-name', 20), ('last-name', 20), ('access-rights-sdo', 20),
                ('access-rights-vendor', 20), ('models-provider', 30), ('email', 30)]
        for fields in users_stats['approved']:
            for key, width in keys:
                tables_text += str(fields.get(key)).ljust(width)
            tables_text += '\n'
        tables_text += '```\n'

        tables_text += '\n\nusers pending approval\n'

        tables_text += '```\n'
        headers = [('user', 25), ('name', 20), ('surname', 20), ('organization', 30), ('email', 30)]
        for header, width in headers:
            tables_text += header.ljust(width)
        tables_text += '\n'

        keys = [('username', 25), ('first-name', 20), ('last-name', 20), ('models-provider', 30), ('email', 30)]
        for fields in users_stats['temp']:
            for key, width in keys:
                tables_text += str(fields.get(key)).ljust(width)
            tables_text += '\n'
        tables_text += '```\n'

        return ('{}\n\nTime to review the user profiles: affiliations and capabilities\n\n{}'
                .format(GREETINGS, tables_text))

    def send_user_reminder_message(self, user_data):
        """Send a message with the current data of pending and approved users.
        Messages are sent to Cisco Webex in markdown format, and e-mails in HTML format.
        
        Arguments:
            :param user_data  (dict) dictionary containing the data of approved and pending users
        """
        self.__post_to_spark(self._markdown_user_reminder_message(user_data), markdown=True)
        self.__post_to_email(self._html_user_reminder_message(user_data), subtype='html')

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
        """Send a message to Cisco Webex notifying about failed authorization
        on the endpoint for Travis jobs.
        """
        self.LOGGER.info('Sending notification about travis authorization failed')
        message = ('Travis pull job not sent because patch was not sent from'
                   ' travis. Key verification failed')
        self.__post_to_spark(message)

    def send_automated_procedure_failed(self, arguments: list, file: str):
        """Send a message to Cisco Webex notifying about a failed job started from
        the admin UI.
        
        Arguments:
            :param arguments    (list) A list of arguments passed to the job.
            :param file         (str) Path to a file to attatch.
        """
        self.LOGGER.info('Sending notification about any automated procedure failure')
        message = ('Automated procedure with arguments:\n {} \nfailed with error.'
                   ' Please see attached document'
                   .format(arguments))
        self.__post_to_spark(message, True, files=[file])

    def send_removed_temp_diff_files(self):
        # TODO send spark message about removed searched diff files
        pass

    def send_removed_yang_files(self, removed_yang_files: str):
        """Send a message to Cisco Webex notifying about removed YANG modules.
        
        Arguments:
            :param removed_yang_files   (str) Dumped JSON object containing
                a list of YANG modules which have been removed.
        """
        self.LOGGER.info('Sending notification about removed YANG modules')
        message = 'Files have been removed from yangcatalog.org. See attached document'
        text = ('The following files has been removed from https://yangcatalog.org'
                ' using the API: \n{}\n'.format(removed_yang_files))
        with open(self._message_log_file, 'w') as f:
            f.write(text)
        self.__post_to_spark(message, True, files=[self._message_log_file])

    def send_added_new_yang_files(self, added_yang_files: str):
        """Send a message to Cisco Webex notifying about new YANG modules.
        
        Arguments:
            :param added_yang_files     (str) Dumped JSON object containing
                a list of new YANG modules.
        """
        self.LOGGER.info('Sending notification about added yang modules')
        message = 'Files have been added to yangcatalog.org. See attached document'
        text = ('The following files have been added to https://yangcatalog.org'
                ' using the API as new modules or old modules with new '
                'revision: \n{}\n'.format(added_yang_files))
        with open(self._message_log_file, 'w') as f:
            f.write(text)
        self.__post_to_spark(message, True, files=[self._message_log_file])

    def send_new_modified_platform_metadata(self, new_files: list, modified_files: list):
        """Send a message to Cisco Webex notifying about new or modified platform
        metadata.
        
        Arguments:
            :param new_files        (list) A list of newly added files.
            :param modified_files   (list) A list of modified files.
        """
        self.LOGGER.info(
            'Sending notification about new or modified platform metadata')
        new_files_string = '\n'.join(new_files)
        modified_files_string = '\n'.join(modified_files)
        message = 'Files have been modified in yangcatalog.org. See attached document'
        text = ('There were new or modified platform metadata json files '
                'added to yangModels/yang repository, that are currently'
                'being processed in following paths:\n\n'
                '\n New json files: \n {} \n\n Modified json files:\n{}\n'
                .format(new_files_string, modified_files_string))
        with open(self._message_log_file, 'w') as f:
            f.write(text)
        self.__post_to_spark(message, True, files=[self._message_log_file])

    def send_github_unavailable_schemas(self, modules_list: list):
        """Send an e-mail message notifying about schemas which could not be fetched
        from GitHub.
        
        Arguments:
            :param modules_list     (list) A list of modules whose schemas could not
                be fetched.
        """
        self.LOGGER.info('Sending notification about unavailable schemas')
        message = ('Following modules could not be retreived from GitHub '
                   'using the schema path:\n{}'.format('\n'.join(modules_list)))
        self.__post_to_email(message, self.__developers_email)

    def send_new_user(self, username: str, email: str, motivation: str):
        """Send an e-mail message notifying about a new user sign up request.
        
        Arguments:
            :param username     (str) Username of the new user.
            :param email        (str) Email used to register.
            :param motivation   (str) The user's submitted reason for registering.
        """
        self.LOGGER.info('Sending notification about new user')

        subject = 'Request for access confirmation'
        msg = 'User {} with email {} is requesting access.\nMotivation: {}\nPlease go to https://yangcatalog.org/admin/users-management ' \
              'and approve or reject this request in Users tab.'.format(username, email, motivation)
        self.__post_to_email(msg, subject=subject)

    def send_confd_writing_failures(self, type: str, data: dict):
        """Send an e-mail message notifying about data not accepted by ConfD.

        Arguments:
            :param type     (str) Type of the data, either 'vendors' or 'modules'
            :param data     (dict) Dictionary containg the rejected data.
        """
        subject = 'Following {} failed to write to ConfD'.format(type)
        self.LOGGER.info(subject)

        message = '{}\n\n'.format(subject)
        for key, error in data.items():
            message += '\n{}:\n'.format(key)
            message += json.dumps(error, indent=2)

        self.__post_to_email(message, email_to=self.__developers_email, subject=subject)
