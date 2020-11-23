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

"""
This class serves to create integrity of yang files.
It stores all the missing modules that are not in
the directory and are in xml file or modules that
have incorrect namespace, or modules with missing
revision or missing submodules or even if we have
extra files in the vendor directory - meaning that
we have yang files in the directory that are not
mentioned in capability xml file and/or are not
included or imported by some module.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import fnmatch
import glob
import os

import time


def find_missing_hello(directory, pattern):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                if not any(".xml" in name for name in files):
                    yield root


class Statistics:
    useless_modules = {}
    missing_modules = {}
    missing_submodules = {}
    missing_revision = {}
    missing_wrong_namespaces = {}
    unique_modules_per_vendor = set()
    os = {}

    def __init__(self, path):
        Statistics.missing_modules[path] = set()
        Statistics.missing_submodules[path] = set()
        Statistics.missing_wrong_namespaces[path] = set()
        Statistics.missing_revision[path] = set()
        folder = path.split('/')
        os_type = '/'.join(path.split('/')[:-2])
        folder.remove(path.split('/')[-1])
        folder = '/'.join(folder)
        if os_type not in Statistics.os:
            Statistics.os[os_type] = set()
        if folder not in Statistics.useless_modules:
            Statistics.useless_modules[folder] = glob.glob(folder + '/*.yang')

    @staticmethod
    def add_platform(os_type, platform):
        Statistics.os[os_type] = platform

    @staticmethod
    def add_unique(modules_revision):
        Statistics.unique_modules_per_vendor.update(set(modules_revision))

    @staticmethod
    def remove_one(key, value):
        if key + '/' + value in Statistics.useless_modules[key]:
            Statistics.useless_modules[key].remove(key + '/' + value)

    @staticmethod
    def dumps(file, yang_models):
        file.write('<!DOCTYPE html><html><body> <ul>'
                   '<li>Generated on {}</li>'
                   '</ul><h1>Yangcatalog statistics</h1>'
                   .format(time.strftime("%d/%m/%y")))
        file.write('<h3>YANG modules in directory but not present in any NETCONF hello message in that directory:</h3>')
        for key in Statistics.useless_modules:
            if len(Statistics.useless_modules[key]) > 0:
                file.write('<h5>' + key + ':</h5>')
                file.write('<p>' + ', '.join([value.split('/')[-1] for value in Statistics.useless_modules[key]])
                           + '</p>')
        file.write('<h3>YANG modules in NETCONF hello messages for a directory but the YANG modules is not present'
                   + ' in that directory:</h3>')
        for key in Statistics.missing_modules:
            file.write('<h5>' + key + ':</h5>')
            file.write('<p>' + ', '.join([value.split('/')[-1] for value in Statistics.missing_modules[key]]) + '</p>')
        file.write('<h3>YANG modules in NETCONF hello messages for a directory but their'
                   + ' submodules are missing:</h3>')
        for key in Statistics.missing_submodules:
            file.write('<h5>' + key + ':</h5>')
            file.write('<p>' + ', '.join([value.split('/')[-1] for value in Statistics.missing_submodules[key]])
                       + '</p>')
        file.write('<h3>YANG modules in NETCONF hello messages for a directory but their'
                   + ' revision date is missing:</h3>')
        for key in Statistics.missing_revision:
            file.write('<h5>' + key + ':</h5>')
            file.write('<p>' + ', '.join([value.split('/')[-1] for value in Statistics.missing_revision[key]]) + '</p>')

        file.write('<h3>YANG modules in NETCONF hello messages for a directory but their'
                   + ' namespace is wrong or missing:</h3>')
        for key in Statistics.missing_wrong_namespaces:
            file.write('<h5>' + key + ':</h5>')
            for value in Statistics.missing_wrong_namespaces[key]:
                file.write('<p>' + str(value) + '</p>')
        missing = []
        my_files = find_missing_hello(yang_models + '/vendor/', '*.yang')
        for name in set(my_files):
            if '.incompatible' not in name and 'MIBS' not in name:
                missing.append(name)
        missing = ', '.join(missing).replace(yang_models, '')
        file.write('<h3>Folders with yang files but missing hello message inside of file:</h3><p>' + missing + '</p>')
        file.write('</body></html>')

    @staticmethod
    def add_submodule(path, value):
        if len(value) > 0:
            Statistics.missing_submodules[path].update(value)

    @staticmethod
    def add_module(path, value):
        if len(value) > 0:
            Statistics.missing_modules[path].update(value)

    @staticmethod
    def add_namespace(path, value):
        if value:
            Statistics.missing_wrong_namespaces[path] = value

    @staticmethod
    def add_revision(path, value):
        if value:
            Statistics.missing_revision[path] = value
