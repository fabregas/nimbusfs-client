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

try:
    from fri_base import FriClient, FabnetPacketRequest
except ImportError:
    from fabnet.core.fri_base import FriClient, FabnetPacketRequest

from constants import DEFAULT_REPLICA_COUNT, FRI_PORT, FRI_CLIENT_TIMEOUT, \
                            RC_NO_DATA
from logger import logger

class FabnetGateway:
    def __init__(self, fabnet_hostname, security_manager):
        if ':' not in fabnet_hostname:
            fabnet_hostname += ':%s'%FRI_PORT
        self.fabnet_hostname = fabnet_hostname
        self.security_manager = security_manager

        cert = self.security_manager.get_client_cert()
        ckey = self.security_manager.get_client_cert_key()
        self.fri_client = FriClient(bool(ckey), cert, ckey)

    def put(self, data, key=None, replica_count=DEFAULT_REPLICA_COUNT, wait_writes_count=2):
        source_checksum =  hashlib.sha1(data).hexdigest()
        data = self.security_manager.encrypt(data)
        checksum =  hashlib.sha1(data).hexdigest()

        params = {'key':key, 'checksum': checksum, 'wait_writes_count': wait_writes_count}
        packet = FabnetPacketRequest(method='ClientPutData', parameters=params, binary_data=data, sync=True)

        resp = self.fri_client.call_sync(self.fabnet_hostname, packet, FRI_CLIENT_TIMEOUT)
        if resp.ret_code != 0:
            logger.error('ClientPutData error: %s'%resp.ret_message)
            raise Exception('ClientPutData error: %s'%resp.ret_message)

        primary_key = resp.ret_parameters['key']

        return primary_key, source_checksum

    def get(self, primary_key, replica_count=DEFAULT_REPLICA_COUNT):
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
                data = resp.binary_data
                checksum =  hashlib.sha1(data).hexdigest()
                if exp_checksum != checksum:
                    logger.error('Currupted data block for key %s from node %s'%(primary_key, node_addr))
                    continue
                data = self.security_manager.decrypt(data)
                return data

        return None


