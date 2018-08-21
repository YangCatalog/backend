# searching for file based on pattern or pattern_with_revision
import fnmatch
import os

import tools.utility.log as lo
from tools.utility import yangParser

LOGGER = lo.get_logger('util')


def get_curr_dir(f):
    LOGGER.debug('{}'.format(os.getcwd()))
    return os.getcwd()


def find_first_file(directory, pattern, pattern_with_revision):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern_with_revision):
                filename = os.path.join(root, basename)
                return filename
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                try:
                    revision = yangParser.parse(filename).search('revision')[0]\
                        .arg
                except:
                    revision = '1970-01-01'
                if '*' not in pattern_with_revision:
                    if revision in pattern_with_revision:
                        return filename
                else:
                    return filename
