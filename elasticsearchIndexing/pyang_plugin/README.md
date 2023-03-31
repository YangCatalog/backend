# PYANG plugins

This directory contains all PYANG plugins used by Yang Search. It can be referenced by the environment variable `$PYANG_PLUGINPATH`.
All the PYANG plugins should only be placed in the `$PYANG_PLUGINPATH` directory.

## [json_tree.py](https://github.com/YangCatalog/backend/blob/master/elasticsearchindexing/pyang_plugin/json_tree.py)

PYANG plugin for generating a JSON-formatted output of the data node hierarchy of the YANG modules.

## [yang_catalog_index_es.py](https://github.com/YangCatalog/backend/blob/master/elasticsearchindexing/pyang_plugin/yang_catalog_index_es.py)

PYANG plugin to generate the Elasticsearch data for indexing from modules.
