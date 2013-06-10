#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.logger
@author Konstantin Andrusenko
@date August 20, 2012

This module contains the fabnet client logger initialization
"""
import os
import tempfile
import sys
import traceback
import StringIO
import logging, logging.handlers

LOGGER_NAME = 'nimbusfs'

def init_logger(log_file=None, logger_name=LOGGER_NAME):
    logger = logging.getLogger(logger_name)
    for hdlr in logger.handlers[:]:
        try:
            hdlr.flush()
            hdlr.close()
        except:
            pass
        logger.removeHandler(hdlr)

    logger.setLevel(logging.INFO)
    if log_file:
        hdlr = logging.FileHandler(log_file)
    else:
        if sys.platform.startswith('win'):
            hdlr = logging.FileHandler(os.path.join(tempfile.gettempdir(), 'nimbusfs.log'))
        else:
            if sys.platform == 'darwin':
                log_path = '/var/run/syslog'
            else:
                log_path = '/dev/log'

            hdlr = logging.handlers.SysLogHandler(address=log_path,
                      facility=logging.handlers.SysLogHandler.LOG_DAEMON)

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    logger.propagate = False
    logger.traceback_debug = lambda: lazy_traceback_log(logger.debug)
    logger.traceback_info = lambda: lazy_traceback_log(logger.info)

    return logger


class lazy_traceback_log(object):
    def __init__(self, logfunc):
        logfunc("%s", self)

    def __str__(self):
        buf = StringIO.StringIO()
        try:
            traceback.print_exc(file=buf)
            return buf.getvalue()
        finally:
            buf.close()

__log_file = os.environ.get('LOG_FILE', None)

logger = init_logger(__log_file)

