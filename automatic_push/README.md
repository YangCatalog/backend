Automatic YANG modules push scripts
============================================

This package contains python scripts to process IETF and openconfig YANG files:

- rfc_push

    This module contains functionality for pushing new/updated modules extracted from RFCs in the:
    https://github.com/yang-catalog/yang/ repo. There are also modules which won't be pushed into the repository,
    they are stored in the ```/var/yang/ietf-exceptions/exceptions.dat``` and ```/var/yang/ietf-exceptions/iana-exceptions.dat``` files.
    Currently, content of these files should be:
    ```
    exceptions.dat
  
    ietf-foo@2016-03-20.yang
    ietf-rip@2020-02-20.yang
    example-dhcpv6-server-conf@2022-06-20.yang
    example-dhcpv6-class-select@2022-06-20.yang
    example-dhcpv6-opt-sip-serv@2022-06-20.yang
  
  
    iana-exceptions.dat
  
    iana-if-type@2022-03-07.yang
    iana-if-type@2022-08-17.yang
    iana-if-type@2022-08-24.yang
    ```
