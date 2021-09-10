# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import logging
import os


def get_logger(name: str, file_name_path: str = 'yang.log', level: int = logging.DEBUG):
    """Create formated logger with the specified name and store at path defined by
        'file_name_path' argument.
        Arguments:
            :param name             (str) set name of the logger.
            :param file_name_path   (str) filename and path where to save logs.
            :param level            (int) Optional - logging level of this logger.
            :return a logger with the specified name.
    """
    os.makedirs(os.path.dirname(file_name_path), exist_ok=True)
    exists = False
    if os.path.isfile(file_name_path):
        exists = True
    FORMAT = '%(asctime)-15s %(levelname)-8s %(filename)s %(name)5s => %(message)s - %(lineno)d'
    DATEFMT = '%Y-%m-%d %H:%M:%S'
    handler = logging.FileHandler(file_name_path)
    handler.setFormatter(logging.Formatter(FORMAT, DATEFMT))
    logger = logging.getLogger(name)
    logging.getLogger('elasticsearch').setLevel(logging.ERROR)
    logger.setLevel(level)
    if len(logger.handlers) == 0:
        logger.addHandler(handler)
    else:
        handler.close()
    # if file didn t exist we create it and now we can set chmod
    if not exists:
        os.chmod(file_name_path, 0o664)
    return logger
