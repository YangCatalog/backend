import os
from utility.create_config import create_config
from redisConnections.redis_users_connection import RedisUsersConnection


def main():
    users = RedisUsersConnection()

    admin_id = users.id_by_username('admin')
    if admin_id != b'':
        print('Admin user already exists.')
        exit(0)

    # Getting confd-credentials from yangcatalog config
    config = create_config()
    credentials = config.get('Secrets-Section', 'confd-credentials',
                             fallback='user password')

    if credentials == "user password":
        raise ValueError('couldnt find confd-credentials in given config file')

    username, password = credentials.strip('"').split()

    # Creating approved admin user
    user_id = users.create(False, username=username, password=password,
                           first_name='admin', last_name='admin', email='foo@bar.com',
                           models_provider='IETF', access_rights_sdo='/', access_rights_vendor='/')

    print(f'Created user with id={user_id}')
    print(users.get_all_fields(user_id))


if __name__ == '__main__':
    main()
