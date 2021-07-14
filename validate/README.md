Validate
=====

This package contains a python script to validate a user and give them appropriate rights.

When someone uses the yangcatalog registration site
at [https://yangcatalog.org/create.php](https://yangcatalog.org/create.php) it sends an e-mail
message to admin users about "Request for access confirmation" and the user will be saved
in a temporary database table with no access

The validate script will search through temporarily created users in the database and prompt you
with several questions about them. This will let you decide which rights you want to grant to
each user.

Questions are either have yes/no answers or you need to provide an organization for sdo to which the
user has access to or you need to provide a path to which user can create update or delete yang modules.

Questions are as follows:

1. Do they need vendor access?
   - if yes what is their vendor branch. Example:
        1. "cisco/xe/1631" can only make changes on cisco modules with platform xe and version 1631
        2. or you can simply say "cisco" which gives them right to make changes to any cisco module
2. Do they need sdo (model) access?
   - if yes what is their model organization

Finally it will create a recapitulation with the user name and access you are about to give them with a yes/no option.
If you choose yes it will move the user from the temporary database table to the real database table and  write
the provided access to the database.

This can be done from the admin yangcatalog UI as well