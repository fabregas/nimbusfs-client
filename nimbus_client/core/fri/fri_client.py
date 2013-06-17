#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package fabnet.core.fri_client
@author Konstantin Andrusenko
@date December 27, 2012

This module contains the implementation of FriClient class.
"""
import socket
import ssl

from constants import RC_ERROR, RC_UNEXPECTED, FRI_CLIENT_TIMEOUT, FRI_CLIENT_READ_TIMEOUT

from fri_base import FabnetPacket, FabnetPacketResponse, FriException
from socket_processor import SocketProcessor

class FriClient:
    """class for calling asynchronous operation over FRI protocol"""
    def __init__(self, is_ssl=None, cert=None, session_id=None):
        self.is_ssl = is_ssl
        self.certificate = cert
        self.session_id = session_id

    def __int_call(self, node_address, packet, conn_timeout, read_timeout=None):
        proc = None

        try:
            address = node_address.split(':')
            if len(address) != 2:
                raise FriException('Node address %s is invalid! ' \
                            'Address should be in format <hostname>:<port>'%node_address)
            hostname = address[0]
            try:
                port = int(address[1])
                if 0 > port > 65535:
                    raise ValueError()
            except ValueError:
                raise FriException('Node address %s is invalid! ' \
                            'Port should be integer in range 0...65535'%node_address)

            if not isinstance(packet, FabnetPacket):
                raise Exception('FRI request packet should be an object of FabnetPacket')

            packet.session_id = self.session_id

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(conn_timeout)

            if self.is_ssl:
                sock = ssl.wrap_socket(sock)

            sock.connect((hostname, port))

            proc = SocketProcessor(sock, self.certificate)

            if read_timeout:
                sock.settimeout(read_timeout)

            resp = proc.send_packet(packet, wait_response=True)

            return resp
        finally:
            if proc:
                proc.close_socket()


    def call(self, node_address, packet, timeout=FRI_CLIENT_TIMEOUT):
        try:
            packet = self.__int_call(node_address, packet, timeout, FRI_CLIENT_READ_TIMEOUT)

            return packet.ret_code, packet.ret_message
        except Exception, err:
            return RC_ERROR, '[FriClient][%s] %s' % (err.__class__.__name__, err)


    def call_sync(self, node_address, packet, timeout=FRI_CLIENT_TIMEOUT):
        try:
            packet.sync = True
            packet = self.__int_call(node_address, packet, timeout, FRI_CLIENT_READ_TIMEOUT)

            return packet
        except Exception, err:
            return FabnetPacketResponse(ret_code=RC_ERROR, ret_message='[FriClient][%s] %s' % (err.__class__.__name__, err))

