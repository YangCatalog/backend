---
title: API Reference

language_tabs: # must be one of https://git.io/vQNgJ
  - shell
  - python

toc_footers:
  - <a href='https://yangcatalog.org/create.php'>Sign Up to contribute for yangcatalog</a>
  - <a href='https://github.com/lord/slate'>Documentation Powered by Slate</a>

search: true
---

# Introduction

Welcome to the Yangcatalog API! You can use our API to access information on various yang modules in our database.
To test out the various endpoints on Postman, you can [download our Postman collection here](https://yangcatalog.org/downloadables/yangcatalog.postman_collection-v2.json)

We have language examples in Shell and Python! You can view code examples in the dark area to the right, and you can switch the programming language of the examples with the tabs in the top right.

This example API documentation page was created with [Slate](https://github.com/lord/slate). Feel free to edit it, create pull or create and issute request
if you find anything that doesn`t work as expected.

# Contribute

## Update model metadata

```python
import requests

url = 'https://yangcatalog.org/api/modules'
body = <data>
requests.put(url, body, auth=('admin', 'admin'),
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X PUT -H "Accept: application/json" -H "Content-type: application/json"
 --user admin:admin "https://yangcatalog.org/api/modules"
 --data '<data>'
```

> Make sure to replace `admin admin` with your name and password.

> The above command uses data like this:

```json
{
  "modules": {
     "module": [
     {
        "name": "example-jukebox",
        "revision": "2014-01-20",
        "organization": "example",
        "maturity-level": "ratified",
        "author-email": "foo@bar.com",
        "module-classification": "network-element",
        "source-file": {
          "repository": "foo",
          "owner": "bar",
          "path": "standard/ietf/DRAFT/example-jukebox.yang"
        }
      }
    ]
  }
}
```

> The above command returns JSON structured like this:

```json
{
  "info": "Verification successful",
  "job-id": "88bd8c4c-8809-4de8-85c8-39d522d4bcdf"
}
```

This endpoint serves to add and updated all the modules from provided
json as body of the request. It will parse all the modules on the
provided paths. Since this job takes some time the request will response
only with verification information and job-id on which you can
[track the job status](#get-job-status).

### HTTP Request

`PUT https://yangcatalog.org/api/modules`

<aside class="notice">
You must replace <code>admin admin</code> with your personal name password.
</aside>

### Body Parameters

Inside of the body we need to provide list of modules with following,
parameters for each module

Parameter | Description
--------- | -----------
name | Name of the yang module
revision | Revision of the yang module
organization | Organization of the yang module
maturity-level | ratified, adopted, initial not-applicable (more information at [yangcatalog RFC](https://tools.ietf.org/html/draft-clacla-netmod-model-catalog-03#section-2.5))
author-email | Email of the author that created this module
module-classification | network-service, network-element, unknown, not-applicable ([RFC8199](https://tools.ietf.org/html/rfc8199) YANG Module Classification)
source-file | Object with source file information
repository | Name of the repository
owner | Name of the owner of the repository
path | Path in the repository for the given yang module

## Add model metadata

```python
import requests

url = 'https://yangcatalog.org/api/modules'
body = <data>
requests.post(url, body, auth=('admin', 'admin'),
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 --user admin:admin "https://yangcatalog.org/api/modules"
 --data '<data>'
```

> Make sure to replace `admin admin` with your name and password.

> The above command uses data like this:

```json
{
  "modules": {
     "module": [
     {
        "name": "example-jukebox",
        "revision": "2014-01-20",
        "organization": "example",
        "maturity-level": "ratified",
        "author-email": "foo@bar.com",
        "module-classification": "network-element",
        "source-file": {
          "repository": "foo",
          "owner": "bar",
          "path": "standard/ietf/DRAFT/example-jukebox.yang"
        }
      }
    ]
  }
}
```

> The above command returns JSON structured like this:

```json
{
  "info": "Verification successful",
  "job-id": "88bd8c4c-8809-4de8-85c8-39d522d4bcdf"
}
```

This endpoint serves to add all the modules from provided
json as body of the request. If the module already exist with given name
and revision, module will not be updated or added, instead it will be
skipped not doing anything with that. Next it will parse all rest of the
modules on the provided paths. Since this job takes some time request
will response only with verification information and job-id on which you
can [track the job status](#get-job-status).

### HTTP Request

`POST https://yangcatalog.org/api/modules`

<aside class="notice">
You must replace <code>admin admin</code> with your personal name password.
</aside>

### Body Parameters

Inside of the body we need to provide list of modules with following,
parameters for each module

Parameter | Description
--------- | -----------
name | Name of the yang module
revision | Revision of the yang module
organization | Organization of the yang module
maturity-level | ratified, adopted, initial not-applicable (more information at [yangcatalog RFC](https://tools.ietf.org/html/draft-clacla-netmod-model-catalog-03#section-2.5))
author-email | Email of the author that created this module
module-classification | network-service, network-element, unknown, not-applicable ([RFC8199](https://tools.ietf.org/html/rfc8199) YANG Module Classification)
source-file | Object with source file information
repository | Name of the repository
owner | Name of the owner of the repository
path | Path in the repository for the given yang module

## Update implementation metadata

```python
import requests

url = 'https://yangcatalog.org/api/platforms'
body = <data>
requests.put(url, body, auth=('admin', 'admin'),
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X PUT -H "Accept: application/json" -H "Content-type: application/json"
 --user admin:admin "https://yangcatalog.org/api/platforms"
 --data '<data>'
```

> Make sure to replace `admin admin` with your name and password.

> The above command uses data like this:

```json
{
  "platforms" {
    "platform": [
      {
        "vendor": "example",
        "name": "baz",
        "module-list-file": {
           "type": "capabilities",
           "repository": "foo",
           "owner": "bar",
           "path": "vendor/example/baz/baz-netconf-capability.xml"
        },
        "platform-ids": [
           "BAZ4000", "BAZ4100"
        ],
        "software-flavor": "ALL",
        "software-version": "1.2.3",
        "os-type": "bazOS"
      }
    ]
  }
}
```

> The above command returns JSON structured like this:

```json
{
  "info": "Verification successful",
  "job-id": "88bd8c4c-8809-4de8-85c8-39d522d4bcdf"
}
```

This endpoint serves to add or update all the modules from provided json
path which should be path to the capabilities xml file or to the
yang-library file which is constructed according to [RFC7895](https://tools.ietf.org/html/rfc7895).
Next it will parse all the modules on the provided xml files. Since this
job takes some time request will response only with verification
information and job-id on which you can
[track the job status](#get-job-status).

### HTTP Request

`PUT https://yangcatalog.org/api/platforms`

<aside class="notice">
You must replace <code>admin admin</code> with your personal name password.
</aside>

### Body Parameters

Inside of the body we need to provide list of platforms with following,
parameters for each platform

Parameter | Description
--------- | -----------
vendor | Name of the vendor (example: cisco or ciena)
name | Platform on which this module is implemented
module-list-file | Object with source file information
type | capabilities or yang-library
repository | Name of the repository
owner | Name of the owner of the repository
path | Path in the repository for the given <type> file
platform-ids | The specific product ID or IDs to which this data applies
software-flavor | A variation of a specific version where YANG model support may be different
software-version | Name of the version of software
os-type | Type of the operating system using the module

## Add implementation metadata

```python
import requests

url = 'https://yangcatalog.org/api/platforms'
body = <data>
requests.post(url, body, auth=('admin', 'admin'),
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 --user admin:admin "https://yangcatalog.org/api/platforms"
 --data '<data>'
```

> Make sure to replace `admin admin` with your name and password.

> The above command uses data like this:

```json
{
  "platforms" {
    "platform": [
      {
        "vendor": "example",
        "name": "baz",
        "module-list-file": {
           "type": "capabilities",
           "repository": "foo",
           "owner": "bar",
           "path": "vendor/example/baz/baz-netconf-capability.xml"
        },
        "platform-ids": [
           "BAZ4000", "BAZ4100"
        ],
        "software-flavor": "ALL",
        "software-version": "1.2.3",
        "os-type": "bazOS"
      }
    ]
  }
}
```

> The above command returns JSON structured like this:

```json
{
  "info": "Verification successful",
  "job-id": "88bd8c4c-8809-4de8-85c8-39d522d4bcdf"
}
```

This endpoint serves to add all the modules from provided json path
which should be path to the capabilities xml file or to the yang-library
file which is constructed according to [RFC7895](https://tools.ietf.org/html/rfc7895).
This will only parse new capability files. If the file already exist it
will skip this file. Next it will parse all the modules on the provided
xml files. Since this job takes some time request will response only
with verification information and job-id on which you can
[track the job status](#get-job-status).

### HTTP Request

`POST https://yangcatalog.org/api/platforms`

<aside class="notice">
You must replace <code>admin admin</code> with your personal name password.
</aside>

### Body Parameters

Inside of the body we need to provide list of platforms with following,
parameters for each platform

Parameter | Description
--------- | -----------
vendor | Name of the vendor (example: cisco or ciena)
name | Platform on which this module is implemented
module-list-file | Object with source file information
type | capabilities or yang-library
repository | Name of the repository
owner | Name of the owner of the repository
path | Path in the repository for the given <type> file
platform-ids | The specific product ID or IDs to which this data applies
software-flavor | A variation of a specific version where YANG model support may be different
software-version | Name of the version of software
os-type | Type of the operating system using the module

## Delete models metadata

```python
import requests

url = 'https://yangcatalog.org/api/modules'
body = <data>
requests.delete(url, body, auth=('admin', 'admin'),
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X DELETE -H "Accept: application/json" -H "Content-type: application/json"
 --user admin:admin "https://yangcatalog.org/api/modules"
 --data '<data>'
```

> Make sure to replace `admin admin` with your name and password.

> The above command uses data like this:

```json
{
  "input" {
    "modules": [
      {
        "name": "<name>",
        "revision": "<revision>",
        "organization": "<organization>"
      }
    ]
  }
}
```

> The above command returns JSON structured like this:

```json
{
  "info": "Verification successful",
  "job-id": "88bd8c4c-8809-4de8-85c8-39d522d4bcdf"
}
```

This endpoint serves to remove all the modules from provided json modules.
Modules is a list of modules that contain main information about module,
which is name, revision, organization. Since this job takes some time
request will response only with verification information and job-id on
which you can [track the job status](#get-job-status).

### HTTP Request

`DELETE https://yangcatalog.org/api/modules`

<aside class="notice">
You must replace <code>admin admin</code> with your personal name password.
</aside>

### Body Parameters

Inside of the body we need to provide list of modules with following,
parameters for each platform

Parameter | Description
--------- | -----------
name | Name of the module
revision | Revision of the module
organization | Organization of the module

## Delete model metadata

```python
import requests

url = 'https://yangcatalog.org/api/modules/module/<name>,<revision>,<organization>'
requests.delete(url, auth=('admin', 'admin'),
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X DELETE -H "Accept: application/json" -H "Content-type: application/json"
 --user admin:admin "https://yangcatalog.org/api/modules/module/<name>,<revision>,<organization>"
```

> Make sure to replace `admin admin` with your name and password.

> The above command returns JSON structured like this:

```json
{
  "info": "Verification successful",
  "job-id": "88bd8c4c-8809-4de8-85c8-39d522d4bcdf"
}
```

This endpoint serves to remove the specific module provided on path.
Since this job takes some time request will response only with
verification information and job-id on which you can
[track the job status](#get-job-status).

### HTTP Request

`DELETE https://yangcatalog.org/api/modules/module/<name>,<revision>,<organization>`

<aside class="notice">
You must replace <code>admin admin</code> with your personal name password.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
name | Name of the module
revision | Revision of the module
organization | Organization of the module

## Delete implementation metadata

```python
import requests

url = 'https://yangcatalog.org/api/vendors/<path:value>'
requests.delete(url, auth=('admin', 'admin'),
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X DELETE -H "Accept: application/json" -H "Content-type: application/json"
 --user admin:admin "https://yangcatalog.org/api/vendors/<path:value>"
```

> Make sure to replace `admin admin` with your name and password.

> The above command returns JSON structured like this:

```json
{
  "info": "Verification successful",
  "job-id": "88bd8c4c-8809-4de8-85c8-39d522d4bcdf"
}
```

This endpoint serves to remove all the modules from provided path. Since
this job takes some time request will response only with verification
information and job-id on which you can [track the job status](#get-job-status).

### HTTP Request

`DELETE https://yangcatalog.org/api/vendors/<path:value>`

<aside class="notice">
You must replace <code>admin admin</code> with your personal name password.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
path:value | Path to a specific vendor modules you want to remove (example: cisco/xe/1632 would delete all 1632 xe cisco modules)

## Get job status

```python
import requests

url = 'https://yangcatalog.org/api/job/<job-id>'
requests.get(url, headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/job/<job-id>"
```

> The above command returns JSON structured like this:

```json
  {
    "info": {
      "job-id": "88bd8c4c-8809-4de8-85c8-39d522d4bcdf",
      "reason": null,
      "result": "In progress"
    }
  }
```

This endpoint serves to get job status.

### HTTP Request

`GET https://yangcatalog.org/api/job/<job-id>`

### URL Parameters

Parameter | Description
--------- | -----------
job-id | Id of the job provided as a response to any of the above requests

# Search

## Get whole catalog

```python
import requests

url = 'https://yangcatalog.org/api/search/catalog'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/search/catalog"
```

> The above command returns JSON-formatted modules data with all
the vendor implementation metadata

This endpoint serves to get all the modules with their vendor
implementation metadata

### HTTP Request

`GET https://yangcatalog.org/api/search/catalog`

<aside class="notice">
The catalog is quite large and growing all the time.
Returning the whole Catalog will pull down quite a bit of data.
</aside>

## Get all modules metadata

```python
import requests

url = 'https://yangcatalog.org/api/search/modules'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/search/modules"
```

> The above command returns JSON-formatted modules data

This endpoint serves to get all the modules metadata

### HTTP Request

`GET https://yangcatalog.org/api/search/modules`

<aside class="notice">
The catalog is quite large and growing all the time.
Returning the all the modules will pull down quite a bit of data.
</aside>

## Get all implementation metadata

```python
import requests

url = 'https://yangcatalog.org/api/search/vendors'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/search/vendors"
```

> The above command returns JSON-formatted vendor implementation metadata

This endpoint serves to get all the vendor implementation metadata

### HTTP Request

`GET https://yangcatalog.org/api/search/vendors`

<aside class="notice">
The catalog is quite large and growing all the time.
Returning all the implementation metadata will pull down quite a bit of data.
</aside>

## Get specific module

```python
import requests

url = 'https://yangcatalog.org/api/search/modules/<name>,<revision>,<organization>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/search/modules/<name>,<revision>,<organization>"
```

> The above command returns JSON-formatted module data like this:

```json
{
  "yang-catalog:module": {
    "name": "ietf-isis",
    "revision": "2018-08-09",
    "organization": "ietf",
    "namespace": "urn:ietf:params:xml:ns:yang:ietf-isis",
    "schema": "https://raw.githubusercontent.com/YangModels/yang/master/experimental/ietf-extracted-YANG-modules/ietf-isis@2018-08-09.yang",
    "generated-from": "not-applicable",
    "module-classification": "unknown",
    "compilation-status": "passed",
    "compilation-result": "Unknown",
    "prefix": "isis",
    "yang-version": "1.1",
    "description": "The YANG module defines a generic configuration model for\nIS-IS common across all of the vendor implementations.",
    "contact": "WG List:  &lt;mailto:isis-wg@ietf.org&gt;\n\nEditor:    Stephane Litkowski\n     &lt;mailto:stephane.litkowski@orange.com&gt;\n\n   Derek Yeung\n     &lt;mailto:derek@arrcus.com&gt;\n   Acee Lindem\n     &lt;mailto:acee@cisco.com&gt;\n   Jeffrey Zhang\n     &lt;mailto:zzhang@juniper.net&gt;\n   Ladislav Lhotka\n     &lt;mailto:llhotka@nic.cz&gt;\n   Yi Yang\n     &lt;mailto:yiya@cisco.com&gt;\n   Dean Bogdanovic\n     &lt;mailto:deanb@juniper.net&gt;\n   Kiran Agrahara Sreenivasa\n     &lt;mailto:kkoushik@brocade.com&gt;\n   Yingzhen Qu\n     &lt;mailto:yiqu@cisco.com&gt;\n           Jeff Tantsura\n             &lt;mailto:jefftant.ietf@gmail.com&gt;\n\n",
    "module-type": "module",
    "tree-type": "nmda-compatible",
    "yang-tree": "https://yangcatalog.org/api/services/tree/ietf-isis@2018-08-09.yang",
    "expired": "not-applicable",
    "dependencies": [
      {
        "name": "iana-routing-types"
      },
      {
        "name": "ietf-bfd-types"
      },
      {
        "name": "ietf-inet-types"
      },
      {
        "name": "ietf-interfaces"
      },
      {
        "name": "ietf-key-chain"
      },
      {
        "name": "ietf-routing"
      },
      {
        "name": "ietf-routing-types"
      },
      {
        "name": "ietf-yang-types"
      }
    ],
    "dependents": [
      {
        "name": "ietf-bier"
      },
      {
        "name": "ietf-isis-ppr"
      },
      {
        "name": "ietf-isis-sr"
      },
      {
        "name": "ietf-isis-srv6"
      },
      {
        "name": "ietf-rip"
      }
    ],
    "derived-semantic-version": "6.0.0"
  }
}
```

This endpoint serves to get specific module metadata

### HTTP Request

`GET https://yangcatalog.org/api/search/modules/<name>,<revision>,<organization>`

### URL Parameters

Parameter | Description
--------- | -----------
name | Name of the module
revision | Revision of the module
organization | Organization of the module

## Get implementation metadata

```python
import requests

url = 'https://yangcatalog.org/api/search/vendors/<path:value>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/search/vendors/<path:value>"
```

> The above command returns JSON-formatted implementation metadata

This endpoint serves to get specific module metadata

### HTTP Request

`GET https://yangcatalog.org/api/search/vendors/<path:value>`

### URL Parameters

Parameter | Description
--------- | -----------
path:value | Path to a specific vendor modules you want to remove (example: cisco/xe/1632 would delete all 1632 xe cisco modules)

## Filter leaf data

```python
import requests

url = 'https://yangcatalog.org/api/search/<path:value>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/search/<path:value>"
```

> The above command with <path:value> = ietf/ietf-wg/netmod returns JSON-formatted yang modules like this:

```json
{
  "yang-catalog:modules": {
    "module": [
      {
        "name": "example-iana-if-type",
        "revision": "2017-06-27",
        "organization": "ietf",
        "ietf": {
            "ietf-wg": "netmod"
        },
        "namespace": "urn:ietf:params:xml:ns:yang:example-iana-if-type",
        "schema": "https://raw.githubusercontent.com/YangModels/yang/master/experimental/ietf-extracted-YANG-modules/example-iana-if-type@2017-06-27.yang",
        "generated-from": "not-applicable",
        "maturity-level": "initial",
        "document-name": "draft-wilton-netmod-interface-properties-00.txt",
        "author-email": "draft-wilton-netmod-interface-properties@ietf.org",
        "reference": "http://datatracker.ietf.org/doc/draft-wilton-netmod-interface-properties",
        "module-classification": "unknown",
        "compilation-status": "unknown",
        "compilation-result": "https://yangcatalog.org/results/example-iana-if-type@2017-06-27_ietf.html",
        "prefix": "ianaift",
        "yang-version": "1.1",
        "description": "This example module illustrates how iana-if-type.yang could\nbe extended to use interface properties.",
        "contact": "",
        "module-type": "module",
        "tree-type": "not-applicable",
        "yang-tree": "https://yangcatalog.org/api/services/tree/example-iana-if-type@2017-06-27.yang",
        "expired": "not-applicable",
        "dependencies": [
          {
            "name": "iana-if-property-type",
            "schema": "https://raw.githubusercontent.com/YangModels/yang/master/experimental/ietf-extracted-YANG-modules/iana-if-property-type@2017-06-27.yang"
          },
          {
            "name": "ietf-interfaces",
            "schema": "https://raw.githubusercontent.com/YangModels/yang/master/experimental/ietf-extracted-YANG-modules/ietf-interfaces@2018-01-09.yang"
          }
        ],
        "derived-semantic-version": "1.0.0"
      },
      {
        "name": "example-ietf-interfaces",
        "revision": "2017-06-27",
        "organization": "ietf",
        "ietf": {
            "ietf-wg": "netmod"
        .
        .
        .
```

This endpoint serves to get all the modules that correspond with provided
keyword

### HTTP Request

`GET https://yangcatalog.org/api/search/<path:value>`

### URL Parameters

Parameter | Description
--------- | -----------
path:value | Path to a specific vendor modules you want to remove (example: cisco/xe/1632 would delete all 1632 xe cisco modules)

### Query Parameters

Parameter | Default | Description
--------- | ------- | -----------
latest-revision | false | If set to true, the result will filter only for latest revision of found yang modules.

# RPC search

## Filter several leafs

```python
import requests

body = <data>
url = 'https://yangcatalog.org/api/search-filter'
requests.post(url, body, headers={'Accept': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 --data '<data>'
 "https://yangcatalog.org/api/search-filter"
```

> The above command uses data like this:

```json
{
  "input":{
    "generated-from": "mib",
    "implementations":{
      "implementation":[
        {
          "vendor":"cisco",
          "software-version":"16.8.1"
        }
      ]
    }
  }
}
```

> The above command returns JSON-formatted yang modules like this:

```json
{
  "yang-catalog:modules": {
    "module": [
      {
        "name": "ATM-FORUM-TC-MIB",
        "revision": "1970-01-01",
        "organization": "ietf",
        "namespace": "urn:ietf:params:xml:ns:yang:smiv2:ATM-FORUM-TC-MIB",
        "schema": "https://raw.githubusercontent.com/YangModels/yang/master/vendor/cisco/xe/1681/MIBS/ATM-FORUM-TC-MIB.yang",
        "generated-from": "mib",
        "module-classification": "unknown",
        "compilation-status": "failed",
        "compilation-result": "https://yangcatalog.org/results/ATM-FORUM-TC-MIB@1970-01-01_ietf.html",
        "prefix": "ATM-FORUM-TC-MIB",
        "yang-version": "1.0",
        "module-type": "module",
        "tree-type": "not-applicable",
        "yang-tree": "https://yangcatalog.org/api/services/tree/ATM-FORUM-TC-MIB@1970-01-01.yang",
        "expired": "not-applicable",
        "dependencies": [
          {
            "name": "ietf-yang-smiv2",
            "schema": "https://raw.githubusercontent.com/YangModels/yang/master/standard/ietf/RFC/ietf-yang-smiv2@2012-06-22.yang"
          }
        ],
        "dependents": [
          {
            "name": "CISCO-ATM-QOS-MIB",
            "revision": "2002-06-10",
            "schema": "https://raw.githubusercontent.com/YangModels/yang/master/vendor/cisco/xe/1681/MIBS/CISCO-ATM-QOS-MIB.yang"
          }
        ],
        "derived-semantic-version": "1.0.0",
        "implementations": {
          "implementation": [
            {
              "vendor": "cisco",
              "platform": "ASR1000",
              "software-version": "16.3.1",
              "software-flavor": "ALL",
              "os-ver
        .
        .
        .
```

This endpoint serves to get all the modules that contains all the leafs
with data as provided by <data> in body of the request

### HTTP Request

`POST https://yangcatalog.org/api/search-filter`

### Query Parameters

Parameter | Default | Description
--------- | ------- | -----------
latest-revision | false | If set to true, the result will filter only for latest revision of found yang modules.

### Body Parameters

Inside of the body we need to start with "input" to which we provide all
the leafs with data that need to be filtered out of yangcatalog.
All the leafs can be found in [draft-clacla-netmod-model-catalog-03 section 2-2](https://tools.ietf.org/html/draft-clacla-netmod-model-catalog-03#section-2.2)

## Get common modules

```python
import requests

body = <data>
url = 'https://yangcatalog.org/api/get-common'
requests.post(url, body, headers={'Accept': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 --data '<data>'
 "https://yangcatalog.org/api/get-common"
```

> The above command uses data like this:

```json
{
  "input":{
    "first":{
      "implementations":{
        "implementation":[
          {
            "vendor":"cisco",
            "software-version":"6.1.1",
            "platform":"asr9k-px"
          }
        ]
      }
    },
    "second":{
      "implementations":{
        "implementation":[
          {
            "vendor":"cisco",
            "software-version":"6.1.3",
            "platform":"asr9k-px"
          }
        ]
      }
    }
  }
}
```

> The above command returns JSON-formatted yang modules like this:

```json
{
  "output": [
    {
      "name": "Cisco-IOS-XR-Ethernet-SPAN-cfg",
      "revision": "2015-11-09",
      "organization": "cisco",
      "namespace": "http://cisco.com/ns/yang/Cisco-IOS-XR-Ethernet-SPAN-cfg",
      "schema": "https://raw.githubusercontent.com/YangModels/yang/master/vendor/cisco/xr/632/Cisco-IOS-XR-Ethernet-SPAN-cfg.yang",
      "generated-from": "native",
      "module-classification": "unknown",
      "compilation-status": "failed",
      "compilation-result": "https://yangcatalog.org/results/Cisco-IOS-XR-Ethernet-SPAN-cfg@2015-11-09_cisco.html",
      "prefix": "ethernet-span-cfg",
      "yang-version": "1.0",
      "description": "This module contains a collection of YANG definitions\nfor Cisco IOS-XR Ethernet-SPAN package configuration.\n\nThis module contains definitions\nfor the following management objects:\n  span-monitor-session: none\n\nThis YANG module augments the\n  Cisco-IOS-XR-ifmgr-cfg,\n  Cisco-IOS-XR-l2vpn-cfg\nmodules with configuration data.\n\nCopyright (c) 2013-2017 by Cisco Systems, Inc.\nAll rights reserved.",
      "contact": "Cisco Systems, Inc.\nCustomer Service\n\nPostal: 170 West Tasman Drive\nSan Jose, CA 95134\n\nTel: +1 800 553-NETS\n\nE-mail: cs-yang@cisco.com",
      "module-type": "module",
      "tree-type": "nmda-compatible",
      "yang-tree": "https://yangcatalog.org/api/services/tree/Cisco-IOS-XR-Ethernet-SPAN-cfg@2015-11-09.yang",
      "expired": "not-applicable",
      "dependencies": [
        {
          "name": "Cisco-IOS-XR-Ethernet-SPAN-datatypes",
          "schema": "https://raw.githubusercontent.com/YangModels/yang/master/vendor/cisco/xr/632/Cisco-IOS-XR-Ethernet-SPAN-datatypes.yang"
        },
        {
          "name": "Cisco-IOS-XR-ifmgr-cfg",
          "schema": "https://raw.githubusercontent.com/YangModels/yang/master/vendor/cisco/xr/632/Cisco-IOS-XR-ifmgr-cfg.yang"
        },
        {
          "name": "Cisco-IOS-XR-l2vpn-cfg",
          "schema": "https://raw.githubusercontent.com/YangModels/yang/master/vendor/cisco/xr/632/Cisco-IOS-XR-l2vpn-cfg.yang"
        },
        {
          "name": "Cisco-IOS-XR-types",
          "schema": "https://raw.githubusercontent.com/YangModels/yang/master/vendor/cisco/xr/632/Cisco-IOS-XR-types.yang"
        },
        {
          "name": "ietf-inet-types",
          "schema": "https://raw.githubusercontent.com/YangModels/yang/master/vendor/cisco/xr/632/ietf-inet-types.yang"
        }
      ],
      "derived-semantic-version": "1.0.0",
      "implementations": {
        "implementation": [
          {
            "vendor": "cisco",
            "platform": "asr9k",
            "software-version": "632",
            "software-flavor": "ALL",
    .
    .
    .
```

This endpoint serves to get all the common modules out of two different filtering
by leafs with data provided by <data> in body of the request

### HTTP Request

`POST https://yangcatalog.org/api/get-common`

### Query Parameters

Parameter | Default | Description
--------- | ------- | -----------
latest-revision | false | If set to true, the result will filter only for latest revision of found yang modules.

### Body Parameters

Inside of the body we need to start with "input" container which needs
to contain containers "first" and "second" to which we provide all the leafs
with data that need to be filtered out of yangcatalog. All the leafs can
be found in [draft-clacla-netmod-model-catalog-03 section 2-2](https://tools.ietf.org/html/draft-clacla-netmod-model-catalog-03#section-2.2)

# Services

## Get tree

```python
import requests

url = 'https://yangcatalog.org/api/services/tree/<name>@<revision>.yang'
requests.get(url, body, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/services/tree/<name>@<revision>.yang"
```

> The above command returns HTML-formatted tree of the module like this:

```html
<html><body><pre>module: example-ietf-interfaces
  +--ro interfaces-state
     +--ro interface* [name]
        +--ro name          string
        +--ro type          identityref
        +--ro statistics
           +--ro discontinuity-time    yang:date-and-time
           +--ro in-octets?            yang:counter64
           +--ro in-unicast-pkts?      yang:counter64
           +--ro in-broadcast-pkts?    yang:counter64
           +--ro in-multicast-pkts?    yang:counter64
</pre></body></html>
```

This endpoint serves to get tree of a specific yang module

### HTTP Request

`GET https://yangcatalog.org/api/services/tree/<name>@<revision>.yang`

### URL Parameters

Parameter | Description
--------- | -----------
name | Name of the yang file
revision | Revision of the yang file

## Get schema of the module

```python
import requests

url = 'https://yangcatalog.org/api/services/reference/<name>@<revision>.yang'
requests.get(url, body, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/services/reference/<name>@<revision>.yang"
```

> The above command returns HTML-formatted schema of the module like this:

```html
<html><body><pre>module ietf-te-device {

  namespace "urn:ietf:params:xml:ns:yang:ietf-te-device";

  /* Replace with IANA when assigned */
  prefix "te-dev";

  /* Import TE generic types */
  import ietf-te {
    prefix te;
  }
  .
  .
  .
</pre></body></html>
```

This endpoint serves to get reference schema of a specific yang module

### HTTP Request

`GET https://yangcatalog.org/api/services/reference/<name>@<revision>.yang`

### URL Parameters

Parameter | Description
--------- | -----------
name | Name of the yang file
revision | Revision of the yang file

## Get semantic differences

```python
import requests

body = <data>
url = 'https://yangcatalog.org/api/check-semantic-version'
requests.post(url, body, headers={'Accept': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 --data '<data>'
 "https://yangcatalog.org/api/check-semantic-version"
```

> The above command uses data like this:

```json
{
  "input":{
    "first":{
      "implementations":{
        "implementation":[
          {
            "vendor":"cisco",
            "software-version":"6.1.1",
            "platform":"asr9k-px"
          }
        ]
      }
    },
    "second":{
      "implementations":{
        "implementation":[
          {
            "vendor":"cisco",
            "software-version":"6.1.3",
            "platform":"asr9k-px"
          }
        ]
      }
    }
  }
}
```

> The above command returns JSON-formatted output like this:

```json
{
  "output": [
    {
      "derived-semantic-version-results": "Both modules failed compilation",
      "name": "Cisco-IOS-XR-bundlemgr-cfg",
      "new-derived-semantic-version": "2.0.0",
      "old-derived-semantic-version": "1.0.0",
      "organization": "cisco",
      "revision-new": "2016-12-16",
      "revision-old": "2016-05-12",
      "yang-module-diff": "https://yangcatalog.org/api//services/diff-file/file1=Cisco-IOS-XR-bundlemgr-cfg@2016-05-12/file2=Cisco-IOS-XR-bundlemgr-cfg@2016-12-16"
    },
    {
      "derived-semantic-version-results": "pyang --check-update-from output: https://yangcatalog.org/api//services/file1=Cisco-IOS-XR-snmp-test-trap-act@2016-10-25/check-update-from/file2=Cisco-IOS-XR-snmp-test-trap-act@2016-04-17",
      "name": "Cisco-IOS-XR-snmp-test-trap-act",
      "new-derived-semantic-version": "2.0.0",
      "old-derived-semantic-version": "1.0.0",
      "organization": "cisco",
      "revision-new": "2016-10-25",
      "revision-old": "2016-04-17",
      "yang-module-diff": "https://yangcatalog.org/api//services/diff-file/file1=Cisco-IOS-XR-snmp-test-trap-act@2016-04-17/file2=Cisco-IOS-XR-snmp-test-trap-act@2016-10-25",
      "yang-module-pyang-tree-diff": "https://yangcatalog.org/api//services/diff-tree/file1=Cisco-IOS-XR-snmp-test-trap-act@2016-04-17/file2=Cisco-IOS-XR-snmp-test-trap-act@2016-10-25"    },
    {
      "derived-semantic-version-results": "Both modules failed compilation",
      "name": "Cisco-IOS-XR-qos-ma-oper",
    .
    .
    .
```

This endpoint serves to get output from pyang tool with option --check-update-from
for all the modules between <first> and <second> filter. If module
compilation failed it will give you only link to get diff in between
two yang modules. if check-update-from has an output it will provide tree
diff and output of the pyang together with diff between two files

### HTTP Request

`POST https://yangcatalog.org/api/check-semantic-version`

### Body Parameters

Inside of the body we need to start with "input" container which needs
to contain containers "first" and "second" to which we provide all the leafs
with data that need to be filtered out of yangcatalog. All the leafs can
be found in [draft-clacla-netmod-model-catalog-03 section 2-2](https://tools.ietf.org/html/draft-clacla-netmod-model-catalog-03#section-2.2)

## Get file difference

```python
import requests

url = 'https://yangcatalog.org/api/services/diff-file/file1=<f1>@<r1>/file2=<f2>@<r2>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/services/diff-file/file1=<f1>@<r1>/file2=<f2>@<r2>"
```

> The above command returns HTML-formatted error messages like this:

```html
<html><body>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"> 
<!-- Generated by rfcdiff 1.47: rfcdiff  --> 
<!-- <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional" > -->
<!-- System: Linux ietfa 4.4.143-65-default #1 SMP Tue Aug 14 09:18:29 UTC 2018 (4e090cc) x86_64 x86_64 x86_64 GNU/Linux --> 
<!-- Using awk: /usr/bin/gawk: GNU Awk 4.1.3, API: 1.1 --> 
<!-- Using diff: /usr/bin/diff: diff (GNU diffutils) 3.3 --> 
<!-- Using wdiff: /usr/bin/wdiff: wdiff (GNU wdiff) 1.2.2 --> 
<html xmlns="http://www.w3.org/1999/xhtml"> 
<head> 
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /> 
  <meta http-equiv="Content-Style-Type" content="text/css" /> 
  <title>Diff: schema1.txt - schema2.txt</title> 
  <style type="text/css"> 
    body    { margin: 0.4ex; margin-right: auto; } 
    tr      { } 
    .
    .
    .
```

This endpoint serves to get diff of the two yang modules

### HTTP Request

`GET https://yangcatalog.org/api/services/diff-file/file1=<f1>@<r1>/file2=<f2>@<r2>`

### URL Parameters

Parameter | Description
--------- | -----------
f1 | Name of the first module
r1 | Revision of the first module
f2 | Name of the second module
r2 | Revision of the second module

## Get tree difference

```python
import requests

url = 'https://yangcatalog.org/api/services/diff-tree/file1=<f1>@<r1>/file2=<f2>@<r2>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/services/diff-tree/file1=<f1>@<r1>/file2=<f2>@<r2>"
```

> The above command returns HTML-formatted error messages like this:

```html
<html><body>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"> 
<!-- Generated by rfcdiff 1.47: rfcdiff  --> 
<!-- <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional" > -->
<!-- System: Linux ietfa 4.4.143-65-default #1 SMP Tue Aug 14 09:18:29 UTC 2018 (4e090cc) x86_64 x86_64 x86_64 GNU/Linux --> 
<!-- Using awk: /usr/bin/gawk: GNU Awk 4.1.3, API: 1.1 --> 
<!-- Using diff: /usr/bin/diff: diff (GNU diffutils) 3.3 --> 
<!-- Using wdiff: /usr/bin/wdiff: wdiff (GNU wdiff) 1.2.2 --> 
<html xmlns="http://www.w3.org/1999/xhtml"> 
<head> 
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /> 
  <meta http-equiv="Content-Style-Type" content="text/css" /> 
  <title>Diff: schema1.txt - schema2.txt</title> 
  <style type="text/css"> 
    body    { margin: 0.4ex; margin-right: auto; } 
    tr      { }
    .
    .
    .
```

This endpoint serves to get tree diff of the two yang modules

### HTTP Request

`GET https://yangcatalog.org/api/services/diff-tree/file1=<f1>@<r1>/file2=<f2>@<r2>`

### URL Parameters

Parameter | Description
--------- | -----------
f1 | Name of the first module
r1 | Revision of the first module
f2 | Name of the second module
r2 | Revision of the second module

## Get semantic difference

```python
import requests

url = 'https://yangcatalog.org/api/services/file1=<f1>@<r1>/check-update-from/file2=<f2>@<r2>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/services/file1=<f1>@<r1>/check-update-from/file2=<f2>@<r2>"
```

> The above command returns HTML-formatted error messages like this:

```html
<html><body><pre>/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:289: error: the mandatory 'true' is illegally added
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:308: error: the mandatory 'true' is illegally added
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:314: error: the leaf 'address', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:305 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:314: error: the leaf 'ifindex', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:310 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:339: error: the leaf 'entity-id', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:325 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:339: error: the leaf 'entity-index', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:333 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:339: error: the leaf 'peer-id', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:340 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:377: error: the leaf 'index', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:355 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:377: error: the leaf 'instance', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:362 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:377: error: the leaf 'source', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:369 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:377: error: the leaf 'destination', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:374 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:416: error: the leaf 'index', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:385 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:416: error: the leaf 'instance', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:392 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:416: error: the leaf 'source', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:399 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:416: error: the leaf 'destination', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:404 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:456: error: the leaf 'index', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:416 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:456: error: the leaf 'instance', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:423 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:456: error: the leaf 'source', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:430 is illegally removed
/home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-10-25.yang:456: error: the leaf 'destination', defined at /home/miroslav/cache/backup_files/Cisco-IOS-XR-snmp-test-trap-act@2016-04-17.yang:434 is illegally removed
</pre></body></html>
```

This endpoint serves to get output from pyang tool with option --check-update-from
in between two modules provided in path of the request

### HTTP Request

`GET https://yangcatalog.org/api/services/file1=<f1>@<r1>/check-update-from/file2=<f2>@<r2>`

### URL Parameters

Parameter | Description
--------- | -----------
f1 | Name of the first module
r1 | Revision of the first module
f2 | Name of the second module
r2 | Revision of the second module

## Get single leaf data

```python
import requests

body = <data>
url = 'https://yangcatalog.org/api/search-filter/<leaf>'
requests.post(url, body, headers={'Accept': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 --data '<data>'
 "https://yangcatalog.org/api/search-filter/<leaf>"
```

> The above command uses data like this:

```json
{
  "input":{
    "implementations":{
      "implementation":[
        {
          "vendor":"cisco",
          "software-version":"6.4.1"
        }
      ]
    }
  }
}
```

> The above command returns JSON-formatted output like this:

```json
{
  "output": {
    "author-email": [
      "draft-openconfig-netmod-model-catalog@ietf.org"
    ]
  }
}
```

This endpoint serves to get list of specified <leaf> in filtered set
of modules. Filter is specified in body of the request

### HTTP Request

`POST https://yangcatalog.org/api/search-filter/<leaf>`

### Body Parameters

Inside of the body we need to start with "input" to which we provide all
the leafs with data that need to be filtered out of yangcatalog.
All the leafs can be found in [draft-clacla-netmod-model-catalog-03 section 2-2](https://tools.ietf.org/html/draft-clacla-netmod-model-catalog-03#section-2.2)
In this request there is one option data that can be inserted in called
"recursive". If set to true it will look for all dependencies of the
module and search for <leaf> data in those too.

# Internal

## Yangsuite redirect

```python
import requests

url = 'https://yangcatalog.org/api/yangsuite/<id>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/yangsuite/<id>"
```

> The above command should redirect you to yangsuite main page
with predefined yang modules and yangsuite user

This endpoint serves to redirect user to yangsuite main page with
predefined yang modules and yangsuite user. This link is generated
with every [search of specific yang module](#get-specific-module) if
YANGSUITE header is set to true. That way you ll receive <id> together
with yang module response.

### HTTP Request

`GET https://yangcatalog.org/api/yangsuite/<id>`

## Trigger ietf pull

```python
import requests

url = 'https://yangcatalog.org/api/ietf'
requests.get(url, auth=('admin', 'admin'), headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 --user admin:admin "https://yangcatalog.org/api/ietf"
```

> Make sure to replace `admin admin` with your name and password.

> The above command should trigger automatic ietf pull of all new
yang modules

This endpoint serves to run two different process:
 
1. draftPullLocal.py
2. openconfigPullLocall.py

These scripts serves as a automated tool to parse and populate all
the new openconfig yang modules and ietf DRAFT and RFC yang modules
to yangcatalog. Since this job takes some time the request will response
only with verification information and job-id on which you can
[track the job status](#get-job-status).

### HTTP Request

`GET https://yangcatalog.org/api/ietf`

<aside class="notice">
You must replace <code>admin admin</code> with your personal name password.
</aside>

## Travis check

This endpoint is used by travis. When a pull request by yang-catalog
user was created travis job runs and at the end it calls this api.
This endpoint will merge the pull request automatically if job didn`t
fail.

### HTTP Request

`POST https://yangcatalog.org/api/checkComplete`

Authorization is done using HTTP_SIGNATURE from the payload provided
by travis request

## Yang search and impact analysis tool

This endpoint is used by yang search and impact analysis tool to 
through the YANG keyword index for a given search pattern. The arguments
are a payload specifying search options and filters.

### HTTP Request

`POST https://yangcatalog.org/api/index/search`

## Load api cache

```python
import requests

url = 'https://yangcatalog.org/api/load-cache'
requests.post(url, auth=('admin', 'admin'), headers={'Accept': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 --user admin:admin "https://yangcatalog.org/api/load-cache"
```

> Make sure to replace `admin admin` with your name and password.

> The above command should trigger loading a cache api not blocking an
api

This endpoint serves to reload api cached modules after new modules have
been added to the yangcatalog. This should be a non-blocking code. There
are two caches create which should be identical and one of them should
always be available for the users

### HTTP Request

`GET https://yangcatalog.org/api/load-cache`

<aside class="notice">
You must replace <code>admin admin</code> with your personal name password.
</aside>

## Get Contributors

```python
import requests

url = 'https://yangcatalog.org/api/contributors'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/contributors"
```

> The above command should return all organizations that contributed
with yang modules to yangcatalog

This endpoint serves to provide with all the organizations that
contributed with yang modules to yangcatalog

### HTTP Request

`GET https://yangcatalog.org/api/contributors`
