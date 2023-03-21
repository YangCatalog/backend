Automatic YANG modules push scripts
============================================

This package contains python scripts to process IETF and IANA YANG files:
  
- ietf_push

  Script automatically pushes new IETF RFC and draft yang modules to the GitHub repository:
  https://github.com/yang-catalog/yang. Old ones are removed and their naming is corrected to <name>@<revision>.yang.
  An e-mail with information about local update of new RFCs is sent to yangcatalog admin users if
  there are files to update. Message about new RFC yang modules is also sent to the Cisco Webex Teams,
  room: YANG Catalog Admin.
  There are also modules which won't be pushed into the repository, they are stored in the 
  ```/var/yang/ietf-exceptions/exceptions.dat``` file, currently, content of this file should be:
  ```
    ietf-foo@2016-03-20.yang
    ietf-rip@2020-02-20.yang
    example-dhcpv6-server-conf@2022-06-20.yang
    example-dhcpv6-class-select@2022-06-20.yang
    example-dhcpv6-opt-sip-serv@2022-06-20.yang
  ```

- iana_push

  Script automatically pushes new IANA-maintained yang modules to the GitHub repository: https://github.com/yang-catalog/yang.
  Old ones are removed and their naming is corrected to ```<name>@<revision>.yang```.
  There are also modules which won't be pushed into the repository, they are stored in the 
  ```/var/yang/ietf-exceptions/iana-exceptions.dat``` file, currently, content of this file should be:
  ```
    iana-if-type@2022-03-07.yang
    iana-if-type@2022-08-17.yang
    iana-if-type@2022-08-24.yang
  ```
