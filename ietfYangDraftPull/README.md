Automatic YANG modules pull and push scripts
============================================

This package contains a python scripts to process IETF and openconfig YANG files:

- draftPull

    Cronjob tool that automatically pushes new IETF
    draft yang modules to the Github repository. Old ones
    are removed and naming is corrected to <name>@<revision>.yang.
    New IETF RFC modules are checked too, but they are not automatically added.
    E-mail is sent to yangcatalog admin users if such thing occurs.
    Message about new RFC or DRAFT yang modules is also sent
    to the Cisco Webex Teams, room: YANG Catalog Admin.

- draftPullLocal

    Cronjob tool that automatically runs populate.py over 3 different directories:
    I. RFC .yang modules -> standard/ietf/RFC path
    II. Draft .yang modules -> experimental/ietf-extracted-YANG-modules path
    III. IANA maintained modules -> standard/iana path

- ianaPull

    Cronjob tool that automatically pushes new IANA-maintained
    yang modules to the Github YangModels/yang repository.
    Old ones are removed and naming is corrected to <name>@<revision>.yang.

- openconfigPullLocal

    Cronjob tool that automatically runs populate.py for all new openconfig modules.
