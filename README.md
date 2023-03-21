# YANG Catalog

[![codecov](https://codecov.io/gh/YangCatalog/backend/branch/develop/graph/badge.svg?token=JHFBBUTL1X)](https://codecov.io/gh/YangCatalog/backend)

---

## Overview
This repository contains YANG Catalog's [REST API](https://yangcatalog.org/doc) and the bulk of its internal infrastructure for processing YANG modules and extracting their properties. It also serves information to YANG Catalog's [frontend](https://github.com/YangCatalog/yangcatalog-ui) and implements the functionality of the [Admin UI](https://github.com/YangCatalog/admin_ui).

## YANG Module Processing
The scripts in this repository serve as a backend to add, update, remove and manage
YANG module files in yangcatalog. It is composed of:
* scripts that run every day as a cron job,
* an API which lets users add, remove or find the modules they expect
* scripts that parse and populate the yangcatalog database.

This repository works directly with  the [yangModels/yang](https://github.com/YangModels/yang)
repository. That repository contains all the modules
structured by vendors (Cisco, Huawei and others) and SDOs
(IETF, IEEE, MEF, BBF and others).

### Parse and Populate

The most important module in this repository is called ParsedAndPopulate.
This module contains parsing scripts to parse all the modules of a given
directory. This gives us all the metadata of the modules
according to [draft-clacla-netmod-model-catalog-03](https://tools.ietf.org/html/draft-clacla-netmod-model-catalog-03).
Parsed metadata is subsequently populated to a confd datastore using
a confd REST request. This database
is used for the yang-search part of yangcatalog.org.

We can parse modules either with the __sdo__ option, which will go through
a given directory and parse all of its yang modules one by one,
or without this option, which will try to find a platform-metadata.json file
in the directory which contains paths to capability.xml files and
parse all the modules according to those files with vendor metadata
added.

To find all the modules with missing or wrong revisions, namespaces, imports,
includes or modules that according to the capability.xml file should be in
the folder but are missing, we can use the integrity script.

## API

The API module runs as a UWSGI emperor vassal (using the `yang-catalog.ini` file)
and contains several endpoints. Most
of the endpoints serve to find modules in different ways. This is described
deeper in the [API documentation](https://yangcatalog.org/doc). If the user is
registered, she/he can add, modify or delete modules based on a pre-approved path.
Once a user has filled in the registration form, one of yangcatalog's admin users
needs to approve user using Admin UI and give the user specific rights, so he is able to add,
remove or update only certain modules.

Some requests may take a longer period of time to process.
Because of this, a sender and a receiver was made. These scripts use rabbitMQ
to communicate. The API will use the sender to send a job to the receiver. While
the receiver is processing this job, the user will receive a job-id. The user can
check his job at any time to see if it has been completed or not. Once a receiver
is done it will update the job status to either Failed of Finished
successfully.

_Note about rabbitMQ: on some Linux distributions, you need to add `HOSTNAME=localhost` to `/etc/rabbitmq/rabbitmq-env.conf`...._

The Yangcatalog API is also used by some automated jobs. Every time new
modules are merged into the yangModels/yang repository a job is triggered to
populate all the new modules to the yangcatalog database.

The backend API also receives
IETF Yang models every day and if there are any new drafts it will
automatically populate the yangcatalog database and update the repository
with all the new IETF modules if GitHub Actions pass successfully.

Please note that UWSGI caching is used to improve the performance compared to
ConfD requests. During loading of the UWSGI, the cache is pre-populated by
issuing one ConfD request per module; during this initial load time, the API
will probably time out and the NGINX server will return a 50x error.

### Jobs

There are several cron jobs that run every day.
* [statistics](https://github.com/YangCatalog/backend/blob/master/statistic/statistics.py) job which goes through all the
modules that are in yangcatalog and generates an HTML file which has
information about what vendors' and SDOs' modules we have and the number of
modules that we have.
* [resolveExpiration](https://github.com/YangCatalog/backend/blob/master/utility/resolveExpiration.py) job that checks all the IETF draft modules
and their expiration dates and updates its metadata accordingly.
* [remove_unused](https://github.com/YangCatalog/backend/blob/master/utility/remove_unused.py) job that removes data on the server that are not used
anymore.
* [user_reminder](https://github.com/YangCatalog/backend/blob/master/utility/user_reminder.py) script that will be triggered twice a year to show us what
users we have in our database.
* In the [ietfYangDraftPull](https://github.com/YangCatalog/backend/blob/master/ietfYangDraftPull) directory there are two jobs.
    1. [pull_local](https://github.com/YangCatalog/backend/blob/master/ietfYangDraftPull/pull_local.py)
    clones the https://github.com/YangModels/yang repo, updates RFCs data with the latest data from the YANG-RFC.tgz,
    which is created during running of this script: https://github.com/YangCatalog/module-compilation/blob/develop/ietf_modules_extraction/run_ietf_module_extraction.sh.
    Then goes through RFC, experimental, and IANA modules data and populates yangcatalog.
    2. [openconfigPullLocal](https://github.com/YangCatalog/backend/blob/master/ietfYangDraftPull/openconfigPullLocal.py) populates all the
    new openconfig yang modules from their own repository to yangcatalog.
* In the [automatic_push](https://github.com/YangCatalog/backend/blob/master/automatic_push) directory there are two jobs.
    1. [ietf_push](https://github.com/YangCatalog/backend/blob/master/automatic_push/ietf_push.py) retrieves and adds new
    IETF RFC and draft modules to the  https://github.com/yang-catalog/yang repository if there are any new/updated modules.
    2. [iana_push](https://github.com/YangCatalog/backend/blob/master/automatic_push/iana_push.py) rsyncs and pushes new 
    IANA modules to the  https://github.com/yang-catalog/yang repo.
* [recovery](https://github.com/YangCatalog/backend/blob/master/recovery/recovery.py) script which pulls all the data from confd and creates a json
file which is saved on the server as a backup. If we loose all the data for
some reason we can use this script to upload it back with no loss of
data.
* [revise_tree_type](https://github.com/YangCatalog/backend/blob/master/utility/revise_tree_type.py) reevaluates the tree type for modules that were previously of type nmda-compatible.
* [reviseSemver](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/reviseSemver.py) reevaluates the derived semantic versions of modules.
### Messaging

Yang admin users are informed about every new module added to the yangcatalog
database in a Cisco Webex teams room and by email.

## Installing

### Pre-requisites

ConfD Premium has to be accessible

### API code

Since this is just a small part of the whole functional environment, you need to build using
the docker-compose file from the [deployment folder](https://github.com/YangCatalog/deployment).
Then the catalog_backend_api:latest image can be used to run a docker container where
everything will start as it is supposed to.

### Documentation

See the README.md file in the `documentation/` directory.

### Fill the ConfD database

Using `backend/recovery/recovery.py --load --file /var/yang/cache/confd/<latest>.json`.

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
