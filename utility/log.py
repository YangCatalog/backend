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
import stat

def get_logger(name, file_name_path='yang.log'):
    """Create formated logger with name of file yang.log
        Arguments:
            :param file_name_path: filename and path where to save logs.
            :param name :  (str) Set name of the logger.
            :return a logger with the specified name.
    """
    # check if file exists
    exists = False
    if os.path.isfile(file_name_path):
        exists = True
    FORMAT = '%(asctime)-15s %(levelname)-8s %(name)5s => %(message)s - %(lineno)d'
    DATEFMT = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(datefmt=DATEFMT, format=FORMAT, filename=file_name_path, level=logging.INFO)
    logger = logging.getLogger(name)
    # if file didn t exist we create it and now we can set chmod
    if not exists:
        os.chmod(file_name_path, 0o664 | stat.S_ISGID)
    return logger
