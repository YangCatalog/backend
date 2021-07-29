Statistics
=====

This package contains a python script to create a statistics.html file:

  * template directory containing jinja template for html file
  * statistics.py containing script to get all statistics

The statistics script goes through all the files in the githup repo and also through all the
 modules populated in the confd catalog using the search api. It counts all the modules for 
 each sdo and vendor and it calculates percentage that pass the compilations.
 
This script will create a statistics.html file which will be automatically added to yc.o
at [https://www.yangcatalog.org/statistics.html](https://www.yangcatalog.org/statistics.html)

This html file is divided into four categories:
1. SDO and Opensource statistics
    - IETF
    - BBF
    - IEEE
    - MEF
    - Openconfig
    
1. Vendor statistics
    - Cisco
    - Ciena
    - Juniper
    - Huawei

1. Cisco version-platform compatibility
    - IOS-XR
    - IOS-XE
    - NX-OS

1. General statistics
    - Number of yang files in vendor directory with duplicates
    - Number of yang files in vendor directory without duplicates
    - Number of yang files in standard directory with duplicates
    - Number of yang files in standard directory without duplicates
    - Number of files parsed into yangcatalog
    - Number of unique files parsed into yangcatalog