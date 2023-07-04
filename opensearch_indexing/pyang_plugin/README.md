# PYANG plugins

This directory contains all PYANG plugins used by Yang Search. It can be referenced by the environment variable `$PYANG_PLUGINPATH`.
All PYANG plugins should be placed in the `$PYANG_PLUGINPATH` directory.

## [json_tree.py](https://github.com/YangCatalog/backend/blob/master/opensearch_indexing/pyang_plugin/json_tree.py)

PYANG plugin for generating a JSON-formatted output of the data node hierarchy of the YANG modules.

## [yang_catalog_index_opensearch.py](https://github.com/YangCatalog/backend/blob/master/opensearch_indexing/pyang_plugin/yang_catalog_index_opensearch.py)

PYANG plugin to generate the OpenSearch data from modules for indexing.
