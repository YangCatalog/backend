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

__author__ = 'Dmytro Kyrychenko'
__copyright__ = 'Copyright The IETF Trust 2022, All Rights Reserved'
__license__ = 'Apache License, Version 2.0'
__email__ = 'dmytro.kyrychenko@pantheon.tech'

import logging
import unittest
from unittest import mock

from pyang.statements import new_statement

from parseAndPopulate.models.dependency import Dependency
from parseAndPopulate.models.implementation import Implementation
from parseAndPopulate.models.submodule import Submodule
from parseAndPopulate.models.vendor_modules import VendorInfo
from parseAndPopulate.resolvers.basic import BasicResolver
from parseAndPopulate.resolvers.expiration import ExpirationResolver
from parseAndPopulate.resolvers.generated_from import GeneratedFromResolver
from parseAndPopulate.resolvers.implementations import ImplementationResolver
from parseAndPopulate.resolvers.imports import ImportsResolver
from parseAndPopulate.resolvers.module_type import ModuleTypeResolver
from parseAndPopulate.resolvers.namespace import NamespaceResolver
from parseAndPopulate.resolvers.organization import OrganizationResolver
from parseAndPopulate.resolvers.prefix import PrefixResolver
from parseAndPopulate.resolvers.revision import RevisionResolver
from parseAndPopulate.resolvers.semantic_version import SemanticVersionResolver
from parseAndPopulate.resolvers.submodule import SubmoduleResolver
from parseAndPopulate.resolvers.yang_version import YangVersionResolver


