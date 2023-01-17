from datetime import datetime

from redisConnections.redis_users_connection import RedisUsersConnection
from utility import message_factory


class UserReminder:
    """Class for sending a message reminding admins to review approved and pending users."""

    def __init__(self):
        self._mf = message_factory.MessageFactory()
        self.month = datetime.now().date().month
        self.day = datetime.now().date().day
        self.users = RedisUsersConnection()

    def send_message(self):
        self._mf.send_user_reminder_message(self._produce_users_info())

    def _produce_users_info(self):
        return {
            'approved': [self.users.get_all_fields(id) for id in self.users.get_all('approved')],
            'temp': [self.users.get_all_fields(id) for id in self.users.get_all('temp')],
        }


if __name__ == '__main__':
    UserReminder().send_message()
