#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package fabnet.core.socket_processor
@author Konstantin Andrusenko
@date December 28, 2012

This module contains the implementation of SocketBasedChunks and  SocketProcessor classes.
"""
import socket

from constants import BUF_SIZE, RC_REQ_CERTIFICATE, FRI_PACKET_INFO_LEN
from fri_base import FriBinaryProcessor, FabnetPacketRequest, FriException,\
                        FriBinaryData, RamBasedBinaryData, FabnetPacket


class SocketBasedChunks(FriBinaryData):
    def __init__(self, socket_processor, chunks_count):
        self.__sock_proc = socket_processor
        self.__chunks_count = chunks_count
        self.__last_idx = 0

    def chunks_count(self):
        return self.__chunks_count

    def get_next_chunk(self):
        if self.__last_idx >= self.__chunks_count:
            return None

        try:
            packet, bin_data = self.__sock_proc.read_next_packet()
            self.__last_idx += 1

            if packet.binary_chunk_idx > packet.binary_chunk_cnt:
                raise FriException('Chunk index is bigger than chunks count (%s>%s)'%(idx, cnt))

            if self.__last_idx == self.__chunks_count:
                self.__sock_proc.allow_close_socket()

            return bin_data
        except Exception, err:
            self.__sock_proc.allow_close_socket()
            raise err


class SocketProcessor:
    def __init__(self, sock, cert=None):
        self.__sock = sock
        self.__rest_data = ''
        self.__cert = cert
        self.__can_close_socket = False #socket can be closed (no pending chunks)
        self.__need_sock_close = False #socket should be closed (after all chunks received)

    def read_next_packet(self):
        data = ''
        exp_len = None
        header_len = 0
        has_rest = len(self.__rest_data) > 0
        while True:
            if self.__rest_data:
                data = self.__rest_data
                self.__rest_data = ''
            else:
                received = self.__sock.recv(BUF_SIZE)

                if not received:
                    break

                data += received

            if exp_len is None:
                if has_rest and len(data) < FRI_PACKET_INFO_LEN:
                    continue
                exp_len, header_len = FriBinaryProcessor.get_expected_len(data)
            if exp_len and len(data) >= exp_len:
                break

        if not data:
            raise FriException('empty data block')

        if len(data) > exp_len:
            self.__rest_data = data[exp_len:]
            data = data[:exp_len]

        packet, bin_data = FriBinaryProcessor.from_binary(data, exp_len, header_len)
        packet = FabnetPacket.create(packet)
        return packet, bin_data

    def __send_cert(self):
        req = FabnetPacketRequest(method='crtput', parameters={'certificate': self.__cert})
        self.__sock.sendall(req.dump())

    def recv_packet(self, allow_socket_close=True):
        packet, bin_data = self.read_next_packet()
        if packet.is_response and packet.ret_code == RC_REQ_CERTIFICATE:
            self.__send_cert()
            packet, bin_data = self.read_next_packet()

        cnt = packet.binary_chunk_cnt
        if cnt > 0 and bin_data:
            raise FriException('Binary data found in init chunk packet (%s chunks expected)'%cnt)

        if cnt > 0:
            packet.binary_data = SocketBasedChunks(self, cnt)
            return packet

        if bin_data:
            packet.binary_data = RamBasedBinaryData(bin_data)

        if allow_socket_close:
            self.__can_close_socket = True

        return packet

    def send_packet(self, packet):
        if packet.binary_data and packet.binary_data.chunks_count() > 1:
            packet.binary_chunk_cnt = packet.binary_data.chunks_count()

            self.__sock.sendall(packet.dump(with_bin=False))

            if packet.is_request:
                allow_packet, _ = self.read_next_packet()
                if allow_packet.is_response and allow_packet.ret_code == RC_REQ_CERTIFICATE:
                    self.__send_cert()

            for i in xrange(packet.binary_chunk_cnt):
                packet.binary_chunk_idx = i+1
                dumped_chunk = packet.dump_next_chunk()
                self.__sock.sendall(dumped_chunk)

            packet.binary_chunk_cnt = None
            packet.binary_chunk_idx = None
        else:
            self.__sock.sendall(packet.dump())


    def allow_close_socket(self):
        """This method trying close socket from SocketBasedChunks"""
        self.__can_close_socket = True
        if self.__need_sock_close and self.__sock:
            self.__close_sock()

    def close_socket(self, force=False):
        self.__need_sock_close = True
        if force:
            self.__can_close_socket = True
        if self.__can_close_socket and self.__sock:
            self.__close_sock()

    def is_closed(self):
        return self.__sock == None

    def __close_sock(self):
        try:
            self.__sock.shutdown(socket.SHUT_RDWR)
            self.__sock.close()
        except socket.error, err:
            print('[close socket error] %s'%err)
        finally:
            self.__sock = None


'''
proc = SocketProcessor(sock, cert)
pack = proc.get_packet()

chunks_count = pack.binary_data.chunks_count()
chunk = pack.binary_data.get_next_chunk()

proc.send_packet(pack)
'''
