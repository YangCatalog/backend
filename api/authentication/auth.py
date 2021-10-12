import base64
import hashlib
import sys

import requests
from flask import current_app
from flask_httpauth import HTTPBasicAuth
from OpenSSL.crypto import FILETYPE_PEM, X509, load_publickey, verify
from redis import RedisError

from utility.redisUsersConnection import RedisUsersConnection

auth = HTTPBasicAuth()
users = None


@auth.hash_password
def hash_pw(password: str):
    """Hash the password

    Arguments:
        :param password     (str) password provided via API
        :return hashed password
    """
    if sys.version_info >= (3, 4):
        password = password.encode(encoding='utf-8', errors='strict')
    return hashlib.sha256(password).hexdigest()


@auth.get_password
def get_password(username: str):
    """Get password out of database

    Arguments:
        :param username     (str) username privided via API
        :return hashed password from database
    """
    try:
        return users.get_field(username, 'password').encode()
    except RedisError as err:
        current_app.logger.error('Cannot connect to database. Redis error: {}'.format(err))
        return None


def check_authorized(signature: str, payload: str):
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
    verify(certificate, base64.b64decode(signature), payload, str('SHA1'))
