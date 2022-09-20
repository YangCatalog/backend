import os
from redisConnections.redis_users_connection import RedisUsersConnection


if __name__ == '__main__':
    users = RedisUsersConnection()

    admin_id = users.id_by_username('admin')
    if admin_id != b'':
        print("Admin user already exists.")
        exit(0)

    # Getting confd-credentials from yangcatalog config
    confd_creds = None
    with open(os.environ['YANGCATALOG_CONFIG_PATH'], 'r') as f:
        for line in f.readlines():
            if 'confd-credentials' in line:
                confd_creds = line.removeprefix(
                    'confd-credentials=').strip('" \n')

    if confd_creds is None:
        raise ValueError('couldnt find confd-credentials in given config file')

    username, password = confd_creds.split()

    # Creating approved admin user
    user_id = users.create(False, username=username, password=password,
                           first_name='admin', last_name='admin', email='foo@bar.com',
                           models_provider='IETF', access_rights_sdo='/', access_rights_vendor='/')

    print(f'Created user with id={user_id}')
    print(users.get_all_fields(user_id))
