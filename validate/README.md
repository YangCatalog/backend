Validate
=====

This package contains a python script to validate user and give them appropriate rights.

When someone will use yangcatalog registration site
at [https://yangcatalog.org/create.php](https://yangcatalog.org/create.php) it will send a e-mail
message to admin users about "Request for access confirmation" and the user will be saved
in temporary database table with no access

Validate script will search through temporary created users in the database and prompt you
with several questions about them. This will let you decide which rights do you want to grant to
each user.

Questions are either with yes/no answers or you need to provide organization for sdo to which the
user has access to or you need to provide path to which user can create update or delete yang modules.

Questions are as follows:

1. Do they need vendor access?
   - if yes what is their vendor branch. Example:
        1. "cisco/xe/1631" only can make changes on cisco modules with platform xe and version 1631
        2. or you can simply say "cisco" which gives them right to make changes on any cisco module
2. Do they need sdo (model) access?
   - if yes what is their model organization

Finally it will create recapitulation with user name and access you are about to give them with yes no option.
If you choose yes it will move the user from temporary database table to real database table and it will write
provided access to the database.

This can be done from admin yangcatalog UI as well