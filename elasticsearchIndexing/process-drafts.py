import argparse
import logging
import os
import typing as t

from utility import log
from utility.create_config import create_config

from elasticsearchIndexing.es_manager import ESManager
from elasticsearchIndexing.models.es_indices import ESIndices


def load_all_drafts(draft_dir: str) -> t.List[str]:
    drafts = []
    for filename in os.listdir(draft_dir):
        if filename[-4:] == '.txt':  # if file name has .txt format
            # Return only name of the draft
            drafts.append(filename[:-4])
    return drafts


def main():
    parser = argparse.ArgumentParser(
        description='Process drafts in draft directory')
    parser.add_argument('--config-path', type=str, default=os.environ['YANGCATALOG_CONFIG_PATH'],
                        help='Set path to config file')
    args = parser.parse_args()
    config_path = args.config_path
    config = create_config(config_path)
    log_directory = config.get('Directory-Section', 'logs')
    ietf_drafts_dir = config.get('Directory-Section', 'ietf-drafts')

    LOGGER = log.get_logger('process_drafts', os.path.join(
        log_directory, 'process-drafts.log'))
    LOGGER.info('Starting process-drafts.py script')

    drafts = load_all_drafts(ietf_drafts_dir)
    print(drafts)

    LOGGER.info('Trying to initialize Elasticsearch indices')
    es_manager = ESManager()
    for index in ESIndices:
        if not es_manager.index_exists(index):
            create_result = es_manager.create_index(index)
            LOGGER.info('Index {} created with message:\n{}'.format(
                index.value, create_result))

    logging.getLogger('elasticsearch').setLevel(logging.ERROR)

    for i, draft_name in enumerate(drafts):
        draft = {'draft': draft_name}

        LOGGER.info('yindex on draft {}. module {} out of {}'.format(
            draft_name, i, len(drafts)))

        try:
            es_manager.index_module(ESIndices.DRAFTS, draft)
        except Exception:
            LOGGER.exception(
                'Problem while processing draft {}'.format(draft_name))

    LOGGER.info('Job finished successfully')


if __name__ == '__main__':
    main()
