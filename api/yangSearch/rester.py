# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
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

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import requests

REST_TIMEOUT = 300


class RestException(Exception):

    def __init__(self, msg, rcode):
        super(RestException, self).__init__(msg)
        self._rcode = rcode

    def get_response_code(self):
        return self._rcode


class Rester(object):
    __timeout = REST_TIMEOUT

    def __init__(self, base, username=None, password=None, timeout=REST_TIMEOUT):
        self.__base = base
        self.__username = username
        self.__password = password
        self.__timeout = timeout

    @staticmethod
    def __assert_response(resp, msg):
        if resp.status_code > 299:
            raise RestException("Failed to {}: {}".format(
                msg, resp.text), resp.status_code)

    def get(self, path, want_json=True):
        url = self.__base

        url += path

        auth = ()
        if self.__username is not None and self.__password is not None:
            auth = (self.__username, self.__password)

        headers = {}
        if want_json:
            headers['Accept'] = 'application/json'

        resp = requests.get(url, auth=auth, headers=headers,
                            timeout=self.__timeout)
        Rester.__assert_response(
            resp, "get {} from {}".format(path, self.__base))

        if want_json:
            return resp.json()
        else:
            return resp.text
