"""Reset the password of any user in the redis database"""

from argparse import ArgumentParser

from redisConnections.redis_users_connection import RedisUsersConnection
from utility.util import hash_pw


def main():
    parser = ArgumentParser()
    parser.add_argument('user', type=str, help='Name of the user who\'s password to reset.')
    parser.add_argument('new_password', type=str, help='The new password.')
    args = parser.parse_args()

    users = RedisUsersConnection()
    user_id = users.id_by_username(args.user)
    hashed_pw = hash_pw(args.new_password)
    users.set_field(user_id, 'password', hashed_pw)


if __name__ == '__main__':
    main()
