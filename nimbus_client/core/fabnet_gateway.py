#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.nibbler
@author Konstantin Andrusenko
@date October 12, 2012

This module contains the implementation of gateway API for talking with fabnet
"""
import hashlib
from nimbus_client.core.fri.fri_base import FabnetPacketRequest, RamBasedBinaryData, FriBinaryData
from nimbus_client.core.fri.fri_client import FriClient
from nimbus_client.core.fri.socket_processor import SocketProcessor
from nimbus_client.core.fri.constants import FRI_CLIENT_TIMEOUT

from nimbus_client.core.data_block import DataBlock
from nimbus_client.core.constants import RC_NO_DATA, DEFAULT_REPLICA_COUNT, FRI_PORT, FILE_ITER_BLOCK_SIZE
from nimbus_client.core.logger import logger

class ChunkedBinaryData(FriBinaryData):
    @classmethod
    def prepare(cls, data_block, chunk_size):
        if isinstance(data_block, DataBlock):
            return cls(data_block, chunk_size)
        else:
            return RamBasedBinaryData(data_block)

    def __init__(self, data_block, chunk_size):
        self.__chunk_size = chunk_size
        self.__data_block = data_block

    def chunks_count(self):
        f_size = self.__data_block.get_actual_size()
        cnt = f_size / self.__chunk_size
        if f_size % self.__chunk_size != 0:
            cnt += 1
        return cnt

    def get_next_chunk(self):
        return self.__data_block.read_raw(self.__chunk_size)

    def data(self):
        return self.__data_block.read_raw()



class FabnetGateway:
    @classmethod
    def force_close_all_connections(cls):
        SocketProcessor.force_close_flag.set()

    @classmethod
    def init_socket_processor(cls):
        SocketProcessor.force_close_flag.clear()

    def __init__(self, fabnet_hostname, security_manager):
        if ':' not in fabnet_hostname:
            fabnet_hostname += ':%s'%FRI_PORT
        self.fabnet_hostname = fabnet_hostname
        self.security_manager = security_manager

        cert = self.security_manager.get_client_cert()
        ckey = self.security_manager.get_client_cert_key()
        self.fri_client = FriClient(bool(ckey), cert, ckey)

    def put(self, data_block, key=None, replica_count=DEFAULT_REPLICA_COUNT, wait_writes_count=2, allow_rewrite=True):
        packet = FabnetPacketRequest(method='PutKeysInfo', parameters={'key': key}, sync=True)
        resp = self.fri_client.call_sync(self.fabnet_hostname, packet, FRI_CLIENT_TIMEOUT)
        if resp.ret_code != 0:
            raise Exception('Key info error: %s'%resp.ret_message)

        if not resp.ret_parameters.has_key('key_info'):
            raise Exception('Invalid PutKeysInfo response! key_info is expected')

        key_info = resp.ret_parameters['key_info']
        key, node_addr = key_info

        params = {'key':key, 'replica_count':replica_count, \
                    'wait_writes_count': wait_writes_count}
        packet = FabnetPacketRequest(method='ClientPutData', parameters=params, \
                        binary_data=ChunkedBinaryData.prepare(data_block, FILE_ITER_BLOCK_SIZE), sync=True)

        resp = self.fri_client.call_sync(node_addr, packet, FRI_CLIENT_TIMEOUT)
        try:
            if resp.ret_code != 0:
                raise Exception('ClientPutData error: %s'%resp.ret_message)

            if not resp.ret_parameters.has_key('key'):
                raise Exception('put data block error: no data key found in response message "%s"'%resp)

            primary_key = resp.ret_parameters['key']
            checksum = resp.ret_parameters['checksum']
            if isinstance(data_block, DataBlock):
                db_checksum = data_block.checksum()
            else:
                db_checksum = hashlib.sha1(data_block).hexdigest()

            if checksum != db_checksum:
                raise Exception('Invalid data block checksum!')
        except Exception, err:
            logger.error('[put] %s'%err)
            logger.traceback_debug()            
            if not allow_rewrite:
                self.remove(key, replica_count)
            raise err

        return primary_key

    def remove(self, key, replica_count=DEFAULT_REPLICA_COUNT):
        params = {'key':key, 'replica_count':replica_count}
        packet = FabnetPacketRequest(method='ClientDeleteData', parameters=params, sync=True)
        resp = self.fri_client.call_sync(self.fabnet_hostname, packet, FRI_CLIENT_TIMEOUT)
        if resp.ret_code != 0:
            logger.error('ClientDeleteData error: %s'%resp.ret_message)
            return False
        return True

    def get(self, primary_key, replica_count, data_block):
        packet = FabnetPacketRequest(method='GetKeysInfo', parameters={'key': primary_key, 'replica_count': replica_count}, sync=True)
        resp = self.fri_client.call_sync(self.fabnet_hostname, packet, FRI_CLIENT_TIMEOUT)
        if resp.ret_code != 0:
            raise Exception('Get keys info error: %s'%resp.ret_message)

        keys_info = resp.ret_parameters['keys_info']
        for key, is_replica, node_addr in keys_info:
            params = {'key': key, 'is_replica': is_replica}
            packet = FabnetPacketRequest(method='GetDataBlock', parameters=params, sync=True)
            resp = self.fri_client.call_sync(node_addr, packet, FRI_CLIENT_TIMEOUT)

            if resp.ret_code == RC_NO_DATA:
                logger.error('No data found for key %s on node %s'%(key, node_addr))
            elif resp.ret_code != 0:
                logger.error('Get data block error for key %s from node %s: %s'%(key, node_addr, resp.ret_message))
            elif resp.ret_code == 0:
                exp_checksum = resp.ret_parameters['checksum']
                while True:
                    chunk = resp.binary_data.get_next_chunk()
                    if not chunk:
                        break
                    data_block.write(chunk, encrypt=False)

                if exp_checksum != data_block.checksum():
                    logger.error('Currupted data block for key %s from node %s'%(primary_key, node_addr))
                    continue
                return data_block

        return None


