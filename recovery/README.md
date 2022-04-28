Recovery
========

This package contains a Python scripts to save or load all the modules.

We need to specify an option to either save or load the modules.

1. Saving modules

    When saving modules it will create a json file with the current
    date and time. This json file contains all the modules and
    metadata that we have in yangcatalog. The option to save modules
    is "--type save", which is the default option
2. Loading modules

    When loading modules we need to either provide a path to a json
    file that contains all the modules and metadata or it will
    load the file with latest date. Option to load modules is
    "--type load" which is not the default option

It also contains `elk_recovery.py` script which allows us to save or load
the Elasticsearch database.

1. Saving database

    When saving the databse it will create a snapshot in the directory that
    must be specified in the elasticsearch.yml file under repo.path.
    The name of the snapshot is the current date and time.

2. Loading database

    When loading a dabase, we need to either provide the name of the snapshot
    or we can use the "--latest" option and it will automaticaly load
    the latest snapshot to Elasticsearch.
