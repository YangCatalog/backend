"""Reset the password of any user in the redis database"""

from argparse import ArgumentParser

from api.authentication.auth import hash_pw
from redisConnections.redis_users_connection import RedisUsersConnection


def main():
    parser = ArgumentParser()
    parser.add_argument('user', type=str, help='Name of the user who\'s password to reset.')
    parser.add_argument('new_password', type=str, help='The new password.')
    args = parser.parse_args()

    users = RedisUsersConnection()
    id = users.id_by_username(args.user)
    hash = hash_pw(args.new_password)
    users.set_field(id, 'password', hash.decode())


if __name__ == '__main__':
    main()
