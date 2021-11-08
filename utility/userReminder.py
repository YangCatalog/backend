from datetime import datetime

from redis import RedisError

from utility import messageFactory
from utility.create_config import create_config
from utility.redisUsersConnection import RedisUsersConnection


class UserReminder:

    def __init__(self):
        self.__mf = messageFactory.MessageFactory()
        self.month = datetime.now().date().month
        self.day = datetime.now().date().day
        self.users = RedisUsersConnection()


    def check_date(self):
        if (self.month == 3 or self.month == 9) and (self.day == 1):
            return True
        else:
            return False

    def send_message(self):
        user_stats = self.__produce_users_info()
        self.__mf.send_user_reminder_message(user_stats)

    def __produce_users_info(self):
        ret_text = 'approved users'
        ret_text += f'\n{str("user"):<25}{str("name"):<20}{str("surname"):<20}{str("sdo_rights"):<20}{str("vendor_rights"):<20}{str("organization"):<30}{str("email"):<30}'
        try:
            for id in self.users.get_all('approved'):
                fields = self.users.get_all_fields(id)
                ret_text += (f"\n{fields['username']:<25}{fields['first-name']:<20}{fields['last-name']:<20}{fields['access-rights-sdo']:<20}"
                             f"{fields['access-rights-vendor']:<20}{fields['models-provider']:<30}{fields['email']:<30}")
        except RedisError:
            pass
        ret_text += '\n\n\nusers pending approval'
        ret_text += f'\n{str("user"):<25}{str("name"):<20}{str("surname"):<20}{str("organization"):<30}{str("email"):<30}'
        try:
            for id in self.users.get_all('temp'):
                fields = self.users.get_all_fields(id)
                ret_text += (f"\n{fields['username']:<25}{fields['first-name']:<20}{fields['last-name']:<20}{'':<20}"
                             f"{'':<20}{fields['models-provider']:<30}{fields['email']:<30}")
        except RedisError:
            pass
        return ret_text


if __name__ == '__main__':
    ur = UserReminder()
    if ur.check_date():
        ur.send_message()
