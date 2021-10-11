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

from redis import Redis

class ResisUsersConnection:

    _universal_fields = ['username', 'password', 'email', 'models.provider', 'first.name', 'last.name', 'registration.datetime']
    _temp_fields = ['motivation']
    _appr_fields = ['access.rights:sdo', 'access.rights:vendor']

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def exists(self, username: str) -> bool:
        return self.is_approved(username) or self.is_temp(username)

    def get_field(self, username: str, field: str) -> str:
        self.redis.get('{}:{}'.format(username, field))

    def set_field(self, username: str, field: str, value: str) -> bool:
        self.redis.set('{}:{}'.format(username, field), value)

    def is_approved(self, username: str) -> bool:
        return self.redis.sismember('approved', username)

    def is_temp(self, username: str) -> bool:
        return self.redis.sismember('temp', username)
    
    def approve_user(self, username: str, access_rights_sdo: str, access_rights_vendor: str):
        self.redis.srem('temp', username)
        self.set_field('access.rights:sdo', access_rights_sdo)
        self.set_field('access.rights:vendor', access_rights_vendor)
        self.redis.delete('{}:{}'.format(username, 'motivation'))
        self.redis.sadd('approved', username)

    def get_all_fields(self, username: str) -> dict:
        r = {}
        for field in self._universal_fields:
            r[field.replace('.', '-')] = self.get_field(username, field)
        if self.is_temp(username):
            for field in self._temp_fields:
                r[field.replace('.', '-')] = self.get_field(username, field)
        elif self.is_approved(username):
            for field in self._appr_fields:
                r[field.replace('.', '-').replace(':', '-')] = self.get_field(username, field)


