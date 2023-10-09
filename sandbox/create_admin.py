from redisConnections.redis_users_connection import RedisUsersConnection
from utility.create_config import create_config
from utility.util import hash_pw


def main():
    users = RedisUsersConnection()

    if users.id_by_username('admin'):
        print('Admin user already exists.')
        exit(0)

    # Getting confd-credentials from yangcatalog config
    config = create_config()
    credentials = config.get('Secrets-Section', 'confd-credentials', fallback='admin admin')

    if credentials == 'admin admin':
        raise ValueError('couldnt find confd-credentials in given config file')

    username, password = credentials.strip('"').split()

    # Creating approved admin user
    user_id = users.create(
        temp=False,
        username=username,
        password=hash_pw(password),
        first_name='admin',
        last_name='admin',
        email='patrik.provaznik@pantheon.tech',
        models_provider='IETF',
        access_rights_sdo='/',
        access_rights_vendor='/',
    )

    print(f'Created user with id={user_id}')
    print(users.get_all_fields(user_id))


if __name__ == '__main__':
    main()
