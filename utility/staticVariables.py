from enum import Enum

# ConfD requests headers
confd_header_str = 'application/yang-data+json'
confd_content_type = {'Content-type': confd_header_str}
confd_accept = {'Accept': confd_header_str}
confd_headers = {**confd_content_type, **confd_accept}

# JSON headers
json_header_str = 'application/json'
json_content_type = {'Content-type': json_header_str}
json_accept = {'Accept': json_header_str}
json_headers = {**json_content_type, **json_accept}

IETF_RFC_MAP = {
    'iana-crypt-hash@2014-08-06.yang': 'NETMOD',
    'iana-if-type@2014-05-08.yang': 'NETMOD',
    'ietf-complex-types@2011-03-15.yang': 'N/A',
    'ietf-inet-types@2010-09-24.yang': 'NETMOD',
    'ietf-inet-types@2013-07-15.yang': 'NETMOD',
    'ietf-interfaces@2014-05-08.yang': 'NETMOD',
    'ietf-ip@2014-06-16.yang': 'NETMOD',
    'ietf-ipfix-psamp@2012-09-05.yang': 'IPFIX',
    'ietf-ipv4-unicast-routing@2016-11-04.yang': 'NETMOD',
    'ietf-ipv6-router-advertisements@2016-11-04.yang': 'NETMOD',
    'ietf-ipv6-unicast-routing@2016-11-04.yang': 'NETMOD',
    'ietf-key-chain@2017-06-15.yang': 'RTGWG',
    'ietf-l3vpn-svc@2017-01-27.yang': 'L3SM',
    'ietf-lmap-common@2017-08-08.yang': 'LMAP',
    'ietf-lmap-control@2017-08-08.yang': 'LMAP',
    'ietf-lmap-report@2017-08-08.yang': 'LMAP',
    'ietf-netconf-acm@2012-02-22.yang': 'NETCONF',
    'ietf-netconf-monitoring@2010-10-04.yang': 'NETCONF',
    'ietf-netconf-notifications@2012-02-06.yang': 'NETCONF',
    'ietf-netconf-partial-lock@2009-10-19.yang': 'NETCONF',
    'ietf-netconf-time@2016-01-26.yang': 'N/A',
    'ietf-netconf-with-defaults@2011-06-01.yang': 'NETCONF',
    'ietf-netconf@2011-06-01.yang': 'NETCONF',
    'ietf-restconf-monitoring@2017-01-26.yang': 'NETCONF',
    'ietf-restconf@2017-01-26.yang': 'NETCONF',
    'ietf-routing@2016-11-04.yang': 'NETMOD',
    'ietf-snmp-common@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-community@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-engine@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-notification@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-proxy@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-ssh@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-target@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-tls@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-tsm@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-usm@2014-12-10.yang': 'NETMOD',
    'ietf-snmp-vacm@2014-12-10.yang': 'NETMOD',
    'ietf-snmp@2014-12-10.yang': 'NETMOD',
    'ietf-system@2014-08-06.yang': 'NETMOD',
    'ietf-template@2010-05-18.yang': 'NETMOD',
    'ietf-x509-cert-to-name@2014-12-10.yang': 'NETMOD',
    'ietf-yang-library@2016-06-21.yang': 'NETCONF',
    'ietf-yang-metadata@2016-08-05.yang': 'NETMOD',
    'ietf-yang-patch@2017-02-22.yang': 'NETCONF',
    'ietf-yang-smiv2@2012-06-22.yang': 'NETMOD',
    'ietf-yang-types@2010-09-24.yang': 'NETMOD',
    'ietf-yang-types@2013-07-15.yang': 'NETMOD',
}

NAMESPACE_MAP = (
    ('http://cisco.com/', 'cisco'),
    ('http://www.cisco.com/', 'cisco'),
    ('http://www.huawei.com/netconf', 'huawei'),
    ('http://openconfig.net/yang', 'openconfig'),
    ('http://tail-f.com/', 'tail-f'),
    ('http://yang.juniper.net/', 'juniper'),
    ('http://www.ciena.com/ns/yang/', 'ciena'),
    ('https://www.broadband-forum.org', 'bbf'),
    ('http://ackl.io/', 'acklio'),
    ('http://ni.com/ns', 'ni'),
    ('http://metroethernetforum.org/ns', 'mef'),
)

github_url = 'https://github.com'
GITHUB_RAW = 'https://raw.githubusercontent.com'
github_api = 'https://api.github.com'
MISSING_ELEMENT = 'missing element'
backup_date_format = '%Y-%m-%d_%H:%M:%S-UTC'

SDOS = ['bbf', 'etsi', 'ieee', 'ietf', 'mef', 'opendaylight', 'openconfig']
ORGANIZATIONS = [
    'mef',
    'ietf',
    'ieee',
    'etsi',
    'bbf',
    'openconfig',
    'tail-f',
    'opendaylight',
    'ciena',
    'cisco',
    'fujitsu',
    'huawei',
    'juniper',
    'nokia',
    'acklio',
]
SCHEMA_TYPES = [
    'typedef',
    'grouping',
    'feature',
    'identity',
    'extension',
    'rpc',
    'container',
    'list',
    'leaf-list',
    'leaf',
    'notification',
    'action',
]
OUTPUT_COLUMNS = [
    'name',
    'revision',
    'schema-type',
    'path',
    'module-name',
    'origin',
    'organization',
    'maturity',
    'dependents',
    'compilation-status',
    'description',
]
MODULE_PROPERTIES_ORDER = {
    'name': 1,
    'revision': 2,
    'organization': 3,
    'ietf': 4,
    'ietf-wg': 1,
    'namespace': 5,
    'schema': 6,
    'generated-from': 7,
    'maturity-level': 8,
    'document-name': 9,
    'author-email': 10,
    'reference': 11,
    'module-classification': 12,
    'compilation-status': 13,
    'compilation-result': 14,
    'prefix': 15,
    'yang-version': 16,
    'description': 17,
    'contact': 18,
    'module-type': 19,
    'belongs-to': 20,
    'tree-type': 21,
    'yang-tree': 22,
    'expires': 23,
    'expired': 24,
    'submodule': 25,
    'dependencies': 26,
    'dependents': 27,
    'semantic-version': 28,
    'derived-semantic-version': 29,
    'implementations': 30,
    'implementation': 1,
    'vendor': 1,
    'platform': 2,
    'software-version': 3,
    'software-flavor': 4,
    'os-version': 5,
    'feature-set': 6,
    'os-type': 7,
    'conformance-type': 8,
}


class JobLogStatuses(str, Enum):
    SUCCESS = 'Success'
    IN_PROGRESS = 'In Progress'
    FAIL = 'Fail'
