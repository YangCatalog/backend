# Parse and Populate

This package contains python scripts to parse yang files
and consequently populate them to ConfD and Redis. Two main scripts
can be called:

## runCapabilites script

   This script can be called if we don't want to populate parsed
   metadata to ConfD right away but we just want to see what metadata
   we get out of a specific sdo directory or vendor capabilities files.

   This is also used if we want to create an integrity.html file using
   --run-integrity option. This will go through all the yang files
   and find all the problems with them like missing includes or imports,
   wrong namespaces, wrong revisions, missing or extra files in folders
   with capabilities.xml files, etc...

   Look for options in [runCapabilities](runCapabilities.py) before
   starting to parse yang modules. Two important options are the --dir
   option which lets you decide which directory with yang files you
   need to parse and the --sdo option which will let the script know that
   it should look for capabilites.xml files if it is set to False.

   If we are parsing SDO files, the script will go through all the modules
   in the directory and will parse each yang file and its dependents
   ignoring all the vendor metadata. If we are parsing vendor files like
   cisco's, it will look for capabilities.xml files and platform-metadata.json
   files to get all the vendor information like platform, software-version, software-flavor
   etc...

## populate script

   This script is called either by an admin user to manually populate data
   of a certain directory or by the API when other users would like to contribute
   to yangcatalog. Also when there are new yang modules added to the Github
   repository, this script will be automatically called after the API
   loads all the new yang modules from the Github repository.

   At the beginning this script will call the above mentioned script called
   runCapabilities.py and when that is done it should create temporary json
   files that needs to be populated to ConfD. After it populates ConfD
   it will restart the API so it can load all the new metadata into its cache.
   This script will also alert the yang-search/metadata_update script about
   new modules so it can parse the modules and save this
   data to the database. After that, this script will start to run more
   complicated algorithms on those parsed yang files. This will extract
   dependents, semantic versioning and tree types. When this is parsed it
   will once again populate ConfD and restart API so we have all the
   metadata of the yang files available.

   Look for options in [populate](populate.py) before starting to parse
   and populate yang modules. Make sure that all the ports, protocols
   and ip addresses are set correctly.

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
