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


def init_logger():
    logger = logging.getLogger('fabnet-client')

    logger.setLevel(logging.INFO)

    if sys.platform.startswith('win'):
        hdlr = logging.FileHandler(os.path.join(tempfile.gettempdir(), 'nimbusfs.log'))
    else:
        if sys.platform == 'darwin':
            log_path = '/var/run/syslog'
        else:
            log_path = '/dev/log'

        hdlr = logging.handlers.SysLogHandler(address=log_path,
                  facility=logging.handlers.SysLogHandler.LOG_DAEMON)

    formatter = logging.Formatter('fabnet-client %(levelname)s [%(threadName)s] %(message)s')
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

logger = init_logger()
