Recovery
========

This package contains a Python scripts to save or load all the modules.

For `recovery.py` script we need to specify an option to either save or load the modules.

1. Saving modules

    When saving modules it will create a json file with the current
    date and time. This json file contains all the modules and
    metadata that we have in yangcatalog. The option to save modules
    is "--save", which is the default option

2. Loading modules

    When loading modules we need to either provide a path to a json
    file that contains all the modules and metadata or it will
    load the file with latest date. Option to load modules is
    "--load" which is not the default option

`elk_recovery.py` script allows us to save/load
the Elasticsearch database to/from snapshot.

1. Saving database

    When saving the databse it will create a snapshot in the directory that
    must be specified in the elasticsearch.yml file under repo.path.
    The name of the snapshot is the current date and time.

2. Loading database

    When loading a dabase, we need to either provide the name of the snapshot
    or we can use the "--latest" option and it will automaticaly load
    the latest snapshot to Elasticsearch.

`elk_fill.py` script is used for creating a dictionary of all the modules
which are currently stored in the Redis database. 
Dictionary contains key: value pairs in following format:
```
{
    "<name>@<revision>/organization": "/var/yang/all_modules/<name>@<revision>.yang"
}
```
The entire dictionary is then stored in a JSON file. 
Content of this JSON file can then be used as an input for indexing modules into Elasticsearch.