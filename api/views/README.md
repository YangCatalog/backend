# YANG Catalog /api/views structure

---

#### admin/admin.py
* /admin
* /admin/login
* /api/admin/login
* /api/admin/logout
* /api/admin/ping
* /api/admin/check
* /api/admin/directory-structure
* /api/admin/yangcatalog-nginx
* /api/admin/yangcatalog-config
* /api/admin/logs
* /api/admin/move-user
* /api/admin/users/\<status\>
* /api/admin/users/\<status\>/id/\<id\>
* /api/admin/scripts/\<script\>
* /api/admin/scripts
* /api/admin/disk-usage

#### comparisons/comparisons.py
* /api/services/\<name1\>@\<revision1\>/check-update-from/\<name2\>@\<revision2\>
* /api/services/diff-file/\<name1\>@\<revision1\>/\<name2\>@\<revision2\>
* /api/services/diff-tree/\<name1\>@\<revision1\>/\<name2\>@\<revision2\>
* /api/get-common
* /api/compare
* /api/check-semantic-version

#### healthCheck/healthCheck.py
* /api/admin/healthcheck/services-list
* /api/admin/healthcheck/elk
* /api/admin/healthcheck/confd
* /api/admin/healthcheck/redis
* /api/admin/healthcheck/nginx
* /api/admin/healthcheck/rabbitmq
* /api/admin/healthcheck/yangre-admin
* /api/admin/healthcheck/yang-validator-admin
* /api/admin/healthcheck/yang-search-admin
* /api/admin/healthcheck/confd-admin
* /api/admin/healthcheck/redis-admin
* /api/admin/healthcheck/yangcatalog
* /api/admin/healthcheck/cronjobs

#### notifications/notifications.py
* /api/notifications/unsubscribe_from_emails/\<path:emails_type\>/\<path:email\>

#### userSpecificModuleMaintenance/moduleMaintenance.py
* /api/register-user
* /api/modules
* /api/module/\<name\>,\<revision\>,\<organization\>
* /api/vendors/\<path:value\>
* /api/platforms
* /api/job/\<job_id\>

#### yangSearch/yangSearch.py
* /api/yang-search/v2/grep_search
* /api/yang-search/v2/tree/\<module_name\>
* /api/yang-search/v2/tree/\<module_name\>@\<revision\>
* /api/yang-search/v2/impact-analysis
* /api/yang-search/v2/search
* /api/yang-search/v2/completions/\<keyword\>/\<pattern\>
* /api/yang-search/v2/show-node/\<name\>/\<path:path\>
* /api/yang-search/v2/show-node/\<name\>/\<path:path\>/\<revision\>
* /api/yang-search/v2/module-details/\<module\>
* /api/yang-search/v2/module-details/\<module\>@\<revision\>
* /api/yang-search/v2/yang-catalog-help

#### ycJobs/ycJobs.py
* /api/ietf
* /api/checkCompleteGithub
* /api/checkComplete
* /api/check-platform-metadata
* /api/get-statistics
* /api/problematic-drafts

#### redisSearch/redisSearch.py
* /api/fast
* /api/search/\<path:value\>
* /api/search-filter/\<leaf\>
* /api/search-filter
* /api/contributors
* /api/search/vendor/\<vendor\>
* /api/search/vendors/\<path:value\>
* /api/search/modules/\<name\>,\<revision\>,\<organization\>
* /api/search/modules
* /api/search/vendors
* /api/search/catalog
* /api/services/tree/\<name\>@\<revision\>.yang
* /api/services/reference/\<name\>@\<revision\>.yang
