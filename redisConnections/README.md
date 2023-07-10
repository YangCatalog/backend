# Redis

Modules for interacting with our Redis databases.

`redis_user_notifications_connection.py` manages a list of email adresses which have opted out of receiving emails from module-compilation.

`redis_users_connection.py` manages YANG Catalog's user database, registering new users, checking their assigned rights, etc..

`redisConnection.py` manages YANG Catalog's main database with module and vendor data.
