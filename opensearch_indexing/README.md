# YANG Search Data Maintenance

## [process_changed_mods.py](https://github.com/YangCatalog/backend/blob/master/opensearch_indexing/process_changed_mods.py)

Executed every 3 minutes by the cronjob. Takes as optional argument `--config-path` - path to the configuration file.

Reads two files: `changes-cache` and `delete-cache` (their actual paths can be found in the configuration file by these names)
with new/changed and deleted modules respectively, making `.bak` file backups before truncating them to 0. Then all the deleted
modules are being deleted from all indices and the new/changed modules are indexed in the `YINDEX` and `AUTOCOMPLETE` indices
with the help of the [build_yindex.py](https://github.com/YangCatalog/backend/blob/master/opensearch_indexing/build_yindex.py) module.

**Note:** `changes-cache` and `delete-cache` files are created inside the
[populate.py](https://github.com/YangCatalog/backend/blob/master/parseAndPopulate/populate.py) script

## [build_yindex.py](https://github.com/YangCatalog/backend/blob/master/opensearch_indexing/build_yindex.py)

Contains functionality to parse a module data using the custom pyang plugin: [yang_catalog_index_opensearch.py](https://github.com/YangCatalog/backend/blob/master/opensearch_indexing/pyang_plugin/yang_catalog_index_opensearch.py)
and add the module data in the `YINDEX` and `AUTOCOMPLETE` indices, previously deleting the module data from these indices.

## [process-drafts.py](https://github.com/YangCatalog/backend/blob/master/opensearch_indexing/process-drafts.py)

Script run by the cronjob to add new drafts to the `DRAFTS` OpenSearch index.
