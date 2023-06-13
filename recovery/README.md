Recovery
========

This package contains Python scripts to save or load all the modules from databases to backups.

## [recovery.py](https://github.com/YangCatalog/backend/blob/master/recovery/recovery.py)

This script is called with the `--save` option by the cronjob every day, and with the `--load` option on every docker-compose
rebuilding by the `yc-api-recovery` container.

1. Saving modules

    A backup gz file of the `dump.rdb` and a backup JSON file with all the currently available modules and vendors (metadata)
    in Redis will be created. The default name for the JSON backup is current datetime in the special backup format, but
    it can be changed using the `--file` argument, for example, to save some specified state of Redis for later.

2. Loading modules

    When loading modules we can provide the path to a specific JSON Redis backup file using the `--file` argument, without
    providing this argument, the latest backup will be used. All the modules and vendors (metadata) from this backup
    will be loaded to Redis.

## [opensearch_recovery.py](https://github.com/YangCatalog/backend/blob/master/recovery/opensearch_recovery.py)

This script can be called via the Admin page, and it saves/loads (using the `--save` and `--load` arguments respectively)
the OpenSearch database (all indices) to/from a snapshot.

1. Saving database

    When saving the database it will create a snapshot in the directory that must be specified in the
    [opensearch.yml](https://github.com/YangCatalog/deployment/blob/master/opensearch/opensearch.yml)
    file in the `path.repo`. The default name for the snapshot is current datetime in the special backup format, but
    it can be changed using the `--file` argument, for example, to save some specified state of OpenSearch for later.

2. Loading database

    When loading the database we can provide the path to a specific snapshot file using the `--file` argument, without
    providing this argument, the latest snapshot will be used. Be aware that restoring an OpenSearch snapshot will
    replace the current state of the OpenSearch indices with the data that was backed up in the snapshot, it will
    replace the entire index, including any data that was added or modified since the snapshot was taken.
    OpenSearch will automatically close the index before restoring the data and then reopen it when the restore is complete.
    This means that the index will be unavailable while the restore is in progress.

## [opensearch_fill.py](https://github.com/YangCatalog/backend/blob/master/recovery/opensearch_fill.py)

This script can be called via the Admin page, and it's used for creating a dictionary of all the modules
which are currently stored in the Redis database. Dictionary contains key: value pairs in following format:
```
{
    "<name>@<revision>/<organization>": "/var/yang/all_modules/<name>@<revision>.yang"
}
```
The entire dictionary is then stored in a JSON file: `opense_data.json` in the `temp` directory. 
Content of this JSON file can then be used as an input for indexing modules into OpenSearch.

## [redis_users_recovery.py](https://github.com/YangCatalog/backend/blob/master/recovery/redis_users_recovery.py)

This script is called with the `--save` option by the cronjob every month, and it also can be called via the Admin page
with either `--save` or `--load` option.

1. Saving users

    A backup JSON file with all the currently available users in Redis will be created. The default name for the JSON
    backup is current datetime in the special backup format, but it can be changed using the `--file` argument, for example,
    to save some specified state of Redis users for later.

2. Loading users

    When loading users we can provide the path to a specific JSON Redis backup file using the `--file` argument, without
    providing this argument, the latest backup will be used. All the users from this backup will be loaded to Redis.