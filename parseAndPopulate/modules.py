# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
#
# Licensed under the Apache Licparse_allense, Version 2.0 (the "License");
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
This is a class of a single module to parse all the basic
metadata we can get out of the module. From this class parse_all
method is called which will call all the other methods that
will get the rest of the metadata.
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import errno
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

import statistic.statistics as stats
from parseAndPopulate.parseException import ParseException
from utility import log, yangParser
from utility.util import find_first_file

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser

IETF_RFC_MAP = {
    "iana-crypt-hash@2014-08-06.yang": "NETMOD",
    "iana-if-type@2014-05-08.yang": "NETMOD",
    "ietf-complex-types@2011-03-15.yang": "N/A",
    "ietf-inet-types@2010-09-24.yang": "NETMOD",
    "ietf-inet-types@2013-07-15.yang": "NETMOD",
    "ietf-interfaces@2014-05-08.yang": "NETMOD",
    "ietf-ip@2014-06-16.yang": "NETMOD",
    "ietf-ipfix-psamp@2012-09-05.yang": "IPFIX",
    "ietf-ipv4-unicast-routing@2016-11-04.yang": "NETMOD",
    "ietf-ipv6-router-advertisements@2016-11-04.yang": "NETMOD",
    "ietf-ipv6-unicast-routing@2016-11-04.yang": "NETMOD",
    "ietf-key-chain@2017-06-15.yang": "RTGWG",
    "ietf-l3vpn-svc@2017-01-27.yang": "L3SM",
    "ietf-lmap-common@2017-08-08.yang": "LMAP",
    "ietf-lmap-control@2017-08-08.yang": "LMAP",
    "ietf-lmap-report@2017-08-08.yang": "LMAP",
    "ietf-netconf-acm@2012-02-22.yang": "NETCONF",
    "ietf-netconf-monitoring@2010-10-04.yang": "NETCONF",
    "ietf-netconf-notifications@2012-02-06.yang": "NETCONF",
    "ietf-netconf-partial-lock@2009-10-19.yang": "NETCONF",
    "ietf-netconf-time@2016-01-26.yang": "N/A",
    "ietf-netconf-with-defaults@2011-06-01.yang": "NETCONF",
    "ietf-netconf@2011-06-01.yang": "NETCONF",
    "ietf-restconf-monitoring@2017-01-26.yang": "NETCONF",
    "ietf-restconf@2017-01-26.yang": "NETCONF",
    "ietf-routing@2016-11-04.yang": "NETMOD",
    "ietf-snmp-common@2014-12-10.yang": "NETMOD",
    "ietf-snmp-community@2014-12-10.yang": "NETMOD",
    "ietf-snmp-engine@2014-12-10.yang": "NETMOD",
    "ietf-snmp-notification@2014-12-10.yang": "NETMOD",
    "ietf-snmp-proxy@2014-12-10.yang": "NETMOD",
    "ietf-snmp-ssh@2014-12-10.yang": "NETMOD",
    "ietf-snmp-target@2014-12-10.yang": "NETMOD",
    "ietf-snmp-tls@2014-12-10.yang": "NETMOD",
    "ietf-snmp-tsm@2014-12-10.yang": "NETMOD",
    "ietf-snmp-usm@2014-12-10.yang": "NETMOD",
    "ietf-snmp-vacm@2014-12-10.yang": "NETMOD",
    "ietf-snmp@2014-12-10.yang": "NETMOD",
    "ietf-system@2014-08-06.yang": "NETMOD",
    "ietf-template@2010-05-18.yang": "NETMOD",
    "ietf-x509-cert-to-name@2014-12-10.yang": "NETMOD",
    "ietf-yang-library@2016-06-21.yang": "NETCONF",
    "ietf-yang-metadata@2016-08-05.yang": "NETMOD",
    "ietf-yang-patch@2017-02-22.yang": "NETCONF",
    "ietf-yang-smiv2@2012-06-22.yang": "NETMOD",
    "ietf-yang-types@2010-09-24.yang": "NETMOD",
    "ietf-yang-types@2013-07-15.yang": "NETMOD"
}

NS_MAP = {
    "http://cisco.com/": "cisco",
    "http://www.huawei.com/netconf": "huawei",
    "http://openconfig.net/yang": "openconfig",
    "http://tail-f.com/": "tail-f",
    "http://yang.juniper.net/": "juniper"
}

github = 'https://github.com/'
github_raw = 'https://raw.githubusercontent.com/'
MISSING_ELEMENT = 'missing element'


