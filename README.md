# YANG Catalog

[![codecov](https://codecov.io/gh/YangCatalog/backend/branch/develop/graph/badge.svg?token=JHFBBUTL1X)](https://codecov.io/gh/YangCatalog/backend)

---

## Overview
This repository contains YANG Catalog's [REST API](https://yangcatalog.org/doc) and the bulk of its internal infrastructure for processing YANG modules and extracting their properties. It also serves information to YANG Catalog's [frontend](https://github.com/YangCatalog/yangcatalog-ui) and implements the functionality of the [Admin UI](https://github.com/YangCatalog/admin_ui).

## YANG Module Processing
The scripts in this repository serve as a backend to add, update, remove and manage
YANG module files in yangcatalog. It is composed of:
* scripts that run every day as a cron job
* an API which lets users add, remove or find the modules they expect
* scripts that parse new/updated modules from different sources and populate them into yangcatalog database

This repository works directly with  the [yangModels/yang](https://github.com/YangModels/yang) repository.
That repository contains all the modules structured by vendors (Cisco, Huawei and others) and SDOs
(IETF, IEEE, MEF, BBF and others).

### Parse and Populate

The most important directory in this repository is [parseAndPopulate](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate).
This directory contains parsing scripts to parse all the modules of given directories. This gives us all the metadata of the modules
according to [draft-clacla-netmod-model-catalog-03](https://tools.ietf.org/html/draft-clacla-netmod-model-catalog-03).
Parsed metadata is subsequently populated to Redis and ConfD databases. These databases are used for the yang-search part of yangcatalog.org.

We can parse modules either with the `--sdo` option, which will go through a given directory and parse all of its
yang modules one by one, or without this option, which will try to find a `platform-metadata.json` file
in the directory which contains paths to `capability.xml` files and parse all the modules according to those files
with vendor metadata added.

To find all the modules with missing or wrong revisions, namespaces, imports, includes or modules that according to
a `capability.xml` file should be in the folder but are missing, we can use the
[integrity](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/integrity.py) script.

## API

The API module runs as a UWSGI emperor vassal (using the `yang-catalog.ini` file) and contains several endpoints.
Most of the endpoints serve to find modules in different ways. This is described deeper in the [API documentation](https://yangcatalog.org/doc).
If the user is registered, she/he can add, modify or delete modules based on a pre-approved path.
Once a user has filled in the registration form, one of yangcatalog's admin users needs to approve user using
Admin UI and give the user specific rights, so he is able to add, remove or update only certain modules.

Some requests may take a longer period of time to process. Because of thissome endpoints will give the user a job-id.
The user can check this job at any time to see if the job has been completed or is still processing or failed during the
execution by using the job-id.

The Yangcatalog API is also used by some automated external jobs. Every time new modules are merged into the yangModels/yang
repository a job is triggered to populate all the new modules to the yangcatalog database.

The backend API also receives IETF Yang models every day and if there are any new drafts it will automatically populate
the yangcatalog database and update the repository with all the new IETF modules if GitHub Actions pass successfully.

### Jobs

There are several cron jobs that run every day.
* [statistics](https://github.com/YangCatalog/backend/blob/master/statistic/statistics.py) job which goes through all the
modules that are in yangcatalog and generates an HTML file which has information about what vendors' and SDOs' modules
we have and the number of modules that we have.
* [resolve_expiration](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/resolve_expiration.py)
job that checks all the IETF draft modules and their expiration dates and updates its metadata accordingly.
* [remove_unused](https://github.com/YangCatalog/backend/blob/master/utility/remove_unused.py) job that removes data
on the server that is not used anymore.
* [user_reminder](https://github.com/YangCatalog/backend/blob/master/utility/user_reminder.py) script that will be
triggered once a month to show us which users we have in our database.
* In the [ietfYangDraftPull](https://github.com/YangCatalog/backend/blob/master/ietfYangDraftPull) directory there is one job.
    1. [pull_local](https://github.com/YangCatalog/backend/blob/master/ietfYangDraftPull/pull_local.py)
    clones the https://github.com/YangModels/yang repo, updates RFCs data with the latest data from the YANG-RFC.tgz,
    which is created during running of this script: https://github.com/YangCatalog/module-compilation/blob/develop/ietf_modules_extraction/run_ietf_module_extraction.sh.
    Then goes through RFC, experimental, and IANA modules data and populates yangcatalog.
* In the [automatic_push](https://github.com/YangCatalog/backend/blob/master/automatic_push) directory there are two jobs.
    1. [ietf_push](https://github.com/YangCatalog/backend/blob/master/automatic_push/ietf_push.py) retrieves and adds new
    IETF RFC and draft modules to the  https://github.com/yang-catalog/yang repository if there are any new/updated modules.
    2. [iana_push](https://github.com/YangCatalog/backend/blob/master/automatic_push/iana_push.py) rsyncs and pushes new 
    IANA modules to the  https://github.com/yang-catalog/yang repo.
* [recovery](https://github.com/YangCatalog/backend/blob/master/recovery/recovery.py) script which pulls all the data
from Redis and creates a json file which is saved on the server as a backup. If we lose all the data for some reason
we can use this script to upload it back with no loss of data.
* [revise_tree_type](https://github.com/YangCatalog/backend/blob/master/utility/revise_tree_type.py)
reevaluates the tree type for modules that were previously of type nmda-compatible.
* [reviseSemver](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/reviseSemver.py)
reevaluates the derived semantic versions of modules.

### Messaging

Yang admin users are informed about every new module added to the yangcatalog database in a Cisco Webex teams room and by email.
Also, there are other emails and Webex messages sent for different events, they can be found in the
[message_factory](https://github.com/YangCatalog/backend/blob/master/utility/message_factory.py) module.

## Installing

### Pre-requisites

ConfD Premium has to be accessible

### API code

Since this is just a small part of the whole functional environment, you need to build using
the docker-compose file from the [deployment folder](https://github.com/YangCatalog/deployment).
Then the `catalog_backend_api:latest` image can be used to run a docker container where
everything will start as it is supposed to.

### Documentation

See the README.md file in the `documentation/` directory.

### Fill the Redis database

Using `backend/recovery/recovery.py --load --file /var/yang/cache/redis-json/<specific>.json` for loading some specific backup,
or using `backend/recovery/recovery.py --load` to load the latest backup.

### NGINX Configuration

To be localized to your configuration.

```
        location /doc {
            alias /usr/share/nginx/html/slate/build;
        }

        location /api {
            rewrite /api(/.*)$ $1 break;
            include uwsgi_params;
            uwsgi_pass 127.0.0.1:8443;
            uwsgi_read_timeout 900;
        }
```
