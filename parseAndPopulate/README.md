# Parse and Populate

This package contains python scripts to parse yang files and consequently populate them to ConfD and Redis.
The main scripts are:

## [integrity](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/integrity.py)

   This script will go through all the yang files and find all the problems with them like missing includes or imports,
   wrong namespaces, wrong revisions, missing or extra files in folders with capabilities.xml files, etc...
   The `--dir` option specifies the directory to check. The `--sdo` option tell it not to look for capabilities.xml files.
   The `--output` option specifies the output JSON file.

## [populate](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/populate.py)

   This script is called either by an admin user to manually populate data of a certain directory or by an API call
   when other users would like to contribute to yangcatalog. Also, when there are new yang modules added to the GitHub
   repository, this script will be automatically called after the API loads all the new yang modules from the GitHub repository.
   This script is also called for different directories in the [pull_local](https://github.com/YangCatalog/backend/blob/master/ietfYangDraftPull/pull_local.py)
   script during the daily cronjob.

   Firstly, it creates a temporary json directory, which will be used to store the needed files
   (like `prepare.json`, `normal.json`, `temp_hashes.json`). Secondly, it runs the [parse_directory](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/parse_directory.py)
   script which dumps new/updated modules and vendors data into the json dir mentioned above in the `prepare.json` and `normal.json` files respectively.
   After populating ConfD and Redis, it will prepare and send modules data for OpenSearch indexing (writes data to the
   `changes-cache` and `delete-cache` files which are later used in the [process_changed_mods.py](https://github.com/YangCatalog/backend/blob/master/opensearch_indexing/process_changed_mods.py)
   script). Then the API will be restarted, so it can load all the new metadata into its cache. After that,
   this script will start to run more complicated algorithms on those parsed yang files. This will extract dependents,
   semantic versioning and tree types. When this is parsed it will once again populate ConfD and Redis, and restart API,
   so we have all the metadata of the yang files available. If there were no errors while updating modules info in ConfD,
   files hashes from the `temp_hashes.json` in the temporary json dir will be saved to the permanent cache directory,
   so the information about already parsed modules can be re-used in the future runs of this script to not reparse unchanged modules in the
   [parse_directory](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/parse_directory.py) script.

   Before starting to parse and populate yang modules, make sure that all the ports, protocols and ip addresses are set correctly.

## [parse_directory](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/parse_directory.py)

   This script is called by the [populate](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/populate.py)
   script during the daily cronjob, and it can also be called via admin page.

   The main option of this script is `--sdo` (boolean) based on this option, either sdo modules or vendor modules will be parsed.
   Firstly, all the new yang modules from the `--dir` directory will be saved to the `--save-file-dir` directory, and then
   the `--dir` directory will be parsed. Vendors and sdo modules have their own parsing logic, but the main goal is to go
   through all the modules (they can be stored in an xml file, or it is just all the modules in the `--dir` directory),
   see if their content has changed, and dump information about new/updated modules in the `prepare.json` and `normal.json`
   files in the `--json-dir` directory, which will be used in the [populate](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/populate.py)
   script to update modules in databases. The hash of the new/updated modules will be dumped in the `temp_hashes.json`
   in the `--json-dir` directory, so it can be used in the `populate` script to update the hash of the files in the
   permanent cache directory to be used in the future to not reparse unchanged modules.


For example for all SDOs (known in October 2021):
```
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/bbf --notify-indexing --force-parsing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/etsi --notify-indexing --force-parsing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/iana --notify-indexing --force-parsing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/ieee --notify-indexing --force-parsing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/ietf --notify-indexing --force-parsing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/mef --notify-indexing --force-parsing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/odp --notify-indexing --force-parsing
```
