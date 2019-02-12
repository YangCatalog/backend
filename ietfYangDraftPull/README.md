Automatic yang modules pull and push
====================================

This package contains a python scripts to process IETF and openconfig YANG files:

- draftPull

    This script serves as a automated tool to find all the new IETF
    yang DRAFT and RFC files. It will automatically push new files
    to github but ONLY DRAFT modules NO RFC modules. If there are
    new RFC modules yangcatalog admin users will receive an e-mail
    about such files.

- draftPullLocal

    This script serves as a automated tool to parse and populate all
    the new IETF DRAFT and RFC modules to yangcatalog.

- openconfigPullLocal

    This script serves as a automated tool to parse and populate all
    the new openconfig modules to yangcatalog.

