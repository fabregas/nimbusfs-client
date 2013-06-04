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
import threading

DAEMON_PORT = 8880

if hasattr(sys,"frozen") and sys.frozen:
    third_party = os.path.dirname(os.path.abspath(sys.executable))
else:
    client_dir = os.environ.get('IDB_LIB_PATH', None)
    if not client_dir:
        client_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../')
    else:
        sys.path.append(os.path.join(client_dir, 'lib-dynload'))

    sys.path.insert(0, client_dir)
    third_party = os.path.join(client_dir, 'third-party')
    sys.path.insert(0, third_party)

if sys.platform == 'win32' and 'OPENSSL_EXEC' not in os.environ:
    os.environ['OPENSSL_EXEC'] = os.path.join(third_party, 'OpenSSL/bin/openssl.exe')

from nimbus_client.core.logger import logger

from id_client.web.web_server import MgmtServer
from id_client.idepositbox_client import IdepositboxClient

class Win32StopThread(threading.Thread):
    def __init__(self, stop_hdlr):
        threading.Thread.__init__(self)
        self.stop_hdlr = stop_hdlr

    def run(self):
        try:
            import win32pipe, win32file
            import win32file

            fileHandle = win32pipe.CreateNamedPipe(r'\\.\pipe\idepositbox_daemon_pipe',
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                1, 65536, 65536,300,None)


            win32pipe.ConnectNamedPipe(fileHandle, None)

            data = win32file.ReadFile(fileHandle, 4096)
            if data == (0, 'STOP'):
                self.stop_hdlr()
            win32pipe.DisconnectNamedPipe(fileHandle)
            win32file.CloseHandle(fileHandle)
        except Exception, err:
            logger.error('Win32StopThread error: %s'%err)


class IDClientDaemon:
    def __init__(self):
        signal.signal(signal.SIGINT, self.stop)
        if hasattr(sys,"frozen"):
            static_path = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'static')

            Win32StopThread(self.stop).start()
        else:
            static_path = None #default static path will be used
            signal.signal(signal.SIGINT, self.stop)
        self.server = MgmtServer('0.0.0.0', DAEMON_PORT, IdepositboxClient(), static_path)

    def start(self):
        try:
            self.server.run()
        except Exception, err:
            logger.error('IDClientDaemon error: %s'%err)
            logger.traceback_info()            

    def stop(self, s=None, p=None):
        logger.info('Stopping IDClientDaemon...')
        try:
            self.server.stop()
            logger.info('IDClientDaemon is stopped')
        except Exception, err:
            logger.error('IDClientDaemon stopping error: %s'%err)
            logger.traceback_info()            


if __name__ == '__main__':
    try:
        IDClientDaemon().start()
    except Exception, err:
        logger.error('IDClientDaemon failed: %s'%err)
        logger.traceback_info()            
        sys.exit(1)
