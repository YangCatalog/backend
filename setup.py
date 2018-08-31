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
__copyright__ = "Copyright 2018 Cisco and its affiliates"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

from setuptools import setup, find_packages

setup(
    name='yang',
    version='',
    packages=find_packages(),
    url='',
    license='Apache License, Version 2.0',
    author='Miroslav Kovac',
    author_email='miroslav.kovac@pantheon.tech',
    description='',
    install_requires=['numpy;python_version<"3.4"',  'pytest;python_version<"3.4"',
                      'flask;python_version<"3.4"', 'Crypto;python_version<"3.4"', 'pika;python_version<"3.4"',
                      'urllib3;python_version<"3.4"', 'pyOpenSSL;python_version<"3.4"', 'flask-httpauth;python_version<"3.4"',
                      'configparser;python_version>"3.4"',
                      'requests', 'jinja2', 'pyang', 'gitpython', 'ciscosparkapi', 'mysqlclient', 'travispy'
                      ]
)
