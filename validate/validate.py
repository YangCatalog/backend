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
from utility.create_config import create_config

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import DeferredReflection
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import SQLAlchemyError

import utility.log as log
from utility.repoutil import pull
from api.models import Base, User, TempUser


class ScriptConfig:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Script to validate user and add him to database")
        parser.add_argument('--config-path', type=str, default=os.environ['YANGCATALOG_CONFIG_PATH'],
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


def connect(engine, dbHost, dbName, dbUser, dbPass, LOGGER):
    try:
        with Session(engine) as session:
            users = session.query(TempUser).all()
            print(users)
            return users
    except SQLAlchemyError as err:
        local_print("Cannot connect to database. MySQL error: " + str(err), LOGGER)


def delete(engine, dbHost, dbName, dbPass, dbUser, row_id, LOGGER):
    try:
        with Session(engine) as session:
            session.delete(session.get(TempUser, row_id))
            session.commit()
            local_print('User ID: {} has been removed from users_temp table'.format(row_id), LOGGER)
    except SQLAlchemyError as err:
        local_print("Cannot connect to database. MySQL error: " + str(err), LOGGER)


def copy(engine, dbHost, dbName, dbPass, dbUser, row_id, vendor_path, sdo_path, LOGGER):
    try:
        with Session(engine) as session:
            user_temp = session.query(TempUser).filter_by(Id=row_id).first()
            user_temp.AccessRightsVendor = vendor_path
            user_temp.AccessRightsSdo = sdo_path
            user = User(Username=user_temp.Username, Password=user_temp.Password, Email=user_temp.Email,
                        ModelsProvider=user_temp.ModelsProvider, FirstName=user_temp.FirstName,
                        LastName=user_temp.LastName, AccessRightsVendor=user_temp.AccessRightsVendor,
                        AccessRightsSdo=user_temp.AccessRightsSdo)
            session.add(user)
            session.commit()
            local_print('User ID: {} has been copied to the users table'.format(row_id), LOGGER)
    except SQLAlchemyError as err:
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


def create(engine, sdo_path, vendor_path, dbHost, dbName, dbPass, dbUser, row_id, LOGGER, config, user_email, email_from):
    if sdo_path is None:
        sdo_path = ''
    if vendor_path is None:
        vendor_path = ''
    copy(engine, dbHost, dbName, dbPass, dbUser, row_id, vendor_path, sdo_path, LOGGER)
    delete(engine, dbHost, dbName, dbPass, dbUser, row_id, LOGGER)
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
    config = create_config(config_path)
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
    uri = URL.create('mysql', username=dbUser, password=dbPass, host=dbHost, database=dbName)
    engine = create_engine(uri, future=True)
    Base.metadata.create_all(engine)
    DeferredReflection.prepare(engine)
    users = connect(engine, dbHost, dbName, dbUser, dbPass, LOGGER)
    pull(yang_models)
    if (vendor_access and vendor_path) or (sdo_access and sdo_path):
        create(engine, sdo_path, vendor_path, dbHost, dbName, dbPass,
               dbUser, row_id, LOGGER, config, user_email, email_from)
        local_print('User ID: {} has been validated based on arguments'.format(row_id), LOGGER)
    else:
        vendor_path = None
        sdo_path = None
        for user in users:
            print(user.Id)
            while True:
                local_print('The user {} {} ({}) is from organization {}'
                            .format(user.FirstName, user.LastName, user.Username, user.ModelsProvider),
                            LOGGER)
                vendor_access = query_yes_no('Do they need vendor access?')
                if vendor_access:
                    vendor_path = query_create('What is their vendor branch ', yang_models, LOGGER)
                sdo_access = query_yes_no('Do they need sdo (model) access?')
                if sdo_access:
                    sdo_path = query_create('What is their model organization ', yang_models, LOGGER)
                want_to_create = False
                if sdo_path or vendor_path:
                    want_to_create = query_yes_no('Do you want to create user {} {} ({}) from organization {}'
                                                  ' with path for vendor {} and organization for sdo {}'
                                                  .format(user.FirstName, user.LastName, user.Username,
                                                          user.ModelsProvider, repr(vendor_path), repr(sdo_path)))
                if want_to_create:
                    create(engine, sdo_path, vendor_path, dbHost, dbName, dbPass,
                           dbUser, user.Id, LOGGER, config, user.Email, email_from)
                    break
                else:
                    local_print('Skipping user {} {} ({}) from organization {} has no path set.'
                                .format(user.FirstName, user.LastName, user.Username, user.ModelsProvider),
                                LOGGER)
                    if query_yes_no('Would you like to delete this user from temporary database?'):
                        delete(engine, dbHost, dbName, dbPass, dbUser, user.Id, LOGGER)
                    break

if __name__ == "__main__":
    main()
