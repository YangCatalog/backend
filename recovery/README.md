Recovery
========

This package contains a python script to save or load all the modules

We need to specify an option to either save or load the modules.

1. Saving modules

    When saving modules it will create a json file with current
    date and time. This json file contains all the modules and
    its metadata that we have in yangcatalog. Option to save modules
    is "--type save" which is default option
2. Loading modules

    When loading modules we need to either provide path to a json
    file that contains all the modules and its metadata or it will
    load the file with latest date. Option to load modules is
    "--type load" which is not a default option

It also contains elkRecovery script which allows us to save or load
elasticsearch database

1. Saving database

    When saving databse it will create snapshot in directory that
    must be specified in elasticsearch.yml file under repo.path.
    The name of the snapshot is current date and time.

2. Loading database

    When loading dabase we need to either provide name of the snapshot
    or we can use "--latest" option and it will automaticaly load
    the latest snapshot to elasticsearch.
