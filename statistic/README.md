Statistics
=====

This package contains a python script to create a statistics.html file:

  * [template](https://github.com/YangCatalog/backend/blob/master/statistic/template) directory containing jinja template for html file
  * [statistics.py](https://github.com/YangCatalog/backend/blob/master/statistic/statistics.py) script to get all statistics

The statistics script goes through all the files in the local clone of the [YangModels/yang](https://github.com/YangModels/yang)
GitHub repo and also through all the modules available in the Redis database using the search API. It counts all the modules for 
each SDO and vendor, and it calculates percentage that pass the compilations.
 
This script will create a statistics.html file which will be automatically added to yangcatalog at
[https://www.yangcatalog.org/stats/statistics.html](https://www.yangcatalog.org/stats/statistics.html)

This html file is divided into four categories:
1. SDO and Opensource statistics
    - IETF
    - BBF
    - IEEE
    - MEF
    - Openconfig
    
2. Vendor statistics
    - Cisco
    - Ciena
    - Juniper
    - Huawei

3. Cisco version-platform compatibility
    - IOS-XR
    - IOS-XE
    - NX-OS

4. General statistics
    - Number of yang files in vendor directory with duplicates
    - Number of yang files in vendor directory without duplicates
    - Number of yang files in standard directory with duplicates
    - Number of yang files in standard directory without duplicates
    - Number of files parsed into yangcatalog
    - Number of unique files parsed into yangcatalog

[runYANGallstats](https://github.com/YangCatalog/backend/blob/master/statistic/runYANGallstats.py)
===============

This is the python script to count all the yang files of the provided directory

use the `--rootdir` option to count all yang files from a path you provide

use the `--excludedir` option to exclude a directory with modules which you don't want to count

use the `--excludekeyword` option to exclude some keywords from the YANG module name.
 
use the `--removedup` option to remove duplicate YANG modules. Default is `False`.
