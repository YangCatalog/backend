Recovery
========

This package contains a python script to save or load all the modules

We need to specify an option to either save or load the modules.

1. Saving modules

    When saving modules it will create a json file with current
    date and time. This json file contains all the modules and
    its metadata that we have in yangcatalog. Option to save modules
    is "--type save" which is default option
2. Loading modules

    When loading modules we need to either provide path to a json
    file that contains all the modules and its metadata or it will
    load the file with latest date. Option to load modules is
    "--type load" which is not a default option