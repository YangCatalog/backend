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


    def send_message(self):
        user_stats = self.__produce_users_info()
        self.__mf.send_user_reminder_message(user_stats)

    def __produce_users_info(self):
        ret_text = '<h3>approved users</h3>'
        ret_text += '\n<table style="width:100%"><tr>'
        for header in ['user', 'name', 'surname', 'sdo_rights', 'vendor_rights', 'organization', 'email']:
            ret_text += '<th>{}</th>'.format(header)
        ret_text += '</tr>'
        try:
            for id in self.users.get_all('approved'):
                fields = self.users.get_all_fields(id)
                ret_text += '<tr>'
                for key in ['username', 'first-name', 'last-name', 'access-rights-sdo', 'access-rights-vendor', 'modles-provider', 'email']:
                    ret_text += '<td>{}</td>'.format(str(fields.get(key)))
                ret_text += '</tr>'
        except RedisError:
            pass
        ret_text += '</table><br>'
        ret_text += '<h3>users pending approval</h3>'
        ret_text += '<table style="width:100%"><tr>'
        for header in ['user', 'name', 'surname', 'organization', 'email']:
            ret_text += '<th>{}</th>'.format(header)
        ret_text += '<tr>'
        try:
            for id in self.users.get_all('temp'):
                fields = self.users.get_all_fields(id)
                ret_text += '<tr>'
                for key in ['username', 'first-name', 'last-name', 'modles-provider', 'email']:
                    ret_text += '<td>{}</td>'.format(str(fields.get(key)))
                ret_text += '</tr>'
        except RedisError:
            pass
        ret_text += '</table>'
        return ret_text


if __name__ == '__main__':
    ur = UserReminder()
    ur.send_message()
