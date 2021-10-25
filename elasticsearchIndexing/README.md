# YANG Search Data Maintenance

A cronjob is executed every minute and calls: `process-changed-mods.py --time -1`

## process-changed-mods.py

Takes as argument: the number of minutes to search for new modules.

Read the JSON file YANG_CACHE_FILE for the list of modules (also making a .bak before truncating it to 0), this is the list of modules to be processed.

**Note:** the two JSON files are actually created by an external process calling the web service at /yang-search/metadata_update/

Finally, calls `build_yindex.py` 


## build_yindex.py

Build the list of all modules modified since the --time (else for all modules), and for all modules to be processed:
* Using the ` -f json-tree` pyang plugin, it generates the tree .json;
* Using the ` -f cxml` pyang plugin, it saves the information for Yang Explorer[https://github.com/CiscoDevNet/yang-explorer].

Then, it calls `process-catalog-file.py` for all catalogs (from environment variable YANG_CATALOG_FILES set in yindex.env).

## process-catalog-file.py

## add-catalog-data.py

## pyang_plugin directory

This directory contains all PYANG plugins used by YangSearch.