class TestResolversClass(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger('test')

        return super().setUp()

    # BasicResolver
    def test_basic_resolver_simple_resolve(self):
        # represents 'module test-module: output test-output'
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        output_stmt = new_statement(None, module_stmt, None, 'output', 'test-output')
        module_stmt.substmts.append(output_stmt)

        br = BasicResolver(parsed_yang=module_stmt, property_name='output')
        res = br.resolve()
        self.assertEqual(res, 'test-output')

    def test_basic_resolver_simple_resolve_with_underscore(self):
        # consider 'leaf-list' if this keyword does not work
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        output_stmt = new_statement(None, module_stmt, None, 'output-test', 'test-output')
        module_stmt.substmts.append(output_stmt)

        br = BasicResolver(parsed_yang=module_stmt, property_name='output_test')
        res = br.resolve()
        self.assertEqual(res, 'test-output')

    # GeneratedFromResolver
    def test_generated_from_resolver_simple_resolve_default(self):
        gfr = GeneratedFromResolver(self.logger, name='test_default', namespace='some_namespace')
        res = gfr.resolve()
        self.assertEqual(res, 'not-applicable')

    def test_generated_from_resolver_simple_resolve_default_no_namespace(self):
        gfr = GeneratedFromResolver(self.logger, name='test_default', namespace=None)
        res = gfr.resolve()
        self.assertEqual(res, 'not-applicable')

    def test_generated_from_resolver_simple_resolve_mib(self):
        gfr = GeneratedFromResolver(self.logger, name='test_mib', namespace='something:smi')
        res = gfr.resolve()
        self.assertEqual(res, 'mib')

    def test_generated_from_resolver_simple_resolve_native(self):
        gfr = GeneratedFromResolver(
            self.logger,
            name='test_native_cisco',
            namespace='urn:cisco:params:xml:ns:yang:cisco-xe-ietf-yang-push-ext',
        )
        res = gfr.resolve()
        self.assertEqual(res, 'native')

    def test_generated_from_resolver_simple_resolve_native_caps(self):
        gfr = GeneratedFromResolver(
            self.logger,
            name='CISCOtest_native',
            namespace='URN:CISCO:PARAMS:XML:NS:YANG:CISCO-XE-IETF-YANG-PUSH-EXT',
        )
        res = gfr.resolve()
        self.assertEqual(res, 'native')

    # ImplementationResolver
    def test_implementation_resolver_simple_resolve(self):
        platform_data1 = {
            'vendor': 'cisco',
            'platform': 'Nexus 9000',
            'software-version': '10.3(1)',
            'software-flavor': 'ALL',
            'os-version': '10.3(1)',
            'feature-set': 'ALL',
            'os': 'NX-OS',
        }
        platform_data2 = {
            'vendor': 'cisco',
            'platform': 'Nexus 3000',
            'software-version': '10.2',
            'software-flavor': 'ALL',
            'os-version': '10.2',
            'feature-set': 'ALL',
            'os': 'NX-OS',
        }
        platform_data = [platform_data1, platform_data2]
        conformance_type = 'implement'
        netconf_capabilities = ['capabilities1', 'capabilities2']
        netconf_versions = ['1.0', '2.0']

        vendor_info = VendorInfo(
            platform_data=platform_data,
            conformance_type=conformance_type,
            capabilities=netconf_capabilities,
            netconf_versions=netconf_versions,
        )
        features = ['feature1', 'feature2']
        deviations = [
            {'name': 'deviation1', 'revision': '2022-12-02'},
            {'name': 'deviation2', 'revision': '2022-12-01'},
        ]

        ir = ImplementationResolver(vendor_info, features, deviations)
        res = ir.resolve()

        self.assertEqual(len(res), 2)
        self.assertIsInstance(res[0], Implementation)
        for platform_data_i, implementation_i in zip(platform_data, res):
            self.assertEqual(implementation_i.vendor, platform_data_i['vendor'])
            self.assertEqual(implementation_i.platform, platform_data_i['platform'])
            self.assertEqual(implementation_i.software_version, platform_data_i['software-version'])
            self.assertEqual(implementation_i.software_flavor, platform_data_i['software-flavor'])
            self.assertEqual(implementation_i.os_version, platform_data_i['os-version'])
            self.assertEqual(implementation_i.feature_set, platform_data_i['feature-set'])
            self.assertEqual(implementation_i.os_type, platform_data_i['os'])
            self.assertEqual(implementation_i.feature, features)
            self.assertEqual(implementation_i.capabilities, netconf_capabilities)
            self.assertEqual(implementation_i.netconf_versions, netconf_versions)
            self.assertEqual(implementation_i.deviations[0].name, deviations[0]['name'])
            self.assertEqual(implementation_i.deviations[0].revision, deviations[0]['revision'])
            self.assertEqual(implementation_i.deviations[1].name, deviations[1]['name'])
            self.assertEqual(implementation_i.deviations[1].revision, deviations[1]['revision'])
            self.assertEqual(implementation_i.conformance_type, conformance_type)

    # ImportsResolver
    def test_imports_resolver_simple_resolve_no_imports(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        output_stmt = new_statement(None, module_stmt, None, 'output', 'test-output')
        module_stmt.substmts.append(output_stmt)

        ir = ImportsResolver(module_stmt, self.logger, 'foo')
        res = ir.resolve()
        self.assertEqual(res, [])

    @mock.patch('utility.util.get_yang')
    def test_imports_resolver_simple_resolve_one_import(self, mock_get_yang: mock.MagicMock):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        import_stmt = new_statement(None, module_stmt, None, 'import', 'test-import')
        module_stmt.substmts.append(import_stmt)

        mock_get_yang.return_value = 'test_yang_file@test_revision.yang'

        ir = ImportsResolver(module_stmt, self.logger, 'foo')
        res = ir.resolve()
        dep = res[0]
        self.assertIsInstance(dep, Dependency)
        self.assertEqual(dep.name, 'test-import')

    # TODO there is more to cover for ImportsResolver, need to get back to it later

    # ModuleTypeResolver
    def test_module_type_resolver_simple_resolve_module(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')

        mtr = ModuleTypeResolver(module_stmt, self.logger)
        res = mtr.resolve()
        self.assertEqual(res, 'module')

    def test_module_type_resolver_simple_resolve_submodule(self):
        submodule_stmt = new_statement(None, None, None, 'submodule', 'test-submodule')

        mtr = ModuleTypeResolver(submodule_stmt, self.logger)
        res = mtr.resolve()
        self.assertEqual(res, 'submodule')

    def test_module_type_resolver_simple_resolve_none(self):
        import_stmt = new_statement(None, None, None, 'import', 'test-import')

        mtr = ModuleTypeResolver(import_stmt, self.logger)
        res = mtr.resolve()
        self.assertIsNone(res)

    # ExpirationResolver
    def test_expiration_resolver_simple_resolve_nothing_changed(self):
        def redis_connection_side_effect():
            return None

        module = {
            'reference': 'test.org/reference',
            'maturity-level': 'adopted',
            'expired': 'not-applicable',
            'expires': None,
        }
        datatracker_failures = []
        redis_connection = mock.MagicMock(side_effect=redis_connection_side_effect)

        er = ExpirationResolver(module, self.logger, datatracker_failures, redis_connection)
        res = er.resolve()
        self.assertEqual(res, False)

    def test_expiration_resolver_simple_resolve_ratified_nothing_changed(self):
        def redis_connection_side_effect():
            return None

        module = {
            'reference': 'test.org/reference',
            'maturity-level': 'ratified',
            'expired': False,
            'expires': None,
        }
        datatracker_failures = []
        redis_connection = mock.MagicMock(side_effect=redis_connection_side_effect)

        er = ExpirationResolver(module, self.logger, datatracker_failures, redis_connection)
        res = er.resolve()
        self.assertEqual(res, False)

    def test_expiration_resolver_simple_resolve_expired_changed(self):
        def redis_connection_side_effect():
            return None

        module = {
            'name': 'test_name',
            'revision': '2022-12-02',
            'reference': 'test.org/reference',
            'maturity-level': 'adopted',
            'expired': True,
            'expires': None,
        }
        datatracker_failures = []
        redis_connection = mock.MagicMock(side_effect=redis_connection_side_effect)

        er = ExpirationResolver(module, self.logger, datatracker_failures, redis_connection)
        res = er.resolve()
        self.assertEqual(res, True)

    def test_expiration_resolver_simple_resolve_expires_changed(self):
        def redis_connection_side_effect():
            return True

        module = {
            'name': 'test_name',
            'revision': '2022-12-02',
            'reference': 'test.org/reference',
            'maturity-level': 'adopted',
            'expired': False,
            'expires': '2022-11-25',
        }
        datatracker_failures = []
        redis_connection = mock.MagicMock(side_effect=redis_connection_side_effect)

        er = ExpirationResolver(module, self.logger, datatracker_failures, redis_connection)
        res = er.resolve()
        self.assertEqual(res, True)

    # TODO more tests are applicable to ExpirationResolver

    # OrganizationResolver
    def test_organization_resolver_simple_resolve_independent(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        organization_stmt = new_statement(None, module_stmt, None, 'organization', 'unknown-org')
        module_stmt.substmts.append(organization_stmt)

        orgr = OrganizationResolver(module_stmt, self.logger, None)
        res = orgr.resolve()
        self.assertEqual(res, 'independent')

    def test_organization_resolver_simple_resolve_cisco_namespace(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        organization_stmt = new_statement(None, module_stmt, None, 'organization', 'unknown-org')
        module_stmt.substmts.append(organization_stmt)

        orgr = OrganizationResolver(module_stmt, self.logger, 'urn:cisco:params:xml:ns:yang:cisco-xe-ietf-yang-ext')
        res = orgr.resolve()
        self.assertEqual(res, 'cisco')

    def test_organization_resolver_simple_resolve_urn(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        organization_stmt = new_statement(None, module_stmt, None, 'organization', 'unknown-org')
        module_stmt.substmts.append(organization_stmt)

        orgr = OrganizationResolver(module_stmt, self.logger, 'urn:someorg:params:xml:ns:yang:xe-yang-push-ext')
        res = orgr.resolve()
        self.assertEqual(res, 'someorg')

    def test_organization_resolver_simple_resolve_nokia(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        organization_stmt = new_statement(None, module_stmt, None, 'organization', 'nokia')
        module_stmt.substmts.append(organization_stmt)

        orgr = OrganizationResolver(module_stmt, self.logger, None)
        res = orgr.resolve()
        self.assertEqual(res, 'nokia')

    # RevisionResolver
    def test_revision_resolver_simple_resolve(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        revision_stmt = new_statement(None, module_stmt, None, 'revision', '2022-11-17')
        module_stmt.substmts.append(revision_stmt)

        rr = RevisionResolver(module_stmt, self.logger)
        res = rr.resolve()
        self.assertEqual(res, '2022-11-17')

    def test_revision_resolver_simple_resolve_default(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        import_stmt = new_statement(None, module_stmt, None, 'import', 'some_import')
        module_stmt.substmts.append(import_stmt)

        rr = RevisionResolver(module_stmt, self.logger)
        res = rr.resolve()
        self.assertEqual(res, '1970-01-01')

    # SemanticVersionResolver
    def test_semantic_version_resolver_simple_resolve_cisco_semver(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        revision_stmt = new_statement(None, module_stmt, None, 'revision', '2022-12-02')
        semver_stmt = new_statement(None, revision_stmt, None, ('cisco-semver', 'module-version'), '1.0.0')
        module_stmt.substmts.append(revision_stmt)
        revision_stmt.substmts.append(semver_stmt)

        svr = SemanticVersionResolver(module_stmt, self.logger)
        res = svr.resolve()
        self.assertEqual(res, '1.0.0')

    def test_semantic_version_resolver_simple_resolve_cisco_semver_index_error(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        revision_stmt = new_statement(None, module_stmt, None, 'revision', '2022-12-02')
        semver_stmt = new_statement(None, revision_stmt, None, ('cisco-semver', 'module-version'), '1.bad.version.0')
        module_stmt.substmts.append(revision_stmt)
        revision_stmt.substmts.append(semver_stmt)

        svr = SemanticVersionResolver(module_stmt, self.logger)
        res = svr.resolve()
        self.assertIsNone(res)

    def test_semantic_version_resolver_simple_resolve_reference(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        revision_stmt = new_statement(None, module_stmt, None, 'revision', '2022-12-02')
        reference_stmt = new_statement(None, revision_stmt, None, 'reference', '1.0.0')
        module_stmt.substmts.append(revision_stmt)
        revision_stmt.substmts.append(reference_stmt)

        svr = SemanticVersionResolver(module_stmt, self.logger)
        res = svr.resolve()
        self.assertEqual(res, '1.0.0')

    def test_semantic_version_resolver_simple_resolve_reference_index_error(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        revision_stmt = new_statement(None, module_stmt, None, 'revision', '2022-12-02')
        reference_stmt = new_statement(None, revision_stmt, None, 'reference', '1.bad.version.0')
        module_stmt.substmts.append(revision_stmt)
        revision_stmt.substmts.append(reference_stmt)

        svr = SemanticVersionResolver(module_stmt, self.logger)
        res = svr.resolve()
        self.assertIsNone(res)

    def test_semantic_version_resolver_simple_resolve_openconfig(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        oc_ext_stmt = new_statement(None, module_stmt, None, ('oc-ext', 'openconfig-version'), '1.0.0')
        module_stmt.substmts.append(oc_ext_stmt)

        svr = SemanticVersionResolver(module_stmt, self.logger)
        res = svr.resolve()
        self.assertEqual(res, '1.0.0')

    def test_semantic_version_resolver_simple_resolve_openconfig_index_error(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        oc_ext_stmt = new_statement(None, module_stmt, None, ('oc-ext', 'openconfig-version'), '1.bad.version.0')
        module_stmt.substmts.append(oc_ext_stmt)

        svr = SemanticVersionResolver(module_stmt, self.logger)
        res = svr.resolve()
        self.assertIsNone(res)

    # SubmoduleResolver
    def test_submodule_resolver_simple_resolve_no_includes(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        output_stmt = new_statement(None, module_stmt, None, 'output', 'test-output')
        module_stmt.substmts.append(output_stmt)

        sr = SubmoduleResolver(module_stmt, self.logger, 'foo')
        res = sr.resolve()
        deps, subs = res[0], res[1]
        self.assertEqual(deps, [])
        self.assertEqual(subs, [])

    @mock.patch('backend.utility.util.get_yang')
    def test_submodule_resolver_simple_resolve_one_include(self, mock_get_yang: mock.MagicMock):
        mock_get_yang.return_value = 'test_yang_file@test_revision.yang'

        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        include_stmt = new_statement(None, module_stmt, None, 'include', 'ietf-yang-types')
        module_stmt.substmts.append(include_stmt)

        sr = SubmoduleResolver(module_stmt, self.logger, 'foo')
        res = sr.resolve()
        deps, subs = res[0], res[1]
        self.assertNotEqual(deps, [])
        self.assertNotEqual(subs, [])
        self.assertIsInstance(deps[0], Dependency)
        self.assertIsInstance(subs[0], Submodule)
        self.assertEqual(deps[0].name, 'ietf-yang-types')
        self.assertEqual(subs[0].name, 'ietf-yang-types')

    # YangVersionResolver
    def test_yang_version_resolver_simple_resolve(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        version_stmt = new_statement(None, module_stmt, None, 'yang-version', '42.0')
        module_stmt.substmts.append(version_stmt)

        yvr = YangVersionResolver(module_stmt, self.logger)
        res = yvr.resolve()
        self.assertEqual(res, '42.0')

    def test_yang_version_resolver_simple_resolve_default(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')

        yvr = YangVersionResolver(module_stmt, self.logger)
        res = yvr.resolve()
        self.assertEqual(res, '1.0')

    def test_yang_version_resolver_simple_resolve_one(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        version_stmt = new_statement(None, module_stmt, None, 'yang-version', '1')
        module_stmt.substmts.append(version_stmt)

        yvr = YangVersionResolver(module_stmt, self.logger)
        res = yvr.resolve()
        self.assertEqual(res, '1.0')

    # PrefixResolver
    def test_prefix_resolver_simple_resolve_module(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        prefix_stmt = new_statement(None, module_stmt, None, 'prefix', 'some-prefix')
        module_stmt.substmts.append(prefix_stmt)

        pr = PrefixResolver(module_stmt, self.logger, '', None)
        res = pr.resolve()
        self.assertEqual(res, 'some-prefix')

    def test_prefix_resolver_simple_resolve_module_index_error(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')

        pr = PrefixResolver(module_stmt, self.logger, '', None)
        res = pr.resolve()
        self.assertIsNone(res)

    def test_prefix_resolver_simple_resolve_submodule_no_belongs_to(self):
        module_stmt = new_statement(None, None, None, 'submodule', 'test-module')
        prefix_stmt = new_statement(None, module_stmt, None, 'prefix', 'some-prefix')
        module_stmt.substmts.append(prefix_stmt)

        pr = PrefixResolver(module_stmt, self.logger, '', None)
        res = pr.resolve()
        self.assertIsNone(res)

    def test_prefix_resolver_simple_resolve_submodule_no_yang_file(self):
        module_stmt = new_statement(None, None, None, 'submodule', 'test-module')
        prefix_stmt = new_statement(None, module_stmt, None, 'prefix', 'some-prefix')
        module_stmt.substmts.append(prefix_stmt)

        pr = PrefixResolver(module_stmt, self.logger, '', 'some_str')
        res = pr.resolve()
        self.assertIsNone(res)

    def test_prefix_resolver_simple_resolve_submodule(self):
        module_stmt = new_statement(None, None, None, 'submodule', 'test-module')
        prefix_stmt = new_statement(None, module_stmt, None, 'prefix', 'some-prefix')
        module_stmt.substmts.append(prefix_stmt)

        pr = PrefixResolver(module_stmt, self.logger, '', 'ietf-yang-types')
        res = pr.resolve()
        self.assertEqual(res, 'yang')

    # NamespaceResolver
    def test_namespace_resolver_simple_resolve_module(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')
        namespace_stmt = new_statement(
            None,
            module_stmt,
            None,
            'namespace',
            'urn:cisco:params:xml:ns:yang:cisco-xe-ietf-yang-push-ext',
        )
        module_stmt.substmts.append(namespace_stmt)

        nr = NamespaceResolver(module_stmt, self.logger, '', None)
        res = nr.resolve()
        self.assertEqual(res, 'urn:cisco:params:xml:ns:yang:cisco-xe-ietf-yang-push-ext')

    def test_namespace_resolver_simple_resolve_module_index_error(self):
        module_stmt = new_statement(None, None, None, 'module', 'test-module')

        nr = NamespaceResolver(module_stmt, self.logger, '', None)
        res = nr.resolve()
        self.assertEqual(res, 'missing element')

    def test_namespace_resolver_simple_resolve_submodule_no_belongs_to(self):
        module_stmt = new_statement(None, None, None, 'submodule', 'test-module')
        namespace_stmt = new_statement(
            None,
            module_stmt,
            None,
            'namespace',
            'urn:cisco:params:xml:ns:yang:cisco-xe-ietf-yang-push-ext',
        )
        module_stmt.substmts.append(namespace_stmt)

        nr = NamespaceResolver(module_stmt, self.logger, '', None)
        res = nr.resolve()
        self.assertEqual(res, 'missing element')

    def test_namespace_resolver_simple_resolve_submodule_no_yang_file(self):
        module_stmt = new_statement(None, None, None, 'submodule', 'test-module')
        namespace_stmt = new_statement(
            None,
            module_stmt,
            None,
            'namespace',
            'urn:cisco:params:xml:ns:yang:cisco-xe-ietf-yang-push-ext',
        )
        module_stmt.substmts.append(namespace_stmt)

        nr = NamespaceResolver(module_stmt, self.logger, '', 'some_str')
        res = nr.resolve()
        self.assertEqual(res, 'missing element')

    def test_namespace_resolver_simple_resolve_submodule(self):
        module_stmt = new_statement(None, None, None, 'submodule', 'test-module')
        namespace_stmt = new_statement(None, module_stmt, None, 'namespace', 'some-namespace')
        module_stmt.substmts.append(namespace_stmt)

        nr = NamespaceResolver(module_stmt, self.logger, '', 'ietf-yang-types')
        res = nr.resolve()
        self.assertEqual(res, 'urn:ietf:params:xml:ns:yang:ietf-yang-types')


if __name__ == '__main__':
    unittest.main()
