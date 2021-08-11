import sys
from datetime import datetime
from utility.util import create_config

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import DeferredReflection
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import SQLAlchemyError

from utility import messageFactory
from api.models import Base, User, TempUser


class UserReminder:

    def __init__(self):
        self.__mf = messageFactory.MessageFactory()
        config = create_config()
        self.dbHost = config.get('DB-Section', 'host')
        self.dbName = config.get('DB-Section', 'name-users')
        self.dbUser = config.get('DB-Section', 'user')
        self.dbPass = config.get('Secrets-Section', 'mysql-password')
        self.month = datetime.now().date().month
        self.day = datetime.now().date().day
        uri = URL.create('mysql', username=self.dbUser, password=self.dbPass, host=self.dbHost, database=self.dbName)
        self.engine = create_engine(uri, future=True)


    def check_date(self):
        if (self.month == 3 or self.month == 9) and (self.day == 1):
            return True
        else:
            return False

    def send_message(self):
        user_stats = self.__produce_users_info()
        self.__mf.send_user_reminder_message(user_stats)

    def __produce_users_info(self):
        ret_text = 'users table'
        ret_text += f'\n{str("user"):<25}{str("name"):<20}{str("surname"):<20}{str("sdo_rights"):<20}{str("vendor_rights"):<20}{str("organization"):<30}{str("email"):<30}'
        try:
            with Session(self.engine) as session:
                users = session.query(User).all()
                for user in users:
                    ret_text += (f'\n{str(user.Username):<25}{str(user.FirstName):<20}{str(user.LastName):<20}{str(user.AccessRightsSdo):<20}'
                                    f'{str(user.AccessRightsVendor):<20}{str(user.ModelsProvider):<30}{str(user.Email):<30}')
        except SQLAlchemyError as err:
            pass
        ret_text += '\n\n\nusers_temp table'
        ret_text += f'\n{str("user"):<25}{str("name"):<20}{str("surname"):<20}{str("organization"):<30}{str("email"):<30}'
        try:
            with Session(self.engine) as session:
                users = session.query(TempUser).all()
                for user in users:
                    ret_text += f'\n{str(user.Username):<25}{str(user.FirstName):<20}{str(user.LastName):<20}{str(user.ModelsProvider):<30}{str(user.Email):<30}'
        except SQLAlchemyError as err:
            pass
        return ret_text


if __name__ == '__main__':
    ur = UserReminder()
    Base.metadata.create_all(ur.engine)
    DeferredReflection.prepare(ur.engine)
    if ur.check_date():
        ur.send_message()
