# Copyright The IETF Trust 2022, All Rights Reserved
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

"""basic-info output plugin
Takes the name, revision, organization, namespace, and belongs-to, and dumps them in JSON format.
"""

import json

from pyang import plugin


def pyang_plugin_init():
    plugin.register_plugin(BasicInfoPlugin())


class BasicInfoPlugin(plugin.PyangPlugin):
    FIELDS = ('revision', 'organization', 'belongs-to', 'namespace',)

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['basic-info'] = self

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        for module in modules:
            output = {'name': module.arg}
            for field in self.FIELDS:
                statement = module.search_one(field)
                if statement is not None:
                    output[field] = statement.arg
            fd.write(json.dumps(output))
