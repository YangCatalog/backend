# YANG Search Data Maintenance

A cronjob is executed every 3 minutes and calls: `python3 process_changed_mods.py`

## process_changed_mods.py

Takes as optional argument: path to the configuration file

Read the JSON file YANG_CACHE_FILE for the list of modules (also making a .bak before truncating it to 0), this is the list of modules to be processed.

**Note:** the two JSON files are actually created by an external process calling the web service at /yang-search/metadata_update/

Finally, calls `build_yindex.py` 


## build_yindex.py

Build the list of all modules modified since the last `process_changed_mods.py` call:
## pyang_plugin directory

This directory contains all PYANG plugins used by YangSearch.