class Modules:
    def __init__(self, yang_models_dir, log_directory, path, html_result_dir, jsons, temp_dir,
                 is_vendor=False, is_yang_lib=False, data=None,
                 is_vendor_imp_inc=False, run_integrity=False):
        """
        Preset Modules class to parse yang module and save data to it.
        :param yang_models_dir:     (str) directory with all yang modules from
                                    github https://github.com/YangModels/yang
        :param log_directory:       (str) directory where the log file is saved
        :param path:                (str) path to yang file being parsed
        :param html_result_dir:     (str) path to directory with html result
                                    files
        :param jsons:               (obj) LoadFiles class containing all the json
                                    and html files with parsed results
        :param temp_dir:            (str) path to temporary directory
        :param is_vendor:           (boolean) if we parsing vendor files (cisco, huawei, ..)
                                    or sdo files (ietf, ieee, ...)
        :param is_yang_lib:         (boolean) if we are parsing file from yang_lib
                                    capability file
        :param data:                (dict) data from yang_lib capability file with additional
                                    information
        :param is_vendor_imp_inc:   (boolean) Obsolete
        :param run_integrity        (boolean) if we are running integrity as well. If true
                                    part of the data parsed are not needed and therefor not
                                    parsed
        """
        global LOGGER
        LOGGER = log.get_logger('modules', log_directory + '/parseAndPopulate.log')
        config_path = '/etc/yangcatalog/yangcatalog.conf'
        config = ConfigParser.ConfigParser()
        config._interpolation = ConfigParser.ExtendedInterpolation()
        config.read(config_path)
        self.__web_uri = config.get('Web-Section', 'my_uri', fallback="https://yangcatalog.org")
        self.run_integrity = run_integrity
        self.__temp_dir = temp_dir
        self.__missing_submodules = []
        self.__missing_modules = []
        self.__missing_namespace = None
        self.__missing_revision = None
        self.is_yang_lib = is_yang_lib
        self.html_result_dir = html_result_dir
        self.jsons = jsons
        self.__is_vendor = is_vendor
        self.revision = '*'
        self.__path = path
        self.features = []
        self.deviations = []
        self.yang_models = yang_models_dir

        if is_vendor:
            if is_yang_lib:
                self.deviations = data['deviations']
                self.features = data['features']
                self.revision = data['revision']
                if self.revision is None:
                    self.revision = '*'
                self.__path = self.__find_file(data['name'], self.revision)
            else:
                self.features = self.\
                    __resolve_deviations_and_features('features=', data)
                self.deviations = \
                    self.__resolve_deviations_and_features('deviations=', data)

                if 'revision' in data:
                    revision_and_more = data.split('revision=')[1]
                    revision = revision_and_more.split('&')[0]
                    self.revision = revision

                self.__path = self.__find_file(data.split('&')[0], self.revision)
        else:
            self.__path = path

        if is_vendor_imp_inc:
            self.__is_vendor = True
        if self.__path:
            self.name = None
            self.organization = None
            self.ietf_wg = None
            self.namespace = None
            self.schema = None
            self.generated_from = None
            self.maturity_level = None
            self.document_name = None
            self.author_email = None
            self.reference = None
            self.tree = None
            self.expired = None
            self.expiration_date = None
            self.module_classification = None
            self.compilation_status = None
            self.compilation_result = {}
            self.prefix = None
            self.yang_version = None
            self.description = None
            self.contact = None
            self.belongs_to = None
            self.submodule = []
            self.dependencies = []
            self.module_type = None
            self.tree_type = None
            self.semver = None
            self.derived_semver = None
            self.implementation = []
            self.imports = []
            self.json_submodules = json.dumps([])
            self.__parsed_yang = yangParser.parse(os.path.abspath(self.__path))
            if self.__parsed_yang is None:
                raise ParseException(path)
        else:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path.split('&')[0])
            # TODO file does not exist

    def __resolve_deviations_and_features(self, search_for, data):
        my_list = []
        if search_for in data:
            devs_or_features = data.split(search_for)[1]
            devs_or_features = devs_or_features.split('&')[0]
            my_list = devs_or_features.split(',')
        return my_list

    def parse_all(self, git_commit_hash, name, keys, schema, schema_start, to, api_sdo_json=None):
        """
        Parse all data that we can from the module.
        :param git_commit_hash: (str) name of the git commit hash where we can find the module
        :param name:            (str) name of the module (not parsed out of the module)
        :param keys:            (set) set of keys labeled as "<name>@<revision>/<organization>"
        :param schema:          (str) full url to raw github module
        :param to:              (str) Where to save the module at. This is a directory
        :param api_sdo_json:    (dict) some aditional information about module given from client
                                using yangcatalog api
        """
        def get_json(js):
            if js:
                return js
            else:
                return u'missing element'

        if api_sdo_json:
            author_email = api_sdo_json.get('author-email')
            maturity_level = api_sdo_json.get('maturity-level')
            reference = api_sdo_json.get('reference')
            document_name = api_sdo_json.get('document-name')
            generated_from = api_sdo_json.get('generated-from')
            if sys.version_info >= (3, 4):
                organization = get_json(api_sdo_json.get('organization'))
            else:
                organization = unicodedata.normalize('NFKD', get_json(
                    api_sdo_json.get('organization'))).encode('ascii', 'ignore')
            module_classification = api_sdo_json.get('module-classification')
        else:
            author_email = None
            reference = None
            maturity_level = None
            generated_from = None
            organization = None
            module_classification = None
            document_name = None
        self.__resolve_name(name)
        self.__resolve_revision()
        self.__resolve_module_type()
        self.__resolve_belongs_to()
        self.__resolve_namespace()
        self.__resolve_organization(organization)
        key = '{}@{}/{}'.format(self.name, self.revision, self.organization)
        if key in keys:
            self.__resolve_schema(schema, git_commit_hash, schema_start)
            self.__resolve_submodule()
            self.__resolve_imports(git_commit_hash)
            return
        self.__resolve_schema(schema, git_commit_hash, schema_start)
        self.__resolve_submodule()
        self.__resolve_imports(git_commit_hash)
        if not self.run_integrity:
            self.__save_file(to)
            self.__resolve_generated_from(generated_from)
            self.__resolve_compilation_status_and_result()
            self.__resolve_yang_version()
            self.__resolve_prefix()
            self.__resolve_contact()
            self.__resolve_description()
            self.__resolve_document_name_and_reference(document_name, reference)
            self.__resolve_tree()
            self.__resolve_module_classification(module_classification)
            self.__resolve_working_group()
            self.__resolve_author_email(author_email)
            self.__resolve_maturity_level(maturity_level)
            self.__resolve_semver()

    def __resolve_tree(self):
        if self.module_type == 'module':
            self.tree = 'services/tree/{}@{}.yang'.format(self.name,
                                                          self.revision)

    def __save_file(self, to):
        file_with_path = '{}/{}@{}.yang'.format(to, self.name, self.revision)
        if not os.path.exists(file_with_path):
            with open(self.__path, 'r', encoding='utf-8') as f:
                with open(file_with_path, 'w', encoding='utf-8') as f2:
                    f2.write(f.read())

    def __resolve_semver(self):
        yang_file = open(self.__path, encoding='utf-8')
        for line in yang_file:
            if re.search('oc-ext:openconfig-version .*;', line):
                self.semver = re.findall('[0-9]+.[0-9]+.[0-9]+', line).pop()
        yang_file.close()

    def __resolve_imports(self, git_commit_hash):
        try:
            self.imports = self.__parsed_yang.search('import')
            if len(self.imports) == 0:
                return

            for chunk in self.imports:
                dependency = self.Dependencies()
                dependency.name = chunk.arg
                if len(chunk.search('revision-date')) > 0:
                    dependency.revision = chunk.search('revision-date')[0].arg
                if dependency.revision:
                    yang_file = self.__find_file(dependency.name,
                                                 dependency.revision)
                else:
                    yang_file = self.__find_file(dependency.name)
                if yang_file is None:
                    dependency.schema = None
                else:
                    try:
                        if '/yangmodels/yang/' in yang_file:
                            suffix = os.path.abspath(yang_file).split('/yangmodels/yang/')[1]
                            prefix = 'https://raw.githubusercontent.com/yangmodels'
                            dependency.schema = '{}/yang/master/{}'.format(prefix, suffix)
                        elif git_commit_hash in yang_file:
                            prefix = self.schema.split('/{}/'.format(git_commit_hash))[0]
                            suffix = os.path.abspath(yang_file).split('/{}/'.format(git_commit_hash))[1]
                            dependency.schema = '{}/master/{}'.format(prefix, suffix)
                    except:
                        LOGGER.ERROR('Unable to resolve schema for {}@{}.yang'.format(self.name, self.revision))
                        dependency.schema = None
                        self.dependencies.append(dependency)
                self.dependencies.append(dependency)
        except:
            return

    def add_vendor_information(self, platform_data,
                               confarmance_type, capability, netconf_version,
                               integrity_checker, split):
        for data in platform_data:
            implementation = self.Implementations()
            implementation.vendor = data['vendor']
            implementation.platform = data['platform']
            implementation.software_version = data['software-version']
            implementation.software_flavor = data['software-flavor']
            implementation.os_version = data['os-version']
            implementation.feature_set = data['feature-set']
            implementation.os_type = data['os']
            implementation.feature = self.features
            implementation.capability = capability
            implementation.netconf_version = netconf_version

            if self.is_yang_lib:
                for deviation in self.deviations:
                    devs = implementation.Deviations()
                    devs.name = deviation['name']
                    devs.revision = deviation['revision']
                    implementation.deviations.append(devs)
            else:
                for name in self.deviations:
                    devs = implementation.Deviations()
                    devs.name = name
                    yang_file = self.__find_file(name)

                    if yang_file is None:
                        devs.revision = '1970-01-01'
                    else:
                        try:
                            s = yang_file.split('/')
                            key = '/'.join(split[0:-1])
                            integrity_checker.remove_one(key, s[-1])
                            devs.revision = yangParser.parse(os.path.abspath(yang_file)) \
                                .search('revision')[0].arg
                        except:
                            devs.revision = '1970-01-01'
                    implementation.deviations.append(devs)

            implementation.conformance_type = confarmance_type
            self.implementation.append(implementation)

    def __resolve_name(self, name):
        LOGGER.debug("Resolving name")
        if self.__parsed_yang.arg is not None or self.__parsed_yang.arg != '':
            self.name = self.__parsed_yang.arg
        else:
            self.name = name

    def __resolve_revision(self):
        LOGGER.debug("Resolving revision")
        if self.revision == '*':
            try:
                self.revision = self.__parsed_yang.search('revision')[0].arg
            except:
                self.__missing_revision = self.name
                self.revision = '1970-01-01'
            rev_parts = self.revision.split('-')
            try:
                self.revision = datetime(int(rev_parts[0]), int(rev_parts[1]), int(rev_parts[2])).date().isoformat()
            except ValueError as e:
                try:
                    if int(rev_parts[2]) == 29 and int(rev_parts[1]) == 2:
                        self.revision = datetime(int(rev_parts[0]), int(rev_parts[1]), 28).date().isoformat()
                except ValueError as e2:
                    self.revision = '1970-01-01'
                    self.__missing_revision = self.name

    def __resolve_schema(self, schema, git_commit_hash, schema_start):
        LOGGER.debug("Resolving schema")
        if self.organization == 'etsi':
            suffix = self.__path.split('SOL006')[-1]
            self.schema = 'https://forge.etsi.org/rep/nfv/SOL006/raw//master/{}'.format(suffix)
        elif schema:
            split_index = '/{}/'.format(git_commit_hash)
            if '/yangmodels/yang/' in self.__path:
                split_index = '/yangmodels/yang/'
            if self.__is_vendor:
                suffix = os.path.abspath(self.__path).split(split_index)[1]
                if schema_start is not None:
                    git_root_dir = schema_start.split('/')[0]
                    if len(suffix.split(git_root_dir)) > 1:
                        suffix = git_root_dir + suffix.split(git_root_dir)[1]
                self.schema = schema + suffix
            else:
                self.schema = schema
        else:
            self.schema = None

    def __resolve_module_classification(self, module_classification=None):
        LOGGER.debug("Resolving module classification")
        if module_classification:
            self.module_classification = module_classification
        else:
            self.module_classification = 'unknown'

    def __resolve_maturity_level(self, maturity_level=None):
        LOGGER.debug("Resolving maturity level")
        if maturity_level:
            self.maturity_level = maturity_level
        else:
            yang_name = self.name + '.yang'
            yang_name_rev = self.name + '@' + self.revision + '.yang'
            try:
                maturity_level = self.jsons.status['IETFDraft'][yang_name][0].split(
                    '</a>')[0].split('\">')[1].split('-')[1]
                if 'ietf' in maturity_level:
                    self.maturity_level = 'adopted'
                    return
                else:
                    self.maturity_level = 'initial'
                    return
            except KeyError:
                pass
            # try to find in draft with revision
            try:
                maturity_level = self.jsons.status['IETFDraft'][yang_name_rev][0].split(
                    '</a>')[0].split('\">')[1].split('-')[1]
                if 'ietf' in maturity_level:
                    self.maturity_level = 'adopted'
                    return
                else:
                    self.maturity_level = 'initial'
                    return
            except KeyError:
                pass
            # try to find in rfc with revision
            if self.jsons.status['IETFYANGRFC'].get(yang_name_rev) is not None:
                self.maturity_level = 'ratified'
                return
            if self.jsons.status['IETFYANGRFC'].get(yang_name) is not None:
                self.maturity_level = 'ratified'
                return
            self.maturity_level = None

    def __resolve_author_email(self, author_email=None):
        LOGGER.debug("Resolving author email")
        if author_email:
            self.author_email = author_email
        else:
            yang_name = self.name + '.yang'
            yang_name_rev = self.name + '@' + self.revision + '.yang'
            try:
                self.author_email = self.jsons.status['IETFDraft'][yang_name][1].split(
                    '\">Email')[0].split('mailto:')[1]
                return
            except KeyError:
                pass
            # try to find in draft with revision
            try:
                self.author_email = self.jsons.status['IETFDraft'][yang_name_rev][1].split(
                    '\">Email')[0].split('mailto:')[1]
                return
            except KeyError:
                pass
            try:
                self.author_email = self.jsons.status['IETFDraftExample'][yang_name][
                    1].split('\">Email')[0].split('mailto:')[1]
                return
            except KeyError:
                pass
            # try to find in draft with revision
            try:
                self.author_email = self.jsons.status['IETFDraftExample'][yang_name_rev][1].split(
                    '\">Email')[0].split('mailto:')[1]
                return
            except KeyError:
                pass
            self.author_email = None

    def __resolve_working_group(self):
        LOGGER.debug("Resolving working group")
        if self.organization == 'ietf':
            yang_name = self.name + '.yang'
            yang_name_rev = self.name + '@' + self.revision + '.yang'
            try:
                self.ietf_wg = self.jsons.status['IETFDraft'][yang_name][0].split(
                        '</a>')[0].split('\">')[1].split('-')[2]
                return
            except KeyError:
                pass
            # try to find in draft with revision
            try:
                self.ietf_wg = self.jsons.status['IETFDraft'][yang_name_rev][
                        0].split('</a>')[0].split('\">')[1].split('-')[2]
                return
            except KeyError:
                pass
            # try to find in ietf RFC map with revision
            try:
                self.ietf_wg = IETF_RFC_MAP[yang_name]
                return
            except KeyError:
                pass
            # try to find in ietf RFC map with revision
            try:
                self.ietf_wg = IETF_RFC_MAP[yang_name_rev]
                return
            except KeyError:
                pass
            self.ietf_wg = None

    def __resolve_document_name_and_reference(self, document_name=None,
                                              reference=None):
        LOGGER.debug("Resolving document name and reference")
        if document_name:
            self.document_name = document_name
        if reference:
            self.reference = reference

        if document_name is None and reference is None:
            self.document_name, self.reference = \
                self.__parse_document_reference()

    def __resolve_submodule(self):
        LOGGER.debug("Resolving submodule")
        try:
            submodules = self.__parsed_yang.search('include')
        except:
            return

        if len(submodules) == 0:
            return

        for chunk in submodules:
            dep = self.Dependencies()
            sub = self.Submodules()
            sub.name = chunk.arg

            if len(chunk.search('revision-date')) > 0:
                sub.revision = chunk.search('revision-date')[0].arg

            if sub.revision:
                yang_file = self.__find_file(sub.name, sub.revision, True)
                dep.revision = sub.revision
            else:
                yang_file = self.__find_file(sub.name, submodule=True)
                try:
                    sub.revision = \
                        yangParser.parse(os.path.abspath(yang_file)).search(
                            'revision')[0].arg
                except:
                    sub.revision = '1970-01-01'
            if yang_file is None:
                LOGGER.error('Module can not be found')
                continue
            path = '/'.join(self.schema.split('/')[0:-1])
            path += '/{}'.format(yang_file.split('/')[-1])
            if yang_file:
                sub.schema = path
            dep.name = sub.name
            dep.schema = sub.schema
            self.dependencies.append(dep)
            self.submodule.append(sub)
        self.json_submodules = json.dumps([{'name': self.submodule[x].name,
                                            'schema': self.submodule[x].schema,
                                            'revision': self.submodule[
                                                x].revision
                                            } for x in
                                           range(0, len(self.submodule))])

    def __resolve_yang_version(self):
        LOGGER.debug("Resolving yang version")
        try:
            self.yang_version = self.__parsed_yang.search('yang-version')[0].arg
        except:
            self.yang_version = '1.0'
        if self.yang_version == '1':
            self.yang_version = '1.0'

    def __resolve_generated_from(self, generated_from=None):
        LOGGER.debug("Resolving generated from")
        if generated_from:
            self.generated_from = generated_from
        else:
            if ':smi' in self.namespace:
                self.generated_from = 'mib'
            elif 'cisco' in self.name.lower():
                self.generated_from = 'native'
            else:
                self.generated_from = 'not-applicable'

    def __resolve_compilation_status_and_result(self):
        LOGGER.debug("Resolving compiation status and result")
        self.compilation_status = self.__parse_status()
        if self.compilation_status['status'] not in ['passed', 'passed-with-warnings', 'failed', 'pending', 'unknown']:
            self.compilation_status['status'] = 'unknown'
        if self.compilation_status['status'] != 'passed':
            self.compilation_result = self.__parse_result()
            if (self.compilation_result['pyang'] == ''
                and self.compilation_result['yanglint'] == ''
                and self.compilation_result['confdrc'] == ''
                and self.compilation_result['yumadump'] == ''
                and self.organization == 'cisco'
                and (self.generated_from == 'native'
                     or self.generated_from == 'mib')):
                self.compilation_status['status'] = 'passed'
        else:
            self.compilation_result = {'pyang': '', 'pyang_lint': '',
                                       'confdrc': '', 'yumadump': '',
                                       'yanglint': ''}
        self.compilation_result = self.__create_compilation_result_file()
        self.compilation_status = self.compilation_status['status']

    def __create_compilation_result_file(self):
        LOGGER.debug("Resolving compilation status")
        if self.compilation_status['status'] == 'passed' \
                and self.compilation_result['pyang_lint'] == '':
            return ''
        else:
            result = self.compilation_result
        result['name'] = self.name
        result['revision'] = self.revision
        context = {'result': result,
                   'ths': self.compilation_status['ths']}
        template = os.path.dirname(os.path.realpath(__file__)) + '/template/compilationStatusTemplate.html'
        rendered_html = stats.render(template, context)
        file_url = '{}@{}_{}.html'.format(self.name, self.revision,
                                          self.organization)

        # Don t override status if it was already written once
        file_path = '{}/{}'.format(self.html_result_dir, file_url)
        if os.path.exists(file_path):
            if self.compilation_status['status'] in ['unknown', 'pending']:
                self.compilation_status['status'] = None
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_html)
                os.chmod(file_path, 0o664)
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(rendered_html)
            os.chmod(file_path, 0o664)

        return '{}/results/{}'.format(self.__web_uri, file_url)

    def __resolve_contact(self):
        LOGGER.debug("Resolving contact")
        try:
            self.contact = self.__parsed_yang.search('contact')[0].arg
        except:
            self.contact = None

    def __resolve_description(self):
        LOGGER.debug("Resolving description")
        try:
            self.description = self.__parsed_yang.search('description')[0].arg
        except:
            self.description = None

    def __resolve_namespace(self):
        LOGGER.debug("Resolving namespace")
        self.namespace = self.__resolve_submodule_case('namespace')
        if self.namespace == MISSING_ELEMENT:
            self.__missing_namespace = self.name + ' : ' + MISSING_ELEMENT

    def __resolve_belongs_to(self):
        LOGGER.debug("Resolving belongs to")
        if self.module_type == 'submodule':
            try:
                self.belongs_to = self.__parsed_yang.search('belongs-to')[0].arg
            except:
                self.belongs_to = None

    def __resolve_module_type(self):
        LOGGER.debug("Resolving module type")
        try:
            file_input = open(self.__path, "r", encoding='utf-8')
        except:
            LOGGER.critical(
                'Could not open a file {}. Maybe a path is set wrongly'.format(
                    self.__path))
            sys.exit(10)
        all_lines = file_input.readlines()
        file_input.close()
        commented_out = False
        for each_line in all_lines:
            module_position = each_line.find('module')
            submodule_position = each_line.find('submodule')
            cpos = each_line.find('//')
            if commented_out:
                mcpos = each_line.find('*/')
            else:
                mcpos = each_line.find('/*')
            if mcpos != -1 and cpos > mcpos:
                if commented_out:
                    commented_out = False
                else:
                    commented_out = True
            if submodule_position >= 0 and (
                            submodule_position < cpos or cpos == -1) and not commented_out:
                LOGGER.debug(
                    'Module {} is of type submodule'.format(self.__path))
                self.module_type = 'submodule'
                return
            if module_position >= 0 and (
                            module_position < cpos or cpos == -1) and not commented_out:
                LOGGER.debug('Module {} is of type module'.format(self.__path))
                self.module_type = 'module'
                return
        LOGGER.error('Module {} has wrong format'.format(self.__path))
        self.module_type = None

    def __resolve_organization(self, organization=None):
        LOGGER.debug("Resolving organization")
        if organization:
            self.organization = organization.lower()
        else:
            try:
                temp_organization = self.__parsed_yang.search('organization')[0].arg.lower()
                if 'cisco' in temp_organization or 'CISCO' in temp_organization:
                    self.organization = 'cisco'
                    return
                elif 'ietf' in temp_organization or 'IETF' in temp_organization:
                    self.organization = 'ietf'
                    return
            except:
                pass
            for ns, org in NS_MAP.items():
                if ns in self.namespace:
                    self.organization = org
                    return
            if self.organization is None:
                if 'cisco' in self.namespace or 'CISCO' in self.namespace:
                    self.organization = 'cisco'
                    return
                elif 'ietf' in self.namespace or 'IETF' in self.namespace:
                    self.organization = 'ietf'
                    return
                elif 'urn:' in self.namespace:
                    self.organization = \
                        self.namespace.split('urn:')[1].split(':')[0]
                    return
            if self.organization is None:
                self.organization = 'independent'

    def __resolve_prefix(self):
        LOGGER.debug("Resolving prefix")
        self.prefix = self.__resolve_submodule_case('prefix')

    def __resolve_submodule_case(self, field):
        if self.module_type == 'submodule':
            LOGGER.debug(
                'Getting parent information because file {} is a submodule'.format(
                    self.__path))
            yang_file = self.__find_file(self.belongs_to)
            if yang_file is None:
                return None
            parsed_parent_yang = yangParser.parse(os.path.abspath(yang_file))
            try:
                return parsed_parent_yang.search(field)[0].arg
            except:
                if field == 'prefix':
                    return None
                else:
                    return MISSING_ELEMENT
        else:
            try:
                return self.__parsed_yang.search(field)[0].arg
            except:
                if field == 'prefix':
                    return None
                else:
                    return MISSING_ELEMENT

    def __parse_status(self):
        LOGGER.debug('Parsing status of module {}'.format(self.__path))
        status = {'status': 'unknown'}
        with_revision = [True, False]
        for w_rev in with_revision:
            if status['status'] == 'unknown':
                for name in self.jsons.names:
                    if status['status'] == 'unknown':
                        if name == 'IETFDraft':
                            status = self.__get_module_status(w_rev, name, 3)
                        else:
                            status = self.__get_module_status(w_rev, name)
                    else:
                        break
            else:
                break
        return status

    def __get_module_status(self, with_revision, name, index=0):
        if name == 'IETFYANGRFC':
            return {'status': 'unknown'}
        status = {}
        if with_revision:
        # try to find with revision
            try:
                status['status'] = self.jsons.status[name][self.name + '@' + self.revision + '.yang'][
                    index]
                if status['status'] == 'PASSED WITH WARNINGS':
                    status['status'] = 'passed-with-warnings'
                status['status'] = status['status'].lower()
                status['ths'] = self.jsons.headers[name]
                return status
            except:
                pass
        else:
            # try to find without revision
            try:
                status['status'] = self.jsons.status[name][self.name + '.yang'][index]
                if status['status'] == 'PASSED WITH WARNINGS':
                    status['status'] = 'passed-with-warnings'
                status['status'] = status['status'].lower()
                status['ths'] = self.jsons.headers[name]
                return status
            except:
                pass
        return {'status': 'unknown', 'ths': self.jsons.headers[name]}

    def __parse_result(self):
        LOGGER.debug('Parsing compulation status of module {}'.format(self.__path))
        res = ''
        with_revision = [True, False]
        for w_rev in with_revision:
            for name in self.jsons.names:
                if name == 'IETFYANGRFC':
                    continue
                if res == '':
                    if name == 'IETFDraft':
                        res = self.__parse_res(w_rev, name, 3)
                    else:
                        res = self.__parse_res(w_rev, name)
                else:
                    return res
        return {'pyang': '', 'pyang_lint': '', 'confdrc': '', 'yumadump': '',
                'yanglint': ''}

    def __parse_res(self, with_revision, name, index=0):
        result = {}
        if with_revision:
            # try to find with revision
            try:
                yang_name = self.name + '@' + self.revision + '.yang'
                result['pyang_lint'] = self.jsons.status[name][yang_name][1 + index]
                result['pyang'] = self.jsons.status[name][yang_name][2 + index]
                result['confdrc'] = self.jsons.status[name][yang_name][3 + index]
                result['yumadump'] = self.jsons.status[name][yang_name][4 + index]
                result['yanglint'] = self.jsons.status[name][yang_name][5 + index]
                return result
            except:
                pass
        else:
        # try to find without revision
            try:
                yang_name = self.name + '.yang'
                result['pyang_lint'] = self.jsons.status[name][yang_name][1 + index]
                result['pyang'] = self.jsons.status[name][yang_name][2 + index]
                result['confdrc'] = self.jsons.status[name][yang_name][3 + index]
                result['yumadump'] = self.jsons.status[name][yang_name][4 + index]
                result['yanglint'] = self.jsons.status[name][yang_name][5 + index]
                return result
            except:
                pass
        return ''

    def __parse_document_reference(self):
        LOGGER.debug(
            'Parsing document reference of module {}'.format(self.__path))
        # try to find in draft without revision
        yang_name = self.name + '.yang'
        yang_name_rev = self.name + '@' + self.revision + '.yang'
        try:
            doc_name = self.jsons.status['IETFDraft'][yang_name][0].split(
                '</a>')[0].split('\">')[1]
            doc_source = self.jsons.status['IETFDraft'][yang_name][0].split(
                'a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
        # try to find in draft with revision
        try:
            doc_name = self.jsons.status['IETFDraft'][yang_name_rev][
                0].split('</a>')[0].split('\">')[1]
            doc_source = self.jsons.status['IETFDraft'][yang_name_rev][
                0].split('a href=\"')[1].split('\">')[0]
            return [doc_name, doc_source]
        except KeyError:
            pass
            # try to find in rfc with revision
            try:
                doc_name = self.jsons.status['IETFYANGRFC'][
                    yang_name_rev].split('</a>')[0].split('\">')[1]
                doc_source = self.jsons.status['IETFYANGRFC'][
                    yang_name_rev].split('a href=\"')[1].split('\">')[0]
                return [doc_name, doc_source]
            except KeyError:
                pass
            try:
                doc_name = self.jsons.status['IETFYANGRFC'][yang_name].split('</a>')[
                    0].split('\">')[1]
                doc_source = self.jsons.status['IETFYANGRFC'][yang_name].split(
                    'a href=\"')[1].split('\">')[0]
                return [doc_name, doc_source]
            except KeyError:
                pass
        return [None, None]

    def __find_file(self, name, revision='*', submodule=False,
                    normal_search=True):
        yang_file = find_first_file('/'.join(self.__path.split('/')[0:-1]),
                                    name + '.yang'
                                    , name + '@' + revision + '.yang')
        if yang_file is None:
            if normal_search:
                if submodule:
                    self.__missing_submodules.append(name)
                else:
                    self.__missing_modules.append(name)
            yang_file = find_first_file(self.yang_models, name + '.yang',
                                        name + '@' + revision + '.yang')
        return yang_file

    class Submodules:
        def __init__(self):
            self.name = None
            self.revision = None
            self.schema = None

    class Dependencies:
        def __init__(self):
            self.name = None
            self.revision = None
            self.schema = None

    class Implementations:
        def __init__(self):
            self.vendor = None
            self.platform = None
            self.software_version = None
            self.software_flavor = None
            self.os_version = None
            self.feature_set = None
            self.os_type = None
            self.feature = []
            self.deviations = []
            self.conformance_type = None
            self.capability = None
            self.netconf_version = None

        class Deviations:
            def __init__(self):
                self.name = None
                self.revision = None
                self.schema = None

    def resolve_integrity(self, integrity_checker, split):
        key = '/'.join(split[0:-1])
        key2 = key + '/' + split[-1]
        if self.name not in self.__missing_modules:
            integrity_checker.remove_one(key, self.__path.split('/')[-1])
        integrity_checker.add_submodule(key2, self.__missing_submodules)
        integrity_checker.add_module(key2, self.__missing_modules)
        integrity_checker.add_revision(key2, self.__missing_revision)

        if self.__missing_namespace is None:
            for ns, org in NS_MAP.items():
                if (ns not in self.namespace and 'urn:' not in self.namespace)\
                        or 'urn:cisco' in self.namespace:
                    self.__missing_namespace = self.name + ' : ' + self.namespace
                else:
                    self.__missing_namespace = None
                    break

        integrity_checker.add_namespace(key2, self.__missing_namespace)

