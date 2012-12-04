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
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

client_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
third_party = os.path.join(client_dir, 'third-party')

sys.path.insert(0, client_dir)
sys.path.insert(0, third_party)

from nimbus_client.core.logger import logger
from id_client.idepositbox_client import IdepositboxClient, \
            CS_STARTED, CS_STOPPED

STATUS_PATH = '/status'
SYNC_STAT_PATH = '/sync_status'
START_PATH = '/start_client'
STOP_PATH = '/stop_client'

DAEMON_PORT = 1812


class IDClientHandler(BaseHTTPRequestHandler):
    client = None
    def do_GET(self):
        logger.info('GET %s'%self.path)
        if self.path == STATUS_PATH:
            self.send_response(200)
            self.end_headers()
            if IDClientHandler.client:
                self.wfile.write(IDClientHandler.client.status)
            else:
                self.wfile.write(CS_STOPPED)
        elif self.path == SYNC_STAT_PATH:
            self.send_response(200)
            self.end_headers()
            if IDClientHandler.client:
                ops = IDClientHandler.client.nibbler.inprocess_operations()
                for op in ops:
                    self.wfile.write('[%s] %s\n'%(op.op_type, op.file_name))
        else:
            self.send_error(404, 'Invalid request')

    def do_POST(self):
        logger.info('POST %s'%self.path)
        try:
            if self.path == START_PATH:
                if IDClientHandler.client:
                    raise Exception('IdepositboxClient is already started!')

                length = int(self.headers['Content-Length'])
                ks_passwd = self.rfile.read(length)
                if not ks_passwd:
                    raise Exception('Key storage password expected!')

                client = IdepositboxClient()
                client.start(ks_passwd)
                if client.status != CS_STARTED:
                    raise Exception('ERROR! IdepositboxClient does not started')

                IDClientHandler.client = client
            elif self.path == STOP_PATH:
                if IDClientHandler.client:
                    IDClientHandler.client.stop()
                    IDClientHandler.client = None
            else:
                raise Exception('Invalid request')

            self.send_response(200)
            self.end_headers()
        except Exception, err:
            logger.error('POST error: %s'%err)
            self.send_error(500, str(err))
            self.end_headers()


class IDClientDaemon:
    def __init__(self):
        signal.signal(signal.SIGINT, self.stop)
        self.server = HTTPServer(('127.0.0.1', DAEMON_PORT), IDClientHandler)

    def start(self):
        try:
            self.server.serve_forever()
        except Exception, err:
            logger.error('IDClientDaemon error: %s'%err)

    def stop(self, s, p):
        logger.info('Stopping IDClientDaemon...')
        try:
            if IDClientHandler.client:
                IDClientHandler.client.stop()

            self.server.socket.close()
            logger.info('IDClientDaemon is stopped')
        except Exception, err:
            logger.error('IDClientDaemon stopping error: %s'%err)


if __name__ == '__main__':
    try:
        IDClientDaemon().start()
    except Exception, err:
        sys.stderr.write('IDClientDaemon failed: %s'%err)
        sys.exit(1)
