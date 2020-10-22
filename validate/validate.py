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
This tool let us decide what user has access to which part
of the tree from yangcatalog.yang module, by prompting us
with several questions.

Do they need vendor access
   if yes what is their vendor branch (example Cisco)

Do they need sdo (model) access?
   if yes what is their model organization

Finally it will create recapitulation with user name
and access you are about to give them with yes no option.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import errno
import os
import smtplib
import sys
from email.mime.text import MIMEText

import MySQLdb

import utility.log as log
from utility.repoutil import pull

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

class ScriptConfig:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Script to validate user and add him to database")
        parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                            help='Set path to config file')
        parser.add_argument('--vendor-access', action='store_true', default=False, help='If user need vendor access')
        parser.add_argument('--vendor-path', type=str, default='', help='What is vendor branch of user')
        parser.add_argument('--sdo-access', action='store_true', default=False, help='If user need sdo access')
        parser.add_argument('--sdo-path', type=str, default='', help='What is model organization of user')
        parser.add_argument('--row-id', type=str, default='', help='Row ID of user in temporary db')
        parser.add_argument('--user-email', type=str, default='', help='Email of user')
        self.args, extra_args = parser.parse_known_args()
        self.defaults = [parser.get_default(key) for key in self.args.__dict__.keys()]

    def get_args_list(self):
        args_dict = {}
        keys = [key for key in self.args.__dict__.keys()]
        types = [type(value).__name__ for value in self.args.__dict__.values()]

        i = 0
        for key in keys:
            args_dict[key] = dict(type=types[i], default=self.defaults[i])
            i += 1
        return args_dict

USE_LOGGER = False


def query_yes_no(question, default=None):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def query_create(question, yang_models, LOGGER):
    """Ask a path like question via raw_input() and return their answer.

    "question" is a string that is presented to the user.

    The return value is path that should be added to database.
    """

    while True:
        sys.stdout.write(question)
        choice = input().lower()

        if choice.startswith('/') and len(choice) > 1:
            choice = choice[1:]
        if choice.endswith('/'):
            choice = choice[:-1]

        if choice == '/':
            choice_without_last = '/'
        else:
            if len(choice.split('/')) > 1:
                choice_without_last = '/'.join(choice.split('/')[:-1])
            else:
                choice_without_last = choice

        if os.path.isdir(yang_models + '/' + choice):
            return choice
        else:
            local_print('Path ' + choice_without_last + ' does not exist.', LOGGER)
            create = query_yes_no('would you like to create path ' + choice)
            if create:
                try:
                    os.makedirs(choice)
                except OSError as e:
                    # be happy if someone already created the path
                    if e.errno != errno.EEXIST:
                        raise
                return choice


