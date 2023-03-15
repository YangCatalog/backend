Automatic YANG modules pull scripts
============================================

This package contains scripts to process IETF and openconfig YANG files:

- pull_local
    Cronjob tool that automatically runs populate.py over 4 different directories:
    I. RFC .yang modules -> standard/ietf/RFC path
    II. Draft .yang modules -> experimental/ietf-extracted-YANG-modules path
    III. IANA maintained modules -> standard/iana path
    IV. OpenConfig modules -> the https://github.com/openconfig/public repo
