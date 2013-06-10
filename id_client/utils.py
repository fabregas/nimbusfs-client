#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.utils
@author Konstantin Andrusenko
@date May 31, 2013
"""
import os
import logging

from id_client.config import Config

config = Config()
log_dir = os.path.join(config.data_dir, 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

os.environ['LOG_FILE'] = os.path.join(log_dir, 'idepositbox.log')

from nimbus_client.core.utils import Subprocess
from nimbus_client.core.logger import LOGGER_NAME, lazy_traceback_log

logger = logging.getLogger('%s.%s'%(LOGGER_NAME, 'idepositbox'))
logger.traceback_debug = lambda: lazy_traceback_log(logger.debug)
logger.traceback_info = lambda: lazy_traceback_log(logger.info)
