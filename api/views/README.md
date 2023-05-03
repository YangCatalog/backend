# YANG Catalog /api/views structure

---

### [admin.py](https://github.com/YangCatalog/backend/blob/master/api/views/admin.py)
* `/api/admin/login`
* `/admin`
* `/admin/login`
* `/api/admin/logout - ['POST']`
* `/api/admin/ping`
* `/api/admin/check - ['GET']`
* `/api/admin/directory-structure/read/<path\:direc> - ['GET']`
* `/api/admin/directory-structure - ['DELETE','GET']`
* `/api/admin/directory-structure/<path\:direc> - ['DELETE','PUT','GET']`
* `/api/admin/yangcatalog-nginx - ['GET']`
* `/api/admin/yangcatalog-nginx/<path\:nginx_file> - ['GET']`
* `/api/admin/yangcatalog-config - ['GET','PUT']`
* `/api/admin/logs - ['GET','POST']`
* `/api/admin/move-user - ['POST']`
* `/api/admin/users/<status> - ['POST','GET']`
* `/api/admin/users/<status>/id/<id> - ['DELETE','PUT']`
* `/api/admin/scripts/<script> - ['GET','POST']`
* `/api/admin/scripts - ['GET']`
* `/api/admin/disk-usage - ['GET']`


### [yang_search/yang_search.py](https://github.com/YangCatalog/backend/blob/master/api/views/yang_search/yang_search.py)
* `/api/yang-search/v2/grep_search - ['GET']`
* `/api/yang-search/v2/tree/<module_name> - ['GET']`
* `/api/yang-search/v2/tree/<module_name>@<revision> - ['GET']`
* `/api/yang-search/v2/impact-analysis - ['POST']`
* `/api/yang-search/v2/search - ['POST']`
* `/api/yang-search/v2/advanced-search - ['POST']`
* `/api/yang-search/v2/completions/<keyword>/<pattern> - ['GET']`
* `/api/yang-search/v2/show-node/<name>/<path\:path> - ['GET']`
* `/api/yang-search/v2/show-node/<name>/<path\:path>/<revision> - ['GET']`
* `/api/yang-search/v2/module-details/<module> - ['GET']`
* `/api/yang-search/v2/module-details/<module>@<revision> - ['GET']`
* `/api/yang-search/v2/draft-code-snippets/<draft_name> - ['GET']`
* `/api/yang-search/v2/yang-catalog-help - ['GET']`


### [health_check.py](https://github.com/YangCatalog/backend/blob/master/api/views/health_check.py)
* `/api/admin/healthcheck/services-list - ['GET']`
* `/api/admin/healthcheck/elk - ['GET']`
* `/api/admin/healthcheck/confd - ['GET']`
* `/api/admin/healthcheck/redis - ['GET']`
* `/api/admin/healthcheck/nginx - ['GET']`
* `/api/admin/healthcheck/yangre-admin - ['GET']`
* `/api/admin/healthcheck/yang-validator-admin - ['GET']`
* `/api/admin/healthcheck/yang-search-admin - ['GET']`
* `/api/admin/healthcheck/confd-admin - ['GET']`
* `/api/admin/healthcheck/redis-admin - ['GET']`
* `/api/admin/healthcheck/yangcatalog - ['GET']`
* `/api/admin/healthcheck/cronjobs - ['GET']`


### [notifications.py](https://github.com/YangCatalog/backend/blob/master/api/views/notifications.py)
* `/api/notifications/unsubscribe_from_emails/<path\:emails_type>/<path\:email> - ['GET']`


### [comparisons.py](https://github.com/YangCatalog/backend/blob/master/api/views/comparisons.py)
* `/api/services/file1=<name1>@<revision1>/check-update-from/file2=<name2>@<revision2> - ['GET']`
* `/api/services/diff-file/file1=<name1>@<revision1>/file2=<name2>@<revision2> - ['GET']`
* `/api/services/diff-tree/file1=<name1>@<revision1>/file2=<file2>@<revision2> - ['GET']`
* `/api/get-common - ['POST']`
* `/api/compare - ['POST']`
* `/api/check-semantic-version - ['POST']`


### [user_specific_module_maintenance.py](https://github.com/YangCatalog/backend/blob/master/api/views/user_specific_module_maintenance.py)
* `/api/register-user - ['POST']`
* `/api/modules/module/<name>,<revision>,<organization> - ['DELETE']`
* `/api/modules - ['DELETE','PUT', 'POST']`
* `/api/vendors/<path\:value> - ['DELETE']`
* `/api/platforms - ['PUT', 'POST']`
* `/api/job/<job_id> - ['GET']`


### [redis_search.py](https://github.com/YangCatalog/backend/blob/master/api/views/redis_search.py)
* `/api/fast - ['POST']`
* `/api/search/<path\:value> - ['GET']`
* `/api/search-filter/<leaf> - ['POST']`
* `/api/search-filter - ['POST']`
* `/api/contributors - ['GET']`
* `/api/search/vendor/<vendor> - ['GET']`
* `/api/search/vendors/<path\:value> - ['GET']`
* `/api/search/modules/<name>,<revision>,<organization> - ['GET']`
* `/api/search/modules - ['GET']`
* `/api/search/vendors - ['GET']`
* `/api/search/catalog - ['GET']`
* `/api/services/tree/<name>@<revision>.yang - ['GET']`
* `/api/services/reference/<name>@<revision>.yang - ['GET']`


### [yc_jobs.py](https://github.com/YangCatalog/backend/blob/master/api/views/yc_jobs.py)
* `/api/ietf - ['GET']`
* `/api/checkCompleteGithub - ['POST']`
* `/api/check-platform-metadata - ['POST']`
* `/api/get-statistics - ['GET']`
* `/api/problematic-drafts - ['GET']`