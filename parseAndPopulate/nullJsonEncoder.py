# Copyright The IETF Trust 2020, All Rights Reserved
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

"""
This is for use with json.dump(s) option. It will dump json without
null values of the json. use cls option - cls=NullJsonEncoder
"""
import json

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright The IETF Trust 2020, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"


class NullJsonEncoder(json.JSONEncoder):

    def encode(self, o):
        ret_obj = self.__remove_null_dict(o)
        return super().encode(ret_obj)

    def iterencode(self, o, _one_shot=False):
        ret_obj = self.__remove_null_dict(o)
        return super().iterencode(ret_obj)

    def __remove_null_dict(self, obj):
        ret_obj = {}
        for key, val in obj.items():
            if isinstance(val, dict):
                temp_obj =  self.__remove_null_dict(val)
                if len(temp_obj) > 0:
                    ret_obj[key] = temp_obj
            elif isinstance(val, list):
                temp_obj = self.__remove_null_list(val)
                if len(temp_obj) > 0:
                    ret_obj[key] = temp_obj
            else:
                if val is not None:
                    ret_obj[key] = val
        return ret_obj

    def __remove_null_list(self, obj):
        ret_obj = []
        for val in obj:
            if isinstance(val, dict):
                temp_obj = self.__remove_null_dict(val)
                if len(temp_obj) > 0:
                    ret_obj.append(temp_obj)
            else:
                if val is not None:
                    ret_obj.append(val)
        return ret_obj
