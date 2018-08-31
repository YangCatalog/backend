Automatic yang modules pull and push
====================================

This package contains a python scripts to process ietf and openconfig
yang files:

- draftPull

    This script serves as a automated tool to find all the new ietf
    yang DRAFT and RFC files. It will automatically push new files
    to github but ONLY DRAFT modules NO RFC modules. If there are
    new RFC modules yangcatalog admin users will receive an e-mail
    about such files.

- draftPullLocall

    This script serves as a automated tool to parse and populate all
    the new ietf DRAFT and RFC modules to yangcatalog.

- openconfigPullLocall

    This script serves as a automated tool to parse and populate all
    the new openconfig modules to yangcatalog.