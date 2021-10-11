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

from redis import Redis

class RedisUsersConnection:

    _universal_fields = ['username', 'password', 'email', 'models-provider', 'first-name', 'last-name', 'registration-datetime']
    _temp_fields = ['motivation']
    _appr_fields = ['access-rights-sdo', 'access-rights-vendor']

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def exists(self, id: str) -> bool:
        return self.redis.sismember('users', id)

    def username_exists(self, username: str) -> bool:
        return self.redis.hexists('usernames', username)

    def get_field(self, id: str, field: str) -> str:
        self.redis.get('{}:{}'.format(id, field)).encode()

    def set_field(self, id: str, field: str, value: str) -> bool:
        self.redis.set('{}:{}'.format(id, field), value)

    def delete_field(self, id: str, field: str):
        self.redis.delete('{}:{}'.format(id, field))

    def is_approved(self, id: str) -> bool:
        return self.redis.sismember('approved', id)

    def is_temp(self, id: str) -> bool:
        return self.redis.sismember('temp', id)

    def create(self, temp: bool, **kwargs):
        id = self.redis.incr('new-id')
        self.redis.sadd('users', id)
        self.redis.hset('usernames', kwargs['username'], id)
        kwargs['registration_datetime'] = str(datetime.datetime.utcnow())
        for field in self._universal_fields:
            self.set_field(id, field, kwargs[field.replace('-', '_')])
        self.redis.sadd('temp' if temp else 'approved', id)
        if temp:
            for field in self._temp_fields:
                self.set_field(id, field, kwargs[field.replace('-', '_')])
        else:
            for field in self._appr_fields:
                self.set_field(id, field, kwargs[field.replace('-', '_')])

    def delete(self, id: str, temp: bool):
        self.redis.hdel('usernames', self.get_field(id, 'username'))
        for field in self._universal_fields:
            self.delete_field(id, field)
        self.redis.srem('temp' if temp else 'approved', id)
        if temp:
            for field in self._temp_fields:
                self.delete_field(id, field)
        else:
            for field in self._appr_fields:
                self.delete_field(id, field)
        self.redis.srem('users', id)

    def approve(self, id: str, access_rights_sdo: str, access_rights_vendor: str):
        self.redis.srem('temp', id)
        self.set_field('access-rights-sdo', access_rights_sdo)
        self.set_field('access-rights-vendor', access_rights_vendor)
        self.redis.delete('{}:{}'.format(id, 'motivation'))
        self.redis.sadd('approved', id)

    def get_all(self, status) -> set:
        return self.redis.smembers(status)

    def get_all_fields(self, id: str) -> dict:
        r = {}
        for field in self._universal_fields:
            r[field] = self.get_field(id, field)
        if self.is_temp(id):
            for field in self._temp_fields:
                r[field] = self.get_field(id, field)
        elif self.is_approved(id):
            for field in self._appr_fields:
                r[field] = self.get_field(id, field)
