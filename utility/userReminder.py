import sys
from datetime import datetime

import MySQLdb

from utility import messageFactory

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


class UserReminder:

    def __init__(self):
        self.__mf = messageFactory.MessageFactory()
        self.config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(self.config_path)
        self.dbHost = config.get('DB-Section', 'host')
        self.dbName = config.get('DB-Section', 'name-users')
        self.dbUser = config.get('DB-Section', 'user')
        self.dbPass = config.get('Secrets-Section', 'mysql-password')
        self.month = datetime.now().date().month
        self.day = datetime.now().date().day

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
            db = MySQLdb.connect(host=self.dbHost, db=self.dbName, user=self.dbUser, passwd=self.dbPass)
            # prepare a cursor object using cursor() method
            cursor = db.cursor()
            cursor.execute("""SELECT * FROM `users`""")
            data = cursor.fetchall()

            for x in data:
                ret_text += f'\n{str(x[1]):<25}{str(x[5]):<20}{str(x[6]):<20}{str(x[7]):<20}{str(x[8]):<20}{str(x[4]):<30}{str(x[3]):<30}'
            db.close()
        except MySQLdb.MySQLError as err:
            if err.args[0] != 1049:
                db.close()
        ret_text += '\n\n\nusers_temp table'
        ret_text += f'\n{str("user"):<25}{str("name"):<20}{str("surname"):<20}{str("organization"):<30}{str("email"):<30}'
        try:
            db = MySQLdb.connect(host=self.dbHost, db=self.dbName, user=self.dbUser, passwd=self.dbPass)
            # prepare a cursor object using cursor() method
            cursor = db.cursor()
            cursor.execute("""SELECT * FROM `users_temp`""")
            data = cursor.fetchall()

            for x in data:
                ret_text += f'\n{str(x[1]):<25}{str(x[5]):<20}{str(x[6]):<20}{str(x[4]):<30}{str(x[3]):<30}'
            db.close()
        except MySQLdb.MySQLError as err:
            if err.args[0] != 1049:
                db.close()
        return ret_text


if __name__ == '__main__':
    ur = UserReminder()
    if ur.check_date():
        ur.send_message()