def connect(dbHost, dbName, dbUser, dbPass, LOGGER):
    try:
        db = MySQLdb.connect(host=dbHost, db=dbName, user=dbUser, passwd=dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        cursor.execute("SELECT * FROM users_temp")
        data = cursor.fetchall()
        db.close()

        return data
    except MySQLdb.MySQLError as err:
        local_print("Cannot connect to database. MySQL error: " + str(err), LOGGER)


def delete(dbHost, dbName, dbPass, dbUser, row_id, LOGGER):
    try:
        db = MySQLdb.connect(host=dbHost, db=dbName, user=dbUser, passwd=dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.
        cursor.execute("""DELETE FROM users_temp WHERE Id=%s LIMIT 1""", (row_id, ))
        db.commit()
        db.close()
        local_print('User ID: {} has been removed from users_temp table'.format(row_id), LOGGER)
    except MySQLdb.MySQLError as err:
        local_print("Cannot connect to database. MySQL error: " + str(err), LOGGER)


def copy(dbHost, dbName, dbPass, dbUser, row_id, vendor_path, sdo_path, LOGGER):
    try:
        db = MySQLdb.connect(host=dbHost, db=dbName, user=dbUser, passwd=dbPass)
        # prepare a cursor object using cursor() method
        cursor = db.cursor()
        # execute SQL query using execute() method.

        cursor.execute("""UPDATE users_temp SET AccessRightsVendor=%s, AccessRightsSdo=%s WHERE Id=%s""",
                       (vendor_path, sdo_path, str(row_id), ))
        cursor.execute("""INSERT INTO users(Username, Password, Email, ModelsProvider, FirstName, LastName,
                          AccessRightsVendor, AccessRightsSdo) SELECT Username, Password, Email, ModelsProvider,
                          FirstName, LastName, AccessRightsVendor, AccessRightsSdo FROM users_temp WHERE Id=%s""",
                       (str(row_id), ))
        db.commit()
        db.close()
        local_print('User ID: {} has been copied to the users table'.format(row_id), LOGGER)
    except MySQLdb.MySQLError as err:
        local_print("Cannot connect to database. MySQL error: " + str(err), LOGGER)


def send_email(to, vendor, sdo, email_from):
    msg = MIMEText('Your rights were granted ')
    msg['Subject'] = 'Access rights granted for vendor path ' + vendor + ' and organization for sdo ' + sdo
    msg['From'] = email_from
    msg['To'] = to

    s = smtplib.SMTP('localhost')
    s.sendmail(email_from, to, msg.as_string())
    s.quit()


def local_print(text, LOGGER):
    if USE_LOGGER:
        LOGGER.info(text)
    else:
        print(text)


def create(sdo_path, vendor_path, dbHost, dbName, dbPass, dbUser, row_id, LOGGER, config, user_email, email_from):
    if sdo_path is None:
        sdo_path = ''
    if vendor_path is None:
        vendor_path = ''
    copy(dbHost, dbName, dbPass, dbUser, row_id, vendor_path, sdo_path, LOGGER)
    delete(dbHost, dbName, dbPass, dbUser, row_id, LOGGER)
    send_email(user_email, repr(vendor_path), repr(sdo_path), email_from)


def main(scriptConf=None):
    if scriptConf is None:
        scriptConf = ScriptConfig()
    args = scriptConf.args
    vendor_access = args.vendor_access
    vendor_path = args.vendor_path
    sdo_access = args.sdo_access
    sdo_path = args.sdo_path
    row_id = args.row_id
    user_email = args.user_email

    config_path = args.config_path

    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    global USE_LOGGER
    if vendor_access is False:
        USE_LOGGER = False
    else:
        USE_LOGGER = True
    LOGGER = log.get_logger('validate', log_directory + '/user-validation.log')
    email_from = config.get('Message-Section', 'email-from')
    dbHost = config.get('DB-Section', 'host')
    dbName = config.get('DB-Section', 'name-users')
    dbUser = config.get('DB-Section', 'user')
    dbPass = config.get('Secrets-Section', 'mysql-password')
    yang_models = config.get('Directory-Section', 'yang-models-dir')
    dbData = connect(dbHost, dbName, dbUser, dbPass, LOGGER)
    pull(yang_models)
    if (vendor_access and vendor_path) or (sdo_access and sdo_path):
        create(sdo_path, vendor_path, dbHost, dbName, dbPass, dbUser, row_id, LOGGER, config, user_email, email_from)
        local_print('User ID: {} has been validated based on arguments'.format(row_id), LOGGER)
    else:
        vendor_path = None
        sdo_path = None
        for row in dbData:
            while True:
                local_print('The user ' + row[5] + ' ' + row[6] + ' (' + row[1] + ')' + ' is from organization ' + row[4],
                            LOGGER)
                vendor_access = query_yes_no('Do they need vendor access?')
                if vendor_access:
                    vendor_path = query_create('What is their vendor branch ', yang_models, LOGGER)
                sdo_access = query_yes_no('Do they need sdo (model) access?')
                if sdo_access:
                    sdo_path = query_create('What is their model organization ', yang_models, LOGGER)
                want_to_create = False
                if sdo_path or vendor_path:
                    want_to_create = query_yes_no('Do you want to create user ' + row[5] + ' ' + row[6] + ' (' + row[1]
                                                + ')' + ' from organization ' + row[4] + ' with path for vendor '
                                                + repr(vendor_path) + ' and organization for sdo ' + repr(sdo_path))
                if want_to_create:
                    create(sdo_path, vendor_path, dbHost, dbName, dbPass, dbUser, row[0], LOGGER, config, row[3], email_from)
                    break
                else:
                    local_print('Skipping user ' + row[5] + ' ' + row[6] + ' (' + row[1] + ')' + ' from organization ' + row[4]
                        + ' has no path set.', LOGGER)
                    if query_yes_no('Would you like to delete this user from temporary database?'):
                        delete(dbHost, dbName, dbPass, dbUser, row[0], LOGGER)
                    break

if __name__ == "__main__":
    main()
