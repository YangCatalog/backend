import base64

import requests
from flask.globals import current_app
from flask_httpauth import HTTPBasicAuth
from OpenSSL.crypto import FILETYPE_PEM, X509, load_publickey, verify
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


def check_authorized(signature: str, payload: str) -> None:
    """Convert the PEM encoded public key to a format palatable for pyOpenSSL,
    then verify the signature

    Arguments:
        :param signature    (str) Signature returned by sign function
        :param payload      (str) String that is encoded
    """
    response = requests.get('https://api.travis-ci.com/config', timeout=10.0)
    response.raise_for_status()
    public_key = response.json()['config']['notifications']['webhook']['public_key']
    pkey_public_key = load_publickey(FILETYPE_PEM, public_key)
    certificate = X509()
    certificate.set_pubkey(pkey_public_key)
    verify(certificate, base64.b64decode(signature), payload, 'SHA1')
