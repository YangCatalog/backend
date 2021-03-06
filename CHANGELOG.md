## Backend Release Notes

* ##### vm.m.p - 2021-MM-DD

* ##### v3.2.1 - 2021-05-04

  * Sandbox: compare_databases.py script updated to compare in both ways [#266](https://github.com/YangCatalog/backend/issues/266)
  * Sandbox: revise_tree_type.py script to check all the modules tree types [#259](https://github.com/YangCatalog/backend/issues/259)
  * Crontab MAILTO variable set during Docker image build [deployment #72](https://github.com/YangCatalog/deployment/issues/72)
  * Schema creation fixed for YangModels/yang repository submodules [#256](https://github.com/YangCatalog/backend/issues/256)
  * api/checkComplete endpoint now will expect a request from Travis.com [#250](https://github.com/YangCatalog/backend/issues/250)
  * DELETE API endpoints for module deletion updated [#261](https://github.com/YangCatalog/backend/issues/261)
  * Sandbox: delete_modules.py script to delete modules based on condition [#260](https://github.com/YangCatalog/backend/issues/260)
  * loadJsonFiles.py script update - added files list to be skipped
  * Sandbox: check_semver.py script to check all the module schemas [#232](https://github.com/YangCatalog/backend/issues/232)

* ##### v3.2.0 - 2021-04-15

  * Verify argument set according to whether it is a prod or not for ES [#252](https://github.com/YangCatalog/backend/issues/252)
  * Python base image bumped to version 3.9 [deployment #66](https://github.com/YangCatalog/deployment/issues/66)
  * ietfYangDraftPull module scripts refactored - replaced subprocess calls [#248](https://github.com/YangCatalog/backend/issues/248)
  * Logs format modified - added filename information [#246](https://github.com/YangCatalog/backend/issues/246)
  * Hashing of the file content introduced [#245](https://github.com/YangCatalog/backend/issues/245)
  * lxml package version bumped
  * revise_semver.py sandbox script created [#242](https://github.com/YangCatalog/backend/issues/242)
  * Confd full check moved into separate scripts [#226](https://github.com/YangCatalog/backend/issues/226)

* ##### v3.1.0 - 2021-03-18

  * Unified the way how --check-update-from is used [#237](https://github.com/YangCatalog/backend/issues/237)
  * Tests for parse_semver() method [#235](https://github.com/YangCatalog/backend/issues/235)
  * Derived semantic version generation fixed [#231](https://github.com/YangCatalog/backend/issues/231)
  * Tests for resolveExpiration.py script [#230](https://github.com/YangCatalog/backend/issues/230)
  * Healthcheck update - ConfD full check [#226](https://github.com/YangCatalog/backend/issues/226)
  * Healthcheck update - Yangcatalog domains [#225](https://github.com/YangCatalog/backend/issues/225)
  * Sync Travis user before accessing repository [#221](https://github.com/YangCatalog/backend/issues/221)
  * resolveExpiration.py script improvements [#219](https://github.com/YangCatalog/backend/issues/219)

* ##### v3.0.1 - 2021-02-26

  * rsyslog and systemd added to Docker image build [deployment #48](https://github.com/YangCatalog/deployment/issues/48)
  * Tests for util.py script [#205](https://github.com/YangCatalog/backend/issues/205)
  * Prevention against missing modules in Elasticsearch [#212](https://github.com/YangCatalog/backend/issues/212)
  * Sandbox scripts added to seach debugging
  * Tests for runCapabilities.py script [#204](https://github.com/YangCatalog/backend/issues/204)
  * Response headers logic moved to NGINX config [#209] (https://github.com/YangCatalog/backend/issues/209)

* ##### v3.0.0 - 2021-02-10

  * Update pyang to version 2.4.0 [deployment #36]( https://github.com/YangCatalog/deployment/issues/36)
  * Update lxml to version 4.6.2
  * Tests for prepare.py script [#177](https://github.com/YangCatalog/backend/issues/177)
  * DraftPull.py additional info added to cronjob message log (whether new commit was created or not)
[#177](https://github.com/YangCatalog/backend/issues/177)
  * Explicitly set version of Python base image to 3.8
  * Tests for loadJsonFiles.py script [#181](https://github.com/YangCatalog/backend/issues/181)
  * Tests for capability.py script [#180](https://github.com/YangCatalog/backend/issues/180)
  * Tests for modules.py script [#179](https://github.com/YangCatalog/backend/issues/179)
  * Tests for flask backend API endpoints [#198](https://github.com/YangCatalog/backend/issues/198)
  * Multiple log files filtering [#184](https://github.com/YangCatalog/backend/issues/184)
  * Reading logs from .gz file [#193](https://github.com/YangCatalog/backend/issues/193)
  * Add rest functionalities for admin UI [#188](https://github.com/YangCatalog/backend/issues/188)
  * SSO to IETF and remove admin users database [#187](https://github.com/YangCatalog/backend/issues/187)
  * Switch to elasticsearch in AWS [deployment #38](https://github.com/YangCatalog/deployment/issues/38)
  * Add user reminder script[#190](https://github.com/YangCatalog/backend/issues/190)
  * Get status of cronjob done [#191](https://github.com/YangCatalog/backend/issues/191)
  * Add endpoint to update yangcatalog users in MariaDb [#192](https://github.com/YangCatalog/backend/issues/192)
  * Moved to Gunicorn from Uwsgi [deployment #39](https://github.com/YangCatalog/deployment/issues/39)
  * Use redis to index and get modules [#195](https://github.com/YangCatalog/backend/issues/195)
  * Add modification date of files into admin UI [#196](https://github.com/YangCatalog/backend/issues/196)
  * Remove load data caching [#197](https://github.com/YangCatalog/backend/issues/197)
  * Fix README.md
  * Update Dockerfile
  * Various major/minor bug fixes and improvements

* ##### v2.0.0 - 2020-08-14

  * Add moving users to another database functionaily [#185](https://github.com/YangCatalog/backend/issues/185)
  * Update of expiration metadata resolution
  * Creation of healthchecks [#202](https://github.com/YangCatalog/backend/issues/202)
  * Fix discrepancy in support platform/OS [#56](https://github.com/YangCatalog/backend/issues/56)
  * Creation of admin database for admin UI
  * Add admin/<some_path> endpoint for admin UI
  * Ignore integrity from parsing if not set [#201](https://github.com/YangCatalog/backend/issues/201)
  * Use of flask abort() [#200](https://github.com/YangCatalog/backend/issues/200)
  * Statistics script runs faster
  * Create blueprints in flask [#186](https://github.com/YangCatalog/backend/issues/186)
  * Validate yangcatalog user using admin UI [199](https://github.com/YangCatalog/backend/issues/199)
  * Start creating rest functionality for admin UI [#188](https://github.com/YangCatalog/backend/issues/188)
  * Update Dockerfile
  * Various major/minor bug fixes and improvements

* ##### v1.1.0 - 2020-07-16

  * Update recovery script
  * Update Pyang version
  * Update Dockerfile
  * Various major/minor bug fixes and improvements

* ##### v1.0.1 - 2020-07-03

  * Add special ID for each request in flask
  * Reload cache watcher [#203](https://github.com/YangCatalog/backend/issues/203)
  * Make receiver thread safe [#124](https://github.com/YangCatalog/backend/issues/124)
  * Create and close connection on each RabbitMq message [#125](https://github.com/YangCatalog/backend/issues/125)
  * Create more readable user messages [#90](https://github.com/YangCatalog/backend/issues/90)
  * Upgrade some library versions
  * Fix README.md
  * Update Dockerfile
  * Various major/minor bug fixes and improvements

* ##### v1.0.0 - 2020-06-23

  * Initial submitted version
