# Copyright The IETF Trust 2021, All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


__author__ = 'Richard Zilincik'
__copyright__ = 'Copyright The IETF Trust 2021, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'richard.zilncik@pantheon.tech'

import datetime
import typing as t
from configparser import ConfigParser

from redis import Redis

import redisConnections.data_transfer_objects as dto
import utility.log as log
from utility.create_config import create_config


class RedisUsersConnection:
    """
    A class for managing the Redis user database. Used for querying user data,
    updating user data, creating new users, deleting users, and approving
    temporary users pending approval.
    """

    _universal_fields = [
        'username',
        'password',
        'email',
        'models-provider',
        'first-name',
        'last-name',
        'registration-datetime',
    ]
    _temp_fields = ['motivation']
    _appr_fields = ['access-rights-sdo', 'access-rights-vendor']

    def __init__(self, db: t.Optional[t.Union[int, str]] = None, config: ConfigParser = create_config()):
        self._redis_host = config.get('DB-Section', 'redis-host')
        self._redis_port = int(config.get('DB-Section', 'redis-port'))
        db = db if db is not None else config.get('DB-Section', 'redis-users-db', fallback=2)
        self.redis = Redis(host=self._redis_host, port=self._redis_port, db=db)  # pyright: ignore

        self.log_directory = config.get('Directory-Section', 'logs')
        self.logger = log.get_logger('redis_users_connection', f'{self.log_directory}/redis_users_connection.log')

    def username_exists(self, username: str) -> bool:
        return self.redis.hexists('usernames', username)

    def get_field(self, user_id: t.Union[str, int], field: str) -> str:
        r = self.redis.get(f'{user_id}:{field}')
        return (r or b'').decode()

    def set_field(self, user_id: t.Union[str, int], field: str, value: str) -> bool:
        return bool(self.redis.set(f'{user_id}:{field}', value))

    def delete_field(self, user_id: t.Union[str, int], field: str) -> bool:
        return bool(self.redis.delete(f'{user_id}:{field}'))

    def is_approved(self, user_id: t.Union[str, int]) -> bool:
        return self.redis.sismember('approved', user_id)

    def is_temp(self, user_id: t.Union[str, int]) -> bool:
        return self.redis.sismember('temp', user_id)

    def id_by_username(self, username: str) -> str:
        r = self.redis.hget('usernames', username)
        return (r or b'').decode()

    def create(self, temp: bool, **kwargs) -> int:
        self.logger.info('Creating new user')
        user_id = self.redis.incr('new-id')
        self.redis.hset('usernames', kwargs['username'], user_id)
        if 'registration_datetime' not in kwargs:
            kwargs['registration_datetime'] = str(datetime.datetime.utcnow())
        for field in self._universal_fields:
            self.set_field(user_id, field, kwargs[field.replace('-', '_')])
        self.redis.sadd('temp' if temp else 'approved', user_id)
        if temp:
            for field in self._temp_fields:
                self.set_field(user_id, field, kwargs[field.replace('-', '_')])
        else:
            for field in self._appr_fields:
                self.set_field(user_id, field, kwargs[field.replace('-', '_')])
        return user_id

    def delete(self, user_id: t.Union[str, int], temp: bool):
        self.logger.info(f'Deleting user with id {user_id}')
        self.redis.hdel('usernames', self.get_field(user_id, 'username'))
        for field in self._universal_fields:
            self.delete_field(user_id, field)
        self.redis.srem('temp' if temp else 'approved', user_id)
        if temp:
            for field in self._temp_fields:
                self.delete_field(user_id, field)
        else:
            for field in self._appr_fields:
                self.delete_field(user_id, field)

    def approve(self, user_id: t.Union[str, int], access_rights_sdo: str, access_rights_vendor: str):
        self.logger.info(f'Approving user with id {user_id}')
        self.redis.srem('temp', user_id)
        self.set_field(user_id, 'access-rights-sdo', access_rights_sdo)
        self.set_field(user_id, 'access-rights-vendor', access_rights_vendor)
        self.redis.delete(f'{user_id}:"motivation"')
        self.redis.sadd('approved', user_id)

    def get_all(self, status: str) -> list[str]:
        return list(map(lambda user_id: user_id.decode(), self.redis.smembers(status)))

    def get_all_fields(self, user_id: t.Union[str, int]) -> t.Union[dto.TempUserFields, dto.ApprovedUserFields]:
        r = {}
        for field in self._universal_fields:
            # Remove milliseconds - should be after '.'
            if field == 'registration-datetime':
                raw_date = self.get_field(user_id, field).split('.')[0]
                r[field] = raw_date
                continue
            r[field] = self.get_field(user_id, field)
        if self.is_temp(user_id):
            for field in self._temp_fields:
                r[field] = self.get_field(user_id, field)
        elif self.is_approved(user_id):
            for field in self._appr_fields:
                r[field] = self.get_field(user_id, field)
        return r
