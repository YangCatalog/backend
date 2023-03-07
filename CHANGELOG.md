## Backend Release Notes

* ##### v5.10.0 - 2023-03-07

  * draftPull.py and ianaPull.py moved to the automatic_push dir [#731](https://github.com/YangCatalog/backend/issues/731)
  * Logic for maintaining GitHub schema URLs removed [#722](https://github.com/YangCatalog/backend/issues/722)
  * Refactor: multiple TypeDict-s and dataclasses added [#693](https://github.com/YangCatalog/backend/issues/693)
  * Leap year replacementes in revision dates removed [#741](https://github.com/YangCatalog/backend/issues/741)
  * GitPython package version updated [#724](https://github.com/YangCatalog/backend/issues/724)
  * SDO organizations list updated [#733](https://github.com/YangCatalog/backend/issues/733)
  * New script: automatically push new RFC modules [#740](https://github.com/YangCatalog/backend/issues/740)
  * New endpoint: fetching code snippets found in documents [#723](https://github.com/YangCatalog/backend/issues/723)
  * Hiding modules from old drafts in impact analysis [#704](https://github.com/YangCatalog/backend/issues/704)

* ##### v5.9.0 - 2023-01-26

  * Bugfix: Minor fix to the create_admin.py script [#713](https://github.com/YangCatalog/backend/issues/713)
  * YANG Search: now possible to search only within RFC modules [frontend #13](https://github.com/YangCatalog/frontend/issues/13)
  * Missing schemas restored
  * All script configs moved into one config file [#712](https://github.com/YangCatalog/backend/issues/712)
  * job_log transformed into function decorator
  * Bugfix: Do not allow to push 404 HTML into YangModels/yang [#698](https://github.com/YangCatalog/backend/issues/698)
  * Bugfix: Extra Space removed from email when sending monthly users email [#697](https://github.com/YangCatalog/backend/issues/697)
  * Another chunk of improvements to the grep search [#692](https://github.com/YangCatalog/backend/issues/692)

* ##### v5.8.0 - 2022-12-20

  * API Endpoints moved to files to reduce yangSearch.py and ycSearch.py files [#649](https://github.com/YangCatalog/backend/issues/649)
  * all_modules directory cleared after running tests [#663](https://github.com/YangCatalog/backend/issues/663)
  * README.md with API endpoints structure added
  * Incorrect use of Elasticsearch scroll fixed
  * Unit tests covering module resolvers added [#690](https://github.com/YangCatalog/backend/issues/690)
  * Functionality for fetching all modules unified [#660](https://github.com/YangCatalog/backend/issues/660)
  * Grep search improved with "pagination" functionality [#602](https://github.com/YangCatalog/backend/issues/602)
  * GitHub Actions environment updated to use Ubuntu 22.04 [deployment #173](https://github.com/YangCatalog/deployment/issues/173)
  * Python base image bumped to version 3.10 [deployment #172](https://github.com/YangCatalog/deployment/issues/172)
  * Script for resetting a forgotten password added [#673](https://github.com/YangCatalog/backend/issues/673)
  * Improvements to remove_unused.py script [#667](https://github.com/YangCatalog/backend/issues/667)

* ##### v5.7.0 - 2022-11-11
  
  * Unused scripts removed from the sandbox directory [#647](https://github.com/YangCatalog/backend/issues/647)
  * Replicas disabled in Elasticsearch [#646](https://github.com/YangCatalog/backend/issues/646)
  * Aliases used now for accessing ES indices [#644](https://github.com/YangCatalog/backend/issues/644)
  * gevent package version updated [#643](https://github.com/YangCatalog/backend/issues/643)
  * setUpClass and tearDownClass methods use for tests [#641](https://github.com/YangCatalog/backend/issues/641)
  * Multiple improvements to te logging added [#638](https://github.com/YangCatalog/backend/issues/638)
  * Check whether module is unparsable before making request to ES [#633](https://github.com/YangCatalog/backend/issues/633)
  * Add implementations without need of re-parsing whole module [#611](https://github.com/YangCatalog/backend/issues/611)
  * Code reformatted according to the defined style guide [deployment #163](https://github.com/YangCatalog/deployment/issues/163)
  * Bugfix: skip parsing modules specified in the iana-exceptions file [#629](https://github.com/YangCatalog/backend/issues/629)
  * Text search (grep) functionality implemented [#602](https://github.com/YangCatalog/backend/issues/602)
  * Send email notification if jobs failed in YangModels/yang repository [#623](https://github.com/YangCatalog/backend/issues/623)
  * Functionality to avoid using synonyms while searching implemented [#603](https://github.com/YangCatalog/backend/issues/603)

* ##### v5.6.1 - 2022-10-10

  * Autocomplete functionality for IETF draft names [yangvalidator #107](https://github.com/YangCatalog/yang-validator-extractor/issues/107)

* ##### v5.6.0 - 2022-09-30

  * Bugfix: storing hashes for vendor modules [#609](https://github.com/YangCatalog/backend/issues/609)
  * ycclient compatibility tested [#551](https://github.com/YangCatalog/backend/issues/551)
  * create_admin.py sandbox script created [#614](https://github.com/YangCatalog/backend/issues/614)
  * Expiration resolver created [#600](https://github.com/YangCatalog/backend/issues/600)
  * New endpoint for unsubscribing from emails added [#607](https://github.com/YangCatalog/backend/issues/607)
  * Implementations resolver created [#571](https://github.com/YangCatalog/backend/issues/571)
  * Arguments of recovery scripts improved [#591](https://github.com/YangCatalog/backend/issues/591)
  * Only latest revision of module kept in dependents [#583](https://github.com/YangCatalog/backend/issues/583)
  * Logging improved for module deletion from ES [#573](https://github.com/YangCatalog/backend/issues/573)
  * Mutually exclusive arguments added to BaseScriptConfig [#587](https://github.com/YangCatalog/backend/issues/587)
  * Outdated mentions of ConfD removed [#574](https://github.com/YangCatalog/backend/issues/574)
  * Bare 'except:' statements removed [#576](https://github.com/YangCatalog/backend/issues/576)
  * Running redis_users_recovery.py once a month as a cronjob [#570](https://github.com/YangCatalog/backend/issues/570)
  * ciscosparkapi replaced with webexteamssdk package [#577](https://github.com/YangCatalog/backend/issues/577)
  * Send notification after starting populate.py script [#568](https://github.com/YangCatalog/backend/issues/568)
  * 'In Progress' status added to the job_log [#567](https://github.com/YangCatalog/backend/issues/567)
  * --simple flag added to the populate.py script [#622](https://github.com/YangCatalog/backend/issues/622)
  * Miliseconds removed from registration date (in payload body) [admin-ui #64](https://github.com/YangCatalog/admin_ui/issues/64)
  * String formatting changes to f-strings in multiple scripts
  * create fork remote in case it doesn't exist [#558](https://github.com/YangCatalog/backend/issues/558)
  * Simplify test data for dumper.py [#543](https://github.com/YangCatalog/backend/issues/543)

* ##### v5.5.0 - 2022-08-16

  * Unit tests covering parse_directory.py (runCapabilities) improved [#543](https://github.com/YangCatalog/backend/issues/543)
  * Unit tests covering modules.py improved [#543](https://github.com/YangCatalog/backend/issues/543)
  * Unit tests covering groupings.py improved [#543](https://github.com/YangCatalog/backend/issues/543)
  * Bugfix: resolving derived-semantic-version in some edge-cases [#548](https://github.com/YangCatalog/backend/issues/548)
  * schema property creation refactored [#538](https://github.com/YangCatalog/backend/issues/538)
  * Tracking API access using Matomo [deployment #151](https://github.com/YangCatalog/deployment/issues/151)
  * resolver classes introduced [#531](https://github.com/YangCatalog/backend/issues/531)

* ##### v5.4.0 - 2022-07-08

  * lxml package version bumped
  * Using SchemaParts dataclass for storing schema URL parts [#529](https://github.com/YangCatalog/backend/issues/529)
  * Various code improvements to the ietfYangDraftPull module
  * Impact analysis API endpoint source code optimized
  * Search for import files in openconfig/public repo [#528](https://github.com/YangCatalog/backend/issues/528)
  * Using IP versus domain name when composing URLs [deployment #141](https://github.com/YangCatalog/deployment/issues/141)
  * Bugfix: Use correct parsed yang object if yang file already parsed [#521](https://github.com/YangCatalog/backend/issues/521)
  * Bugfix: Loading Redis from backup
  * GET api/problematic-drafts API endpoint added [#517](https://github.com/YangCatalog/backend/issues/517)
  * Bugfix: Trying to hash file content if file does not exist

* ##### v5.3.0 - 2022-06-06

  * Fixed user reminder webex message [#517](https://github.com/YangCatalog/backend/issues/517)
  * Created iana-exceptions.dat file [#516](https://github.com/YangCatalog/backend/issues/516)
  * Updated running statistics.py over each ieee directories [#512](https://github.com/YangCatalog/backend/issues/512)
  * Parsing Ciena modules adjustments [#510](https://github.com/YangCatalog/backend/issues/510)
  * Page title added to the Bootstrap HTML pages [#507](https://github.com/YangCatalog/backend/issues/507)
  * Loading yangcatalog-api-prefix from config file [#504](https://github.com/YangCatalog/backend/issues/504)
  * Various code adjustments after config file update [deployment #135](https://github.com/YangCatalog/deployment/issues/135)
  * Notification to user if there was timeout during search [#498](https://github.com/YangCatalog/backend/issues/498)
  * Notification to user if there are many search results [#501](https://github.com/YangCatalog/backend/issues/501)
  * elk_fill.py script refactored
  * YANG Search - sort results by SDO first [#332](https://github.com/YangCatalog/backend/issues/332)
  * Fetching compilation results data more efficiently [#515](https://github.com/YangCatalog/backend/issues/515)

* ##### v5.2.0 - 2022-05-03

  * Type checking fixes with pyright [deployment #126](https://github.com/YangCatalog/deployment/issues/126)
  * Pyang update to version 2.5.3 [deployment #124](https://github.com/YangCatalog/deployment/issues/124)
  * No longer needed Dockerfile (documentation) deleted [deployment #123](https://github.com/YangCatalog/deployment/issues/123)
  * ESSnapshotsManager class created [#494](https://github.com/YangCatalog/backend/issues/494)
  * ESManager class created [#493](https://github.com/YangCatalog/backend/issues/493)  
  * Bugfix: Empty arrays passed as the files argument [#492](https://github.com/YangCatalog/backend/issues/492)
  * Deprecated "/fast" API endpoint removed completely [#491](https://github.com/YangCatalog/backend/issues/491)
  * SearchParams dataclass created [#490](https://github.com/YangCatalog/backend/issues/490)
  * repoUtil functionality refactored [#489](https://github.com/YangCatalog/backend/issues/489)
  * Elasticsearch updated to version 7.10 [#471](https://github.com/YangCatalog/backend/issues/471)
  * Bugfix: Closing RabbitMQ connection properly [#470](https://github.com/YangCatalog/backend/issues/470)
  * flask-oidc replaced with Flask-pyoidc library [#440](https://github.com/YangCatalog/backend/issues/440)

* ##### v5.1.0 - 2022-03-28

  * Directory structure for modules sent via API changed [#464](https://github.com/YangCatalog/backend/issues/464)
  * Elasticsearch AuthorizationException error handled [#462](https://github.com/YangCatalog/backend/issues/462)
  * User notified when module sent via API does not exist [#463](https://github.com/YangCatalog/backend/issues/463)
  * Elasticsearch indexing pipeline updated [#462](https://github.com/YangCatalog/backend/issues/462)
  * Files hashing for Openconfig modules enabled [#461](https://github.com/YangCatalog/backend/issues/461)
  * Various updates to the scripts in the ietfYangDraftPull module [#460](https://github.com/YangCatalog/backend/issues/460)
  * Various changes after YangModels/yang default branch rename [#459](https://github.com/YangCatalog/backend/issues/459)
  * Tests modified to run locally [#451](https://github.com/YangCatalog/backend/issues/451)
  * DirPaths TypedDict created for passing paths to the dirs as single argument
  * parseAndPopulate pipeline refactored completely
  * User reminder email formatted as HTML [#443](https://github.com/YangCatalog/backend/issues/443)
  * statistics.py script now also processing ETSI and IANA modules
  * JSON trees will no longer be stored with indentation [#458](https://github.com/YangCatalog/backend/issues/458)
  * YANG tree: show_node_path attribute added also for nodes [yangcatalog-ui #43](https://github.com/YangCatalog/yangcatalog-ui/issues/43)

* ##### v5.0.0 - 2022-02-02

  * Integrity checker script rework [#154](https://github.com/YangCatalog/backend/issues/154)
  * Data migrated from ConfD to Redis completely [#405](https://github.com/YangCatalog/backend/issues/405)
  * pyang context reset to decrease RAM usage of scripts [#436](https://github.com/YangCatalog/backend/issues/436)
  * Change ownership of yangvalidator cache directories [yangvalidator #80](https://github.com/YangCatalog/yang-validator-extractor/issues/80)
  * Handle broken paths in platform-metadata.json files [#422](https://github.com/YangCatalog/backend/issues/422)
  * Bugfix: Memory leak while parsing modules [#421](https://github.com/YangCatalog/backend/issues/421)
  * Pyang update to version 2.5.2 [deployment #113](https://github.com/YangCatalog/deployment/issues/113)
  * Calculate percentage of modules with metadata [#416](https://github.com/YangCatalog/backend/issues/416)
  * Adjustments to api/checkCompleteGithub endpoint [#435](https://github.com/YangCatalog/backend/issues/435)
  * Allow to store vendors into both ConfD and Redis in parallel [#405](https://github.com/YangCatalog/backend/issues/405)
  * Compressing backup files [#414](https://github.com/YangCatalog/backend/issues/414)
  * lxml package version bumped
  * prepare_environment script adjustments
  * receiver.py script refactored [#412](https://github.com/YangCatalog/backend/issues/412)
  * Bugfix: Fixed error while searching for some strings in yang-search [#407](https://github.com/YangCatalog/backend/issues/407)
  * Send email notification with data that failed to write to ConfD [#71](https://github.com/YangCatalog/backend/issues/71)

* ##### v4.3.0 - 2021-12-03

  * Allow to store modules into both ConfD and Redis in parallel [#405](https://github.com/YangCatalog/backend/issues/405)
  * Tests for receiver.py script [#404](https://github.com/YangCatalog/backend/issues/404)
  * Logging modules and vendors that failed to patch to the ConfD [#403](https://github.com/YangCatalog/backend/issues/403)
  * BaseScriptConfig created - rework of ScriptConfig functionality [#402](https://github.com/YangCatalog/backend/issues/402)
  * recovery script for the Redis user database added [#401](https://github.com/YangCatalog/backend/issues/401)
  * Repoutil tests reworked [#189](https://github.com/YangCatalog/backend/issues/189)
  * Various adjustments to healthcheck endpoints [#400](https://github.com/YangCatalog/backend/issues/400)
  * statistics.py script refactored [#387](https://github.com/YangCatalog/backend/issues/387)
  * MariaDB replaces with Redis as database for storing users [#377](https://github.com/YangCatalog/backend/issues/377)
  * Bugfix: Unnecessary arguments removed from script calls [#374](https://github.com/YangCatalog/backend/issues/374)

* ##### v4.2.1 - 2021-10-06

  * confdService for communication with ConfD added [#373](https://github.com/YangCatalog/backend/issues/373)
  * Use dump.rdb file to load data into Redis cache [#372](https://github.com/YangCatalog/backend/issues/372)
  * Remove old yangvalidator-v2-cache directories [#371](https://github.com/YangCatalog/backend/issues/371)
  * Bugfix: api/services/diff-file endpoint fixed [#370](https://github.com/YangCatalog/backend/issues/370)
  * Using static variables over backend application [#369](https://github.com/YangCatalog/backend/issues/369)
  * Remove old Mariadb backups, move ConfD backups [#368](https://github.com/YangCatalog/backend/issues/368)
  * MySQL updated to store motivation and registration date [#363](https://github.com/YangCatalog/backend/issues/363)
  * Slate documentation moved into separate Docker image [#358](https://github.com/YangCatalog/backend/issues/358)
  * validate.py script removed [#357](https://github.com/YangCatalog/backend/issues/357)
  * Create directory for log files if not exists [#353](https://github.com/YangCatalog/backend/issues/353)
  * Date of validation added to module compilation results html [sdo_analysis #98](https://github.com/YangCatalog/sdo_analysis/issues/98)

* ##### v4.2.0 - 2021-09-09

  * Scripts to process IANA-maintained modules created [#342](https://github.com/YangCatalog/backend/issues/342)
  * Bugfix: Incorrect path to some JSON files [#351](https://github.com/YangCatalog/backend/issues/351)
  * Github Actions webhook consuming [#336](https://github.com/YangCatalog/backend/issues/336)
  * Dockerfile reorganized - image build speed up [#350](https://github.com/YangCatalog/backend/issues/350)
  * Config loading simplified [deployment #96](https://github.com/YangCatalog/deployment/issues/96)

* ##### v4.1.0 - 2021-08-10

  * Use cached ytrees in to speed-up parse_semver() method [#312](https://github.com/YangCatalog/backend/issues/312)
  * Tests for admin.py script [#330](https://github.com/YangCatalog/backend/issues/330)
  * Unification of find_first_file methods [#318](https://github.com/YangCatalog/backend/issues/318)
  * More tests for modulesComplicatedAlgorithms.py script added [#235](https://github.com/YangCatalog/backend/issues/235)
  * admin.py script refactored [#329](https://github.com/YangCatalog/backend/issues/329)
  * Exceptions handling improved while indexing modules to ES [#265](https://github.com/YangCatalog/backend/issues/265)
  * modulesComplicatedAlgorithms.py script refactored [#328](https://github.com/YangCatalog/backend/issues/328)
  * ycSearch.py script refactored [#327](https://github.com/YangCatalog/backend/issues/327)
  * User registration notification email body changed [#326](https://github.com/YangCatalog/backend/issues/326)
  * Introduction of Github actions [#325](https://github.com/YangCatalog/backend/issues/325)
  * reviseTreeType.py script added to check nmda-compatible trees [#324](https://github.com/YangCatalog/backend/issues/324)
  * reviseSemver.py sandbox script coverted to cronjob [#323](https://github.com/YangCatalog/backend/issues/323)
  * Tests for ycJobs.py script [#322](https://github.com/YangCatalog/backend/issues/322)
  * Errors in READMEs and Documentation files fixed
  * Removed redundant "\n" in tooltip text [#293](https://github.com/YangCatalog/backend/issues/293)
  * Usage of Flask's built-in logger [#287](https://github.com/YangCatalog/backend/issues/287)
  * MySQLdb replaced by SQLAlchemy [#285](https://github.com/YangCatalog/backend/issues/285)
  * Recovery script for MariaDB added [#298](https://github.com/YangCatalog/backend/issues/298)

* ##### v4.0.0 - 2021-07-09

  * MAJOR UPDATE: YANG search API moved under backend repository
  * Bugfix: Text displaying for api/service/reference endpoint [#296](https://github.com/YangCatalog/backend/issues/296)
  * stats.json file places to persistent folder [#294](https://github.com/YangCatalog/backend/issues/294)
  * Pyang update to version 2.5.0 [deployment #85](https://github.com/YangCatalog/deployment/issues/85)
  * tree-type property generating changed for nmda-compatible tree types [#289](https://github.com/YangCatalog/backend/issues/289)
  * Healthcheck endpoints adjustments after minor changes in API
  * YangModels/yang repo forking changes in draftPull.py script [#283](https://github.com/YangCatalog/backend/issues/283)
  * Sandbox: find_conflicting_files.py script created [#301](https://github.com/YangCatalog/backend/issues/301)
  * Various existing tests updated
  * Removed manipulation with Travis in draftPull.py after migration [#300](https://github.com/YangCatalog/backend/issues/300)
  * TravisCI migrated from travis-ci.org to travis-ci.com [#250](https://github.com/YangCatalog/backend/issues/250)
  * yang2.amsl.com mailname replaced by yangcatalog.org [deployment #73](https://github.com/YangCatalog/deployment/issues/73)
  * Updated all the Flask dependecies [#299](https://github.com/YangCatalog/backend/issues/299)

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
