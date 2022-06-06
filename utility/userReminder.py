from datetime import datetime

from utility import messageFactory
from utility.redisUsersConnection import RedisUsersConnection


class UserReminder:

    def __init__(self):
        self._mf = messageFactory.MessageFactory()
        self.month = datetime.now().date().month
        self.day = datetime.now().date().day
        self.users = RedisUsersConnection()


    def send_message(self):
        user_stats = self._produce_users_info()
        self._mf.send_user_reminder_message(user_stats)

    def _produce_users_info(self):
        return {
            'approved': [self.users.get_all_fields(id) for id in self.users.get_all('approved')],
            'temp': [self.users.get_all_fields(id) for id in self.users.get_all('temp')]
        }


if __name__ == '__main__':
    ur = UserReminder()
    ur.send_message()
