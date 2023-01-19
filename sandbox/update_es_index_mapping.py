"""Update Elasticsearch index's mapping"""

import argparse
import json
import os

from elasticsearchIndexing.es_manager import ESManager
from utility import log
from utility.create_config import create_config


def main():
    config = create_config()
    logger = log.get_logger(
        'update_es_index_mapping',
        os.path.join(config.get('Directory-Section', 'logs'), 'sandbox.log'),
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=str, required=True, help='Index to update')
    parser.add_argument(
        '--new-mapping-path',
        type=str,
        required=True,
        help=(
            'Path to json file containing new mapping. The mapping structure should be like this: '
            '{'
            '    "properties": {'
            '        "name": {'
            '            "type": "text",'
            '            "fields": {'
            '               "keyword": {'
            '                   "type": "keyword",'
            '                   "ignore_above": 256'
            '               }'
            '            }'
            '        },'
            '        ...other fields...'
            '}'
        ),
    )
    args = parser.parse_args()
    es = ESManager().es
    with open(args.new_mapping_path, 'r') as new_mapping_file:
        new_mapping_body = json.load(new_mapping_file)
    es.indices.put_mapping(index=args.index, body=new_mapping_body)
    logger.info(
        f'{args.index} index is updated and now has the following mapping:\n{es.indices.get_mapping(index=args.index)}',
    )


if __name__ == '__main__':
    main()
