YANGCATALOG
===========

You can find official yangcatalog website in [here](https://yangcatalog.org).

This scripts in this repository serve as a backend to add, update, remove and manage
yang modules files in yangcatalog. It is composed out of:
* scripts that run every day as a cron job, 
* API which lets users to add, remove or find modules they expect to 
* scripts that parse and populate yangcatalog database.

This repository works directly with [yangModels/yang](https://github.com/YangModels/yang)
repository. That repository contains all the different modules
structered in vendors (Cisco, Huawei and others modules) and SDOs
(IETF, IEEE, MEF, BBF and others modules)

#### Parse and Populate

The most important module in this repository is called ParsedAndPopulate.
This module contains parsing scripts to parse all the modules on given
directory and therefore we receive all the metadata about the module
according to [draft-clacla-netmod-model-catalog-03](https://tools.ietf.org/html/draft-clacla-netmod-model-catalog-03).
Parsed metedata are subsequently populated to confd datastore using
confd REST request. All the new modules that were not yet in the datastore
are sent to metadata-update script of yangcatalog using REST request
which populates a MySQL database with all the new modules. This database
is used for yang-search purposes of yangcatalog.org.

We can parse module either with using __sdo__ option which will go through
given directory and will parse all the yang modules in there one by one,
or without this option which will try to find platform-metadata.json file
in the directory which contains paths to capability.xml files and it
will parse all the modules according to those files with vendor metadata
added.

To find all the modules missing or wrong revisions, namespaces, imports,
include or modules that according to capability.xml file should be in
folder but are missing, we can use runCapabilities script with __integrity__
option.

#### API

The API module runs as a UWSGI emperor vassal and contains several endpoints. Most
of the endpoints serves to find modules in different ways. This is described
deeper in [API documentation](www.yangcatalog.org/doc). If the user is
registered, she/he can add modify or delete modules based on pre-approved path.
Once user has filled in registration form, one of yangcatalog admin users
needs to use validate script which will walk him through the validation
process to give the user specific rights so he is able to add, remove or
update only certain modules.

Some of the requests may take a longer period of time to process. For this
matter a sender and receiver was made. These scripts are using rabbitMQ
to communicate. API will use sender to send a job to the receiver. While
receiver is processing this job, user will receive a job-id. User can
check his job at any time if it has been completed or not. Once a receiver
is done it will update a job status to either Failed of Finished
successfully.

Yangcatalog api is also used for some automated jobs. Every time new
modules are merged in yangModels/yang repository a job is triggered to
populate all new modules to yangcatalog database. API is also receiving
IETF Yang models every day and if there are any new drafts it will
automatically populate yangcatalog database and update the repository
with all the new IETF modules if travis job passed successfully.

#### Jobs

There are several cron jobs that are running every day.
* Statistics job under statistic module which goes through all the
modules that are in yangcatalog and generates html file which has
information about what vendors and sdos modules do we have and amound of
modules that we have.
* Resolve expiration job that checks all the ietf draft modules
and their expiration date and update its metadata accordingly.
* Remove unused job that removes data on the server that are not used
anymore.
* In ietfYangDraftPull there are three jobs. DraftPull.py adds new modules
to yangModels/yang repository if there are any new modules. DraftPullLocall.py
goes through all ietf drafts and rfcs and populates yangcatalog if there
are any new modules. Finally OpenconfigPullLocall.py populates all the
new openconfig yang modules from their own repository to the yangcatalog.
* Recovery script which pulls all the data from confd and creates a json
file which is saved in server as backup. If we loose all the data for
some reason we can use this script to upload them back with no loss of
data.

### Messaging

For every new module that has been added to yangcatalog database, yang admin
users are informed about this using a Cisco Webex teams room and by email.


