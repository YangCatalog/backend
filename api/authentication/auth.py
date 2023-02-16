from flask.globals import current_app
from flask_httpauth import HTTPBasicAuth
from redis import RedisError

from redisConnections.redis_users_connection import RedisUsersConnection
from utility.util import hash_pw

auth = HTTPBasicAuth()
users: RedisUsersConnection


@auth.hash_password
def hash_pw_bytes(password: str) -> bytes:
    return hash_pw(password).encode()


@auth.get_password
def get_password(username: str) -> bytes:
    """Get password out of database

    Arguments:
        :param username     (str) username privided via API
        :return hashed password from database
    """
    try:
        user_id = users.id_by_username(username)  # noqa
        if users.is_approved(user_id):  # noqa
            return users.get_field(user_id, 'password').encode()  # noqa
    except RedisError as err:
        current_app.logger.error(f'Cannot connect to database. Redis error: {err}')
    return b''
