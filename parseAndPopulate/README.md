# Parse and Populate

This package contains a python scripts to parse yang files
and consequently to populate them to confd. Two main scripts
can be called in here:

## runCapabilites script

   This script can be called if we don t want top populate parsed
   metadata to confd right away but we just want to see what metadata
   do we get out of specific sdo directory or vendor capabilities files.

   This is also used if we want to create integrity.html file using
   --run-integrity option. This will go through all the yang files
   and finds all the problems with them like missing includes or imports,
   wrong namespace, wrong revision, missing or extra files from folder
   with capabilities.xml files, etc...

   Look for options in [runCapabilities](runCapabilities.py) before
   starting to parse yang modules. Two main options are the --dir
   option which lets you decide which directory with yang files you
   need to parse and --sdo option which will let the script know that
   it should look for capabilites.xml files if it is set to False.

   If we are parsing sdo files script will go through all the modules
   in the directory and will parse each yang file and its dependents
   ignoring all the vendor metadata. If we are parsing vendor files like
   cisco it will look for capabilities.xml file and platform-metadata.json
   file to get all the vendor information like platform, version, flavor
   etc...

## populate script

   This script is called either by admin user to manually populate data
   on certain directory or by api when other users would like to contribute
   to yangcatalog. Also when there are new yang modules added to github
   repository, this script will be automatically called after api will
   load all the new yang modules from the github repository.

   This script at the beginning will call the above mention script called
   runCapabilities and when that is done it should create temporary json
   files that needs to be populated to confd. After it populates the confd
   it will restart api so it can load all the new metadata to its cache.
   This script will also alert yang-search/metadata_update script about
   new modules so it can parse the modules for it purpose and save those
   data to database. After that, this script will start to run more
   complicated algorithms on just parsed yang files. These metadata are
   dependents, semantic versioning and tree type. When it is parsed it
   will once again populate confd and restart api so we have all the
   available metadata to yang files.

   Look for options in [populate](populate.py) before starting to parse
   and populate yang modules. Make sure that all the ports, protocols
   and ip addresses are set correctly.

For example for all SDO (known in December 2018):
```
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/bbf--notify-indexing --force-indexing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/ieee --notify-indexing --force-indexing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/ietf --notify-indexing --force-indexing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/mef --notify-indexing --force-indexing
python populate.py --sdo  --dir /var/yang/nonietf/yangmodels/yang/standard/odp --notify-indexing --force-indexing
```
