#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.client_daemon
@author Konstantin Andrusenko
@date December 4, 2012

This module contains the implementation of Idepositbox client daemon
This daemon is used in CLI user interface
"""
import os
import sys
import signal

DAEMON_PORT = 8880

client_dir = os.environ.get('IDB_LIB_PATH', None)
if not client_dir:
    client_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    third_party = os.path.join(client_dir, 'third-party')
    sys.path.insert(0, third_party)
else:
    sys.path.append(os.path.join(client_dir, 'lib-dynload'))

sys.path.insert(0, client_dir)


from nimbus_client.core.logger import logger

from id_client.web.web_server import MgmtServer
from id_client.idepositbox_client import IdepositboxClient

class IDClientDaemon:
    def __init__(self):
        signal.signal(signal.SIGINT, self.stop)
        self.server = MgmtServer('0.0.0.0', DAEMON_PORT, IdepositboxClient())

    def start(self):
        try:
            self.server.run()
        except Exception, err:
            logger.error('IDClientDaemon error: %s'%err)

    def stop(self, s, p):
        logger.info('Stopping IDClientDaemon...')
        try:
            self.server.stop()
            logger.info('IDClientDaemon is stopped')
        except Exception, err:
            logger.error('IDClientDaemon stopping error: %s'%err)


if __name__ == '__main__':
    try:
        IDClientDaemon().start()
    except Exception, err:
        logger.error('IDClientDaemon failed: %s'%err)
        sys.exit(1)
