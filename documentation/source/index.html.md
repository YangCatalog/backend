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
To test out the various endpoints on Postman, you can [download our Postman collection here](https://yangcatalog.org/downloadables/yangcatalog.postman_collection.json)

We have language examples in Shell and Python! You can view code examples in the dark area to the right, and you can switch the programming language of the examples with the tabs in the top right.

This example API documentation page was created with [Slate](https://github.com/lord/slate). Feel free to edit it, create pull or create and issute request
if you find anything that doesn`t work as expected.

# Contribute

This section is for users who wants to directly contribute with some yang modules to yangcatalog.org database without using YangModels/yang repository, but
adding files from your own repository instead. For this you need to have access credentials which you ll create by [creating an account](https://www.yangcatalog.org/create.html) in
yangcatalog.org. Full description on how to proceed can be found on [contribute page](https://www.yangcatalog.org/contribute.html)

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

This endpoint serves to get the job status which can be either 'Failed', 'In progress', or 'Finished successfully'.

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

## Get organization platform list

```python
import requests

url = 'https://yangcatalog.org/api/search/vendor/<org>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/search/vendor/<org>"
```

> The above command returns JSON-formatted implementation metadata

```json
{
    "IOS-XE": {
        "16.10.1": [
            "CAT9300",
            "IR1101",
            "ASR1000",
            "ASR920",
            "ISR4000",
            "NCS520",
            "ISR1000",
            "CSR1000V",
            "ASR900",
            "CAT9500",
            "CAT9400",
            "NCS4200",
            "CBR-8",
            "CAT9800"
        ],
        "16.11.1": [
            "CAT3650",
            "IE3x00",
            "CAT9300",
            "CAT9200",
        .
        .
        .
```

This endpoint serves to get all the platforms where specific organization contains some yang modules.

### HTTP Request

`GET https://yangcatalog.org/api/search/vendor/<org>`

### URL Parameters

Parameter | Description
--------- | -----------
org | organization that you are trying to search for (example: cisco would get you all platforms with cisco modules)

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

## Compare two searches

```python
import requests

body = <data>
url = 'https://yangcatalog.org/api/compare'
requests.post(url, body, headers={'Accept': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 --data '<data>'
 "https://yangcatalog.org/api/compare"
```

> The above command uses data like this:

```json
{
  "input":{
    "old":{
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
    "new":{
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
            "compilation-result": "https://yangcatalog.org/results/Cisco-IOS-XE-umbrella@2017-08-30_cisco.html",
            "compilation-status": "failed",
            "contact": "Cisco Systems, Inc.\nCustomer Service\n\nPostal: 170 W Tasman Drive\nSan Jose, CA 95134\n\nTel: +1 1800 553-NETS\n\nE-mail: cs-yang@cisco.com",
            "dependencies": [
                {
                    "name": "Cisco-IOS-XE-native",
                    "schema": "https://raw.githubusercontent.com/yangmodels/yang/master/vendor/cisco/xe/1662/Cisco-IOS-XE-native.yang"
                },
                {
                    "name": "ietf-inet-types",
                    "schema": "https://raw.githubusercontent.com/yangmodels/yang/master/vendor/cisco/xe/1662/ietf-inet-types.yang"
                }
            ],
            "derived-semantic-version": "1.0.0",
            "description": "Cisco XE Native Umbrella Yang model.\nCopyright (c) 2017 by Cisco Systems, Inc.\nAll rights reserved.",
            "expired": "not-applicable",
            "generated-from": "native",
            "implementations": {
                "implementation": [
                    {
                        "conformance-type": "implement",
                        "feature-set": "ALL",
                        "os-type": "IOS-XE",
                        "os-version": "16.6.2",
                        "platform": "CSR1000V",
                        "software-flavor": "ALL",
                        "software-version": "16.6.2",
                        "vendor": "cisco"
                    },
                    {
                        "conformance-type": "implement",
                        "feature-set": "ALL",
                        "os-type": "IOS-XE",
                        "os-version": "16.6.2",
                        "platform": "ISR4000",
                        "software-flavor": "ALL",
                        "software-version": "16.6.2",
                        "vendor": "cisco"
                    }
                ]
            },
            "maturity-level": "not-applicable",
            "module-classification": "unknown",
            "module-type": "module",
            "name": "Cisco-IOS-XE-umbrella",
            "namespace": "http://cisco.com/ns/yang/Cisco-IOS-XE-umbrella",
            "organization": "cisco",
            "prefix": "ios-umbrella",
            "reason-to-show": "New module",
            "revision": "2017-08-30",
            "schema": "https://raw.githubusercontent.com/YangModels/yang/0aa291b720ee6f013966f9bcbea9375671457ee9/vendor/cisco/xe/1662/Cisco-IOS-XE-umbrella.yang",
            "tree-type": "nmda-compatible",
            "yang-tree": "https://yangcatalog.org/api/services/tree/Cisco-IOS-XE-umbrella@2017-08-30.yang",
            "yang-version": "1.0"
        },
    .
    .
    .
```

This endpoint serves to compare and find different modules out of two different filtering
by leafs with data provided by <data> in body of the request. Output contains module metadata
with reason-to-show data as well which can be showing either 'New module' or 'Different revision'

### HTTP Request

`POST https://yangcatalog.org/api/compare`

### Query Parameters

Parameter | Default | Description
--------- | ------- | -----------
latest-revision | false | If set to true, the result will filter only for latest revision of found yang modules.

### Body Parameters

Inside of the body we need to start with "input" container which needs
to contain containers "new" and "old" to which we provide all the leafs
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

## Get update difference

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

## Get raw module

```python
import requests

url = 'https://yangcatalog.org/api/services/reference/<f1>@<r1>.yang'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/services/reference/<f1>@<r1>.yang"
```

> The above command returns HTML-formatted raw module like this:

```html
<html>

<body>
	<pre>module ietf-mpls {
  yang-version 1.1;
  namespace "urn:ietf:params:xml:ns:yang:ietf-mpls";

  /* Replace with IANA when assigned */

  prefix mpls;

  import ietf-routing {
    prefix rt;
    reference
      "RFC8349: A YANG Data Model for Routing Management";
  }
  import ietf-routing-types {
    prefix rt-types;
    reference
      "RFC8294:Common YANG Data Types for the Routing Area";
  }
  import ietf-yang-types {
    prefix yang;
    reference
      "RFC6991: Common YANG Data Types";
  }
  import ietf-interfaces {
    prefix if;
    reference
      "RFC8343: A YANG Data Model for Interface Management";
  }

  organization
    "IETF MPLS Working Group";
  contact
    "WG Web:   <http://tools.ietf.org/wg/mpls/>
.
.
.
```

This endpoint serves to get raw yang module in html form

### HTTP Request

`GET https://yangcatalog.org/api/services/reference/<f1>@<r1>.yang`

### URL Parameters

Parameter | Description
--------- | -----------
f1 | Name of the first module
r1 | Revision of the first module

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

## New vendor modules added

This endpoint is used within github. Whenever something is merged to [YangModles/yang](https://github.com/YangModels/yang) github repository this endpoint is
triggered and checks if there is an updated platform-metadata.json file which is then used withing [populate.py](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/populate.py) script.

### HTTP Request

`POST https://yangcatalog.org/api/check-platform-metadata`

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

# ADMIN

The following endpoints are only for admin UI and you need to be signed in to ietf account using single sign on to be able
to use any of the following endpoints. Once signed in and token is aquired you will be able to create these requests.

The admin UI serves to authorized IETF personel only who have access to manage users read through log files and all
the yangcatalog files which can be deleted update or read by them.

## Login

```python
import requests

url = 'https://yangcatalog.org/api/admin/login'
requests.get(url, headers={'Accept': 'application/json'})

or

import requests

url = 'https://yangcatalog.org/api/admin'
requests.get(url, headers={'Accept': 'application/json'})

or

import requests

url = 'https://yangcatalog.org/admin/login'
requests.get(url, headers={'Accept': 'application/json'})

```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/login"

or

curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin"

or

curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/admin/login"
```

> The above command should redirect you to datatracker login page

This endpoint serves to make a SSO to ietf which will let you access all the admin endpoints. This endpoint will
redirect you to datatracker.ietf.org login page which after successful login will redirect you back to yangcatalog UI
healthcheck page.

### HTTP Request

`GET https://yangcatalog.org/api/admin/login`

`GET https://yangcatalog.org/api/admin`

`GET https://yangcatalog.org/admin/login`

## Logout

```python
import requests

url = 'https://yangcatalog.org/api/admin/logout'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/logout"
```

> The above command should remove all the remebered token and sessions from OIDC

This endpoint serves to log user out

### HTTP Request

`GET https://yangcatalog.org/api/admin/logout`

## Ping redirection

```python
import requests

url = 'https://yangcatalog.org/api/admin/ping'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/ping"
```

> The above command should not be used and is for ietf datatracker to redirect here once user has successfully signed in

This endpoint serves to comunicate with ietf datatracker as an redirection link for OIDC

### HTTP Request

`GET https://yangcatalog.org/api/admin/ping`

<aside class="warning">
This endpoint hould not be used and is for ietf datatracker to redirect here once user has successfully signed in
</aside>

## Admin check

```python
import requests

url = 'https://yangcatalog.org/api/admin/check'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/check"
```

> The above command should return following json

```json
{
  "info": "Success"
}
```

This endpoint serves to admin UI to check if the user is logged in. If he receives 200 all is ok otherwise we are not
logged in and should not let you get into admin UI

### HTTP Request

`GET https://yangcatalog.org/api/admin/check`


## Get file output

```python
import requests

url = 'https://yangcatalog.org/api/admin/directory-structure/read/<path:direc>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/directory-structure/read/<path:direc>"
```

> The above command returns JSON-formatted output

```json
{
    "data":"output of the specified file",
    "info":"Success"
}
```

This endpoint serves to get output of the file specified from /var/yang folder. This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/directory-structure/read/<path:direc>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
path:direc | path to the file we want to read from /var/yang folder

## Delete file from directory

```python
import requests

url = 'https://yangcatalog.org/api/admin/directory-structure/<path:direc>'
requests.delete(url, headers={'Accept': 'application/json'})
```

```shell
curl -X DELETE -H "Accept: application/json" "https://yangcatalog.org/api/admin/directory-structure/<path:direc>"
```

> The above command returns JSON-formatted output

```json
{
    "data":"output of the file that has been deleted",
    "info":"Success"
}
```

This endpoint serves to delete a file from /var/yang folder. This is used with admin UI.

### HTTP Request

`DELETE https://yangcatalog.org/api/admin/directory-structure/<path:direc>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
path:direc | path to the file we want to delete - from /var/yang folder. This can be empty

## Update file from directory

```python
import requests

url = 'https://yangcatalog.org/api/admin/directory-structure/<path:direc>'
body = <data>
requests.put(url, body,
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X PUT -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/directory-structure/<path:direc>"
 --data '<data>'
```

> The above command uses data like this:

```json
{
  "input": {
     "data": "Updated text for given file"
  }
}
```

> The above command returns JSON-formatted output

```json
{
    "data":"output of the file that has been updated",
    "info":"Success"
}
```

This endpoint serves to update a file from /var/yang folder. This is used with admin UI.

### HTTP Request

`PUT https://yangcatalog.org/api/admin/directory-structure/<path:direc>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
path:direc | path to the file we want to update - from /var/yang folder.

## Get directory structure

```python
import requests

url = 'https://yangcatalog.org/api/admin/directory-structure/<path:direc>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/directory-structure/<path:direc>"
```

> The above command returns JSON-formatted directory structure

```json
{
  "data": {
    "files": [
      {
        "group": "yang",
        "name": "yang2_repo_cache.dat",
        "permissions": "0o644",
        "size": 0,
        "user": "yang"
      }
    ],
    "folders": [
      {
        "group": "yang",
        "name": "ytrees",
        "permissions": "0o775",
        "size": 43524699772,
        "user": "yang"
      },
      {
        "group": "yang",
        "name": "commit_dir",
        "permissions": "0o755",
        "size": 41,
        "user": "yang"
      }
    ],
    "name": ""
  },
  "info": "Success"
}
```

This endpoint serves to receive list of files and folders on given path with their name, group id, user id size and permissions.
This is used in admin UI

### HTTP Request

`GET https://yangcatalog.org/api/admin/directory-structure/<path:direc>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
path:direc | path to the file we want to read from /var/yang folder. This can be empty

### Ouptut Parameters

Each file and folder contains following data

Parameter | Description
--------- | -----------
group | linux group name that this file or folder belongs to
name | name of the file or folder
permissions | permissions of the file or folder
size | size of the file or folder
user | linux user name that this file or folder belongs to

## List nginx files

```python
import requests

url = 'https://yangcatalog.org/api/admin/yangcatalog-nginx'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/yangcatalog-nginx"
```

> The above command returns JSON-formatted output

```json
{
    "data": [
         "list of",
         "nginx files"
     ],
    "info":"Success"
}
```

This endpoint serves to receive list of used nginx files. This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/yangcatalog-nginx`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

## Read nginx file

```python
import requests

url = 'https://yangcatalog.org/api/admin/yangcatalog-nginx/<path:nginx_file>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/yangcatalog-nginx/<path:nginx_file>"
```

> The above command returns JSON-formatted output

```json
{
    "data": "nginx file output",
    "info":"Success"
}
```

This endpoint serves to read a nginx file. This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/yangcatalog-nginx/<path:nginx_file>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
path:nginx_file | path to the nginx file we want to read

## Read yangcatalog config file

```python
import requests

url = 'https://yangcatalog.org/api/admin/yangcatalog-config'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/yangcatalog-config"
```

> The above command returns JSON-formatted output

```json
{
    "data": "yangcatalog config file output",
    "info":"Success"
}
```

This endpoint serves to read a yangcatalog config file. This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/yangcatalog-config`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

## Update yangcatalog config file

```python
import requests

url = 'https://yangcatalog.org/api/admin/yangcatalog-config'
body = <data>
requests.put(url, body,
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X PUT -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/yangcatalog-config"
 --data '<data>'
```

> The above command uses data like this:

```json
{
  "input": {
     "data": "Updated text for yangcatalog config file"
  }
}
```

> The above command returns JSON-formatted output

```json
{
    "new-data":"output of the yangcatalog config file that has been updated",
    "info":"Success"
}
```

This endpoint serves to update yangcatalog config file. This is used with admin UI.

### HTTP Request

`PUT https://yangcatalog.org/api/admin/yangcatalog-config`

## List all log files

```python
import requests

url = 'https://yangcatalog.org/api/admin/logs'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/logs"
```

> The above command returns JSON-formatted output

```json
{
  "data": [
    "elasticsearch/gc",
    "crons-log",
    "confd/browser",
    "YANGgenericstats-daily",
    "confd/netconf",
    "elasticsearch/elasticsearch_index_indexing_slowlog",
    "healthcheck"
  ],
  "info": "success"
}
```

This endpoint serves to list all the log files we have in yangcatalog.org. This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/logs`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

## Search and filter for specific output in log files

```python
import requests

url = 'https://yangcatalog.org/api/admin/logs'
body = <data>
requests.post(url, body,
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/logs"
 --data '<data>'
```

> The above command uses data like this:

```json
{
    "input": {
	    "file-names": "yang",
	    "lines-per-page": 1000,
	    "page": 1,
        "from-date": null,
        "to-date": null,
		"filter": {
			"filter-out": "pika",
            "match-cases": false,
            "match-words": false,
            "search-for": "",
            "level": "INFO"
		}
    }
}
```

> The above command returns JSON-formatted output

```json
{
    "meta": {
        "file-names": ["list of", "log files"],
        "from-date": "timestamp same as from request",
        "to-data": "timestamp same as from request",
        "lines--per-page": 1000,
        "page": 1,
        "pages": 72,
        "filter": "same object as from request",
        "format": true
    },
    "output": "Ouptut text from log files"
}
```

This endpoint serves to read and filter log files. This is used with admin UI.

### HTTP Request

`POST https://yangcatalog.org/api/admin/logs`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

## List all sql tables

```python
import requests

url = 'https://yangcatalog.org/api/admin/sql-tables'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/sql-tables"
```

> The above command returns JSON-formatted output

```json
[
    {
        "label":"approved users",
        "name":"users"
    },
    {
        "label":"users waiting for approval",
        "name":"users_temp"
    }
]
```

This endpoint serves to list all the sql tables that exists in yangcatalog.org. This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/sql-tables`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

## Accept user

```python
import requests

url = 'https://yangcatalog.org/api/admin/move-user'
body = <data>
requests.post(url, body,
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/move-user"
 --data '<data>'
```

> The above command uses data like this:

```json
{
    "input": {
	    "models-provider": " Cisco Systems, Inc",
	    "access-rights-sdo": "ietf",
	    "access-rights-vendor": "cisco",
        "username": "foo-bar",
        "first-name": "bar",
		"last-name":"foo",
        "email": "foo-bar@bar.com"
    }
}
```

> The above command returns JSON-formatted output like this if successful

```json
{
    "info": "data successfully added to database users and removed from users_temp",
    "data": {
        "models-provider": " Cisco Systems, Inc",
	    "access-rights-sdo": "ietf",
	    "access-rights-vendor": "cisco",
        "username": "foo-bar",
        "first-name": "bar",
		"last-name":"foo",
        "email": "foo-bar@bar.com"
    }
}
```

This endpoint serves to approve yangcatalog user and set his rights so he can be adding or removing modules based on the
'access-rights-sdo' adn 'access-rights-vendor'. This is used with admin UI.

### HTTP Request

`POST https://yangcatalog.org/api/admin/move-user`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

## Add user

```python
import requests

url = 'https://yangcatalog.org/api/admin/sql-tables/<table>'
body = <data>
requests.post(url, body,
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/sql-tables/<table>"
 --data '<data>'
```

> The above command uses data like this:

```json
{
    "input": {
	    "models-provider": " Cisco Systems, Inc",
	    "access-rights-sdo": "ietf",
	    "access-rights-vendor": "cisco",
        "username": "foo-bar",
        "first-name": "bar",
		"last-name":"foo",
        "email": "foo-bar@bar.com",
        "password": "something secret"
    }
}
```

> The above command returns JSON-formatted output like this if successful

```json
{
    "info": "data successfully added to database",
    "data": {
        "models-provider": " Cisco Systems, Inc",
	    "access-rights-sdo": "ietf",
	    "access-rights-vendor": "cisco",
        "username": "foo-bar",
        "first-name": "bar",
		"last-name":"foo",
        "email": "foo-bar@bar.com",
        "password": "something secret"
    }
}
```

This endpoint serves to add new user to any database that we have in yangcatalog.org (users or users_temp database).
This is used with admin UI.

### HTTP Request

`POST https://yangcatalog.org/api/admin/sql-tables/<table>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
table | Name of the mysql table you want to use

## Delete user

```python
import requests

url = 'https://yangcatalog.org/api/admin/sql-tables/<table>/id/<unique_id>'
requests.delete(url, headers={'Accept': 'application/json'})
```

```shell
curl -X DELETE -H "Accept: application/json"
 "https://yangcatalog.org/api/admin/sql-tables/<table>/id/<unique_id>"
```

This endpoint serves to remove user from any database that we have in yangcatalog.org (users or users_temp database).
This is used with admin UI.

### HTTP Request

`DELETE https://yangcatalog.org/api/admin/sql-tables/<table>/id/<unique_id>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
table | Name of the mysql table you want to use
unique_id | Id of the user you are deleting

## List all rows from sql table

```python
import requests

url = 'https://yangcatalog.org/api/admin/sql-tables/<table>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/sql-tables/<table>"
```

> The above command returns JSON-formatted output

```json
[
    {
        "access-rights-sdo":"bbf",
        "access-rights-vendor":"",
        "email":"fooo@broadband-forum.org",
        "first-name":"fooo",
        "id":4,
        "last-name":"bar",
        "models-provider":"Broadband Forum",
        "username":"fooo-bar"
    },
    {
        "access-rights-sdo":"huawei",
        "access-rights-vendor":"huawei",
        "email":"fooo2@huawei.com",
        "first-name":"fooo2",
        "id":5,
        "last-name":"bar",
        "models-provider":"Huawei Tech.",
        "username":"fooo-bar2"
    }
.
.
.
]
```

This endpoint serves to list all the rows from the specified sql table that exists in yangcatalog.org.
This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/sql-tables/<table>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
table | Name of the mysql table you want to use

## Get list of all scripts

```python
import requests

url = 'https://yangcatalog.org/api/admin/scripts'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/scripts"
```

> The above command returns JSON-formatted output like this

```json
{
    "data":[
        "populate",
        "runCapabilities",
        "draftPull",
        "draftPullLocal",
        "openconfigPullLocal",
        "statistics",
        "recovery",
        "elkRecovery",
        "elkFill",
        "resolveExpiration"
    ],
    "info":"Success"
}
```

This endpoint serves to receive list of scripts that are available to use. This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/scripts`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

## Get script details

```python
import requests

url = 'https://yangcatalog.org/api/admin/scripts/<script>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/scripts/<script>"
```

> The above command returns JSON-formatted output like this for populate script

```json
{
    "data":{
        "api":{
            "default":false,
            "type":"bool"
        },
        "api_ip":{
            "default":"yangcatalog.org",
            "type":"str"
        },
        "api_port":{
            "default":"8443",
            "type":"int"
        },
        "api_protocol":{
            "default":"https",
            "type":"str"
        },
        "dir":{
            "default":"/var/yang/nonietf/yangmodels/yang/standard/ietf/RFC",
            "type":"str"
        },
        "force_indexing":{
            "default":false,
            "type":"bool"
        },
        "ip":{
            "default":"yc_confd_1",
            "type":"str"
        },
        "notify_indexing":{
            "default":false,
            "type":"bool"
        },
        "port":{
            "default":"8008",
            "type":"int"
        },
        "protocol":{
            "default":"http",
            "type":"str"
        },
        "result_html_dir":{
            "default":"/usr/share/nginx/html/results",
            "type":"str"
        },
        "save_file_dir":{
            "default":"/var/yang/all_modules",
            "type":"str"
        },
        "sdo":{
            "default":false,
            "type":"bool"
        }
    },
    "help":"Parse hello messages and YANG files to JSON dictionary. These dictionaries are used for populating a yangcatalog. This script runs first a runCapabilities.py script to create a JSON files which are used to populate database.",
    "options":{
        "api":"If request came from api",
        "api_ip":"Set host address where the API is started. Default: yangcatalog.org",
        "api_port":"Whether API runs on http or https (This will be ignored if we are using uwsgi). Default: https",
        "api_protocol":"Whether API runs on http or https. Default: https",
        "dir":"Set dir where to look for hello message xml files or yang files if using \"sdo\" option",
        "force_indexing":"Force to index files. Works only in notify-indexing is True",
        "ip":"Set host address where the Confd is started. Default: yc_confd_1",
        "notify_indexing":"Whether to send files for indexing",
        "port":"Set port where the Confd is started. Default: 8008",
        "protocol":"Whether Confd runs on http or https. Default: http",
        "result_html_dir":"Set dir where to write HTML compilation result files. Default: /usr/share/nginx/html/results",
        "save_file_dir":"Directory where the yang file will be saved. Default: /var/yang/all_modules",
        "sdo":"If we are processing sdo or vendor yang modules"
    }
}
```

This endpoint serves to receive detail information about script you are running. It will show you what options you can
use with its default values and help if it contains any. This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/scripts/<script>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
script | Name of the script you want to use

## Run script

```python
import requests

url = 'https://yangcatalog.org/api/admin/scripts/<script>'
body = <data>
requests.post(url, body,
    headers={'Accept': 'application/json', 'Content-type': 'application/json'})
```

```shell
curl -X POST -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/scripts/<script>"
 --data '<data>'
```

> The above command uses data like this if the script is "draftPull":

```json
{
    "input":{
        "config_path":"/etc/yangcatalog/yangcatalog.conf",
        "send_message":false
    }
}
```

> The above command returns JSON-formatted output like this if successful

```json
{
    "info": "Verification successful",
    "job_id": "sadfaewsf-sdfas4568-ef5s8df-as4568ef",
    "arguments": ["list of", "arguments sent"]
}
```

This endpoint serves to run scripts manualy from yangcatalog.org. We need to provide a payload with arguments for given
script where key is a name of the option and value is an value you want to provide to that specific option of the script.
This is used with admin UI.

### HTTP Request

`POST https://yangcatalog.org/api/admin/scripts/<script>`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
script | Name of the script you want to run

## Get script details

```python
import requests

url = 'https://yangcatalog.org/api/admin/disk-usage'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" "https://yangcatalog.org/api/admin/disk-usage"
```

> The above command returns JSON-formatted output like this

```json
{
    "data":{
        "free": 205436604416,
        "total": 416291377152,
        "used": 210837995520
    },
    "info":"Success"
}
```

This endpoint serves to receive disk space information in bytes. This is used with admin UI.

### HTTP Request

`GET https://yangcatalog.org/api/admin/disk-usage`

<aside class="warning">
This URL works only after you are signed in using single sign on from ietf and after token has been received and
session created. Otherwise you ll get unauthorized 401 response.
</aside>

### URL Parameters

Parameter | Description
--------- | -----------
script | Name of the script you want to use


# Healthchecks

The following enpoints serve to check the health status of the yangcatalog.org. AWS where yangcatalog.org is running is
checking the following endpoints from several locations every minute several times. When any of the healthcheck fails it
will send the message to preset mailing list and informs about this failure. If the failure is on backend API itself all
of the healthcheck endpoint will consequently fail even if it is a false failure. These endpoints are used within admin UI
as well.

## Get list of services

```python
import requests

url = 'https://yangcatalog.org/api/admin/healthcheck/services-list'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/healthcheck/services-list"
```

> The above command should return services with their endpoints for healthcheck (just the last part) we need to use
> https://yangcatalog.org/api/admin/healthcheck/ in front of all of them

```json
[
    {
        "endpoint": "my-sql",
        "name": "MySQL"
    },
    {
        "endpoint": "elk",
        "name": "Elasticsearch"
    },
    {
        "endpoint": "confd",
        "name": "ConfD"
    },
    {
        "endpoint": "yang-search-admin",
        "name": "YANG search"
    },
    {
        "endpoint": "yang-validator-admin",
        "name": "YANG validator"
    },
    {
        "endpoint": "yangre-admin",
        "name": "YANGre"
    },
    {
        "endpoint": "nginx",
        "name": "NGINX"
    },
    {
        "endpoint": "rabbitmq",
        "name": "RabbitMQ"
    }
]
```

This endpoint serves to provide with all the services we have with its endpoints to check their healthstatus

### HTTP Request

`GET https://yangcatalog.org/api/admin/healthcheck/services-list`

## Get service healthcheck

```python
import requests

url = 'https://yangcatalog.org/api/admin/healthcheck/<service-name>'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/healthcheck/<service-name>"
```

> The above command should return service health status (example output with my-sql)

```json
{
    "info": "MySQL is running",
    "message": "3 tables available in the database: yang_catalog",
    "status": "running"
}
```

This endpoint serves to provide service health status

### HTTP Request

`GET https://yangcatalog.org/api/admin/healthcheck/<service-name>`

### URL Parameters

Parameter | Description
--------- | -----------
service-name | Name of the service you want to test health for

### Output Parameters

Parameter | Description
--------- | -----------
info | status information
message | short description of status (why it failed or why are we saying it is running)
status | status enum - can be 'running', 'failed' or 'problem'

## Get service admin healthcheck

```python
import requests

url = 'https://yangcatalog.org/api/admin/healthcheck/<service-name>-admin'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/healthcheck/<service-name>-admin"
```

> The above command should return service admin health status (example output with yangre-admin)

```json
{
    "info": "yangre is available",
    "message": "yangre successfully validated string",
    "status": "running"
}
```

This endpoint serves to provide service admin health status. This is valid only for yang-validator-admin, yangre-admin and
yang-search-admin. These endpoints are not checking only if the service itself is running (django or flask application with uwsgi),
but also it s trying to make request on some real data and checking if it is getting valid response.

### HTTP Request

`GET https://yangcatalog.org/api/admin/healthcheck/<service-name>-admin`

### URL Parameters

Parameter | Description
--------- | -----------
service-name | Name of the service you want to test health for. It can be yang-validator, yanre or yang-search

### Output Parameters

Parameter | Description
--------- | -----------
info | status information
message | short description of status (why it failed or why are we saying it is running)
status | status enum - can be 'running', 'failed' or 'problem'

## Get cronjobs healthcheck

```python
import requests

url = 'https://yangcatalog.org/api/admin/healthcheck/cronjobs'
requests.get(url, headers={'Accept': 'application/json'})
```

```shell
curl -X GET -H "Accept: application/json" -H "Content-type: application/json"
 "https://yangcatalog.org/api/admin/healthcheck/cronjobs"
```

> The above command should return data about each cronjob

```json
{
    "data": {
        "draftPull": {
            "end": 1599603601,
            "error": "",
            "last_successfull": 1599603601,
            "start": 1599603558,
            "status": "Success"
        },
        "draftPullLocal": {
            "end": 1599612283,
            "error": "",
            "last_successfull": 1599612283,
            "start": 1599602701,
            "status": "Success"
        },
        "openconfigPullLocal": {
            "end": 1599613583,
            "error": "",
            "last_successfull": 1599613583,
            "start": 1599613501,
            "status": "Success"
        },
        "recovery": {
            "end": 1599589314,
            "error": "",
            "last_successfull": 1599589314,
            "start": 1599589021,
            "status": "Success"
        },
        "removeUnused": {
            "end": 1599579002,
            "error": "AuthenticationException(401, '{\"Message\":\"settings.role_arn is needed for snapshot registration.\"}')",
            "start": 1599579002,
            "status": "Fail"
        },
        "resolveExpiration": {
            "end": 1599625957,
            "error": "",
            "last_successfull": 1599625957,
            "start": 1599624301,
            "status": "Success"
        },
        "statistics": {
            "end": 1599621220,
            "error": "",
            "last_successfull": 1599621220,
            "start": 1599620702,
            "status": "Success"
        }
    }
}
```

This endpoint serves to provide information about cronjob that are running on daily or weekly basis. each one contains information
about its startint and ending timestamp, status if it failed or run successfully, error message and last successful run timestamp

### HTTP Request

`GET https://yangcatalog.org/api/admin/healthcheck/cronjobs`

### Output Parameters

each cronjob contains following data

Parameter | Description
--------- | -----------
end | timestamp of last run end time
error | error message if job failed
last_successfull | timestamp of last successful run
start | timestamp of last run start time
status | status enum - can be 'Fail' or 'Success'
