import argparse
import logging
import os
import typing as t

from utility import log
from utility.create_config import create_config

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices


def load_all_drafts(draft_dir: str) -> t.List[str]:
    return [filename[:-4] for filename in os.listdir(draft_dir) if filename[-4:] == '.txt']


def main():
    parser = argparse.ArgumentParser(
        description='Process drafts in draft directory')
    parser.add_argument('--config-path', type=str, default=os.environ['YANGCATALOG_CONFIG_PATH'],
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = create_config(config_path)
    is_prod = config.get('General-Section', 'is-prod')
    log_directory = config.get('Directory-Section', 'logs')

    if is_prod:
        ietf_drafts_dir = config.get(
            'Directory-Section', 'ietf-archive-drafts')
    else:
        ietf_drafts_dir = config.get('Directory-Section', 'ietf-drafts')

    logger = log.get_logger('process_drafts', os.path.join(
        log_directory, 'process-drafts.log'))
    logger.info('Starting process-drafts.py script')

    drafts = load_all_drafts(ietf_drafts_dir)
    logger.debug(drafts)

    logger.info('Trying to initialize Elasticsearch indices')
    es_manager = ESManager()
    for index in ESIndices:
        if not es_manager.index_exists(index):
            create_result = es_manager.create_index(index)
            logger.info(
                f'Index {index.value} created with message:\n{create_result}')

    logging.getLogger('elasticsearch').setLevel(logging.ERROR)

    done = 0
    for i, draft_name in enumerate(drafts):
        draft = {'draft': draft_name}

        logger.info(
            f'Indexing draft {draft_name} - draft {i+1} out of {len(drafts)}')

        try:
            if not es_manager.document_exists(ESIndices.DRAFTS, draft):
                # Add draft to index only if it is not already there
                es_manager.index_module(ESIndices.DRAFTS, draft)
                logger.info(f'added {draft_name} to index')
                done += 1
            else:
                logger.info(
                    f'skipping - {draft_name} is already in index')
        except Exception:
            logger.exception(
                f'Problem while processing draft {draft_name}')
    logger.info(f'Added {done} drafts to ElasticSearch')
    logger.info('Job finished successfully')


if __name__ == '__main__':
    main()
