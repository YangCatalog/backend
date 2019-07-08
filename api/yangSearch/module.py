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

import sys
if sys.version_info >= (3, 4):
    import urllib.parse as urlib
else:
    import urllib as urlib

class Module(object):
    __object_dict = {
        'name': True,
        'revision': True,
        'organization': True,
        'ietf': True,
        'namespace': True,
        'schema': True,
        'generated-from': True,
        'maturity-level': True,
        'document-name': True,
        'author-email': True,
        'reference': True,
        'module-classification': True,
        'compilation-status': True,
        'compilation-result': True,
        'prefix': True,
        'yang-version': True,
        'description': True,
        'contact': True,
        'module-type': True,
        'belongs-to': True,
        'tree-type': True,
        'yang-tree': True,
        'expires': True,
        'expired': True,
        'submodule': True,
        'dependencies': False,
        'dependents': False,
        'semantic-version': True,
        'derived-semantic-version': True,
        'implementations': True
    }

    __seen_modules = {}

    def __init__(self, rest, name, revision, organization, attrs={}):
        self.__rester = rest
        self.__dict = {}

        for key, val in Module.__object_dict.items():
            if key in attrs:
                self.__dict[key] = attrs[key]
            else:
                self.__dict[key] = None

        if len(attrs) > 0:
            self.__initialized = True
        else:
            self.__initialized = False

        self.__dict['name'] = name
        if revision == '':
            revision = '1970-01-01'

        self.__dict['revision'] = revision
        self.__dict['organization'] = organization

    @staticmethod
    def module_factory(rest, name, revision, organization, override=False, attrs={}):
        mod_sig = '{}@{}/{}'.format(name, revision, organization)

        create_new = False
        if mod_sig not in Module.__seen_modules:
            create_new = True
        elif override:
            Module.__seen_modules[mod_sig] = None
            create_new = True

        if create_new:
            Module.__seen_modules[mod_sig] = Module(
                rest, name, revision, organization, attrs)

        return Module.__seen_modules[mod_sig]

    def __fetch(self):
        if self.__initialized:
            return

        result = self.__rester.get('/search/modules/{},{},{}'.format(urlib.quote(
            self.__dict['name']), urlib.quote(self.__dict['revision']), urlib.quote(self.__dict['organization'])))
        for key, value in result['module'][0].items():
            if key in Module.__object_dict:
                self.__dict[key] = value
            else:
                raise Exception(
                    'Failed to set key {}: not defined'.format(key))

        self.__initialized = True

    def get(self, field):
        if field not in Module.__object_dict:
            raise Exception("Field {} does not exist; please specify one of:\n\n{}".format(
                field, "\n".join(list(Module.__object_dict.keys()))))

        if not self.__initialized:
            self.__fetch()

        return self.__dict[field]

    def get_name(self):
        return self.__dict['name']

    def get_revision(self):
        return self.__dict['revision']

    def get_organization(self):
        return self.__dict['organization']

    def get_rester(self):
        return self.__rester

    def get_mod_sig(self):
        return '{}@{}/{}'.format(self.__dict['name'], self.__dict['revision'], self.__dict['organization'])

    def to_dict(self):
        if not self.__initialized:
            self.__fetch()

        arr = {}
        for key, value in Module.__object_dict.items():
            arr[key] = self.__dict[key]

        return arr

    def __del__(self):
        mod_sig = self.get_mod_sig()
        if mod_sig in Module.__seen_modules:
            del Module.__seen_modules[mod_sig]
