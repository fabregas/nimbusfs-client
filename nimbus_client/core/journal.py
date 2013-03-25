#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.journal
@author Konstantin Andrusenko
@date February 20, 2013

This module contains the implementation of Journal class
"""
import os
import struct
import threading
import time

from nimbus_client.core.data_block import DataBlock
from nimbus_client.core.pycrypto_enc_engine import BLOCK_SIZE
from nimbus_client.core.metadata import AbstractMetadataObject, DirectoryMD
from nimbus_client.core.base_safe_object import LockObject
from nimbus_client.core.logger import logger
from nimbus_client.core.constants import JOURNAL_SYNC_CHECK_TIME

JLock = LockObject()

PAD = '\x44'

class Journal:
    #journal statuses
    JS_SYNC = 0
    JS_NOT_SYNC = 1
    JS_NOT_INIT = 2
    JS_SYNC_FAILED = 3

    #types of operations for journaling
    OT_APPEND = 1
    OT_UPDATE = 2
    OT_REMOVE = 3

    RECORD_STRUCT = '<IBQ'
    RECORD_STRUCT_SIZE = struct.calcsize(RECORD_STRUCT)

    def __init__(self, journal_key, journal_path, fabnet_gateway):
        self.__journal_key = journal_key
        self.__journal_path = journal_path
        self.__journal = DataBlock(self.__journal_path, create_if_none=True)
        self.__fabnet_gateway = fabnet_gateway
        self.__last_record_id = 0

        self.__no_foreign = True
        self.__is_sync = False
        self.__sync_failed = False

        self.__j_sync_thrd = JournalSyncThread(self)
        self.__j_sync_thrd.start()

    def __recv_journal(self):
        self.__journal.remove()
        self.__journal = DataBlock(self.__journal_path, create_if_none=True)

        is_recv = self.__fabnet_gateway.get(self.__journal_key, 2, self.__journal)
        if is_recv:
            self.__no_foreign = False
            self.__is_sync = True
            self.__journal.close() #next __journal.write reopen data block
            logger.info("Journal is received from NimbusFS backend")
        else:
            logger.warning("Can't receive journal from NimbusFS backend")
            self.__no_foreign = True

    def close(self):
        self.__journal.close()
        self.__j_sync_thrd.stop()

    @JLock
    def synchronized(self):
        return self.__is_sync

    @JLock
    def status(self):
        if self.__sync_failed:
            return self.JS_SYNC_FAILED
        if self.__no_foreign:
            return self.JS_NOT_INIT
        if  not self.__is_sync:
            return self.JS_NOT_SYNC
        return self.JS_SYNC

    @JLock
    def _synchronize(self):
        try:
            logger.debug('synchronizing journal...')
            self.__journal.flush()
            j_data = DataBlock(self.__journal_path, actsize=True)
            is_send = self.__fabnet_gateway.put(j_data, key=self.__journal_key)
            if is_send:
                self.__is_sync = True
            self.__sync_failed = False
        except Exception, err:
            self.__sync_failed = True
            raise err

    @JLock
    def foreign_exists(self):
        if self.__no_foreign:
            self.__recv_journal()
        return not self.__no_foreign

    @JLock
    def init(self):
        if self.__journal.get_actual_size() > 0:
            raise RuntimeError('Journal is already initialized')

        #append root directory
        self.__int_append(self.OT_APPEND, DirectoryMD(item_id=0, parent_dir_id=0, name='/'))
        self._synchronize() #full initialized journal should be send
        self.__no_foreign = False

    @JLock
    def append(self, operation_type, item_md):
        j_id = self.__int_append(operation_type, item_md)
        self.__is_sync = False
        return j_id

    @JLock
    def get_last_id(self):
        return self.__last_record_id

    def __int_append(self, operation_type, item_md):
        if operation_type not in (self.OT_APPEND, self.OT_UPDATE, self.OT_REMOVE):
            raise RuntimeError('Unsupported journal operation type: %s'%operation_type)

        self.__last_record_id += 1
        if operation_type == self.OT_REMOVE:
            item_dump = struct.pack('<I', item_md.item_id)
        else:
            item_dump = item_md.dump()
        item_dump_len = len(item_dump)
        record_h = struct.pack(self.RECORD_STRUCT, item_dump_len, operation_type, self.__last_record_id)

        remaining_len = BLOCK_SIZE - self.RECORD_STRUCT_SIZE - item_dump_len
        to_pad_len = remaining_len % BLOCK_SIZE
        pad_string = PAD * to_pad_len

        unsync_j_data = self.__journal.write(''.join([record_h, item_dump, pad_string]))
        return self.__last_record_id

    def iter(self, start_record_id=None):
        JLock.lock()
        try:
            j_data = DataBlock(self.__journal_path, actsize=True)
            buf = ''
            while True:
                if len(buf) < self.RECORD_STRUCT_SIZE:
                    buf += j_data.read(1024)
                    #logger.debug('J_ITER: buf=%s'%buf.encode('hex').upper())
                    if not buf:
                        break

                #logger.debug('J_ITER: header=%s'%buf[:self.RECORD_STRUCT_SIZE].encode('hex').upper())
                item_dump_len, operation_type, record_id = struct.unpack(self.RECORD_STRUCT, buf[:self.RECORD_STRUCT_SIZE])
                #logger.debug('J_ITER: buf_len=%s, item_dump_len=%s, operation_type=%s, record_id=%s'%(len(buf), item_dump_len, operation_type, record_id))
                if operation_type not in (self.OT_APPEND, self.OT_UPDATE, self.OT_REMOVE):
                    #logger.debug('J_ITER: buf=%s'%buf.encode('hex').upper())
                    raise RuntimeError('Invalid journal!!! Unknown operation type: %s'%operation_type)

                if len(buf) < (self.RECORD_STRUCT_SIZE + item_dump_len):
                    buf += j_data.read(1024)

                item_dump = buf[self.RECORD_STRUCT_SIZE:self.RECORD_STRUCT_SIZE+item_dump_len]

                remaining_len = BLOCK_SIZE - self.RECORD_STRUCT_SIZE - item_dump_len
                to_pad_len = remaining_len % BLOCK_SIZE
                #logger.debug('J_ITER: record=%s'%buf[:self.RECORD_STRUCT_SIZE+item_dump_len+to_pad_len].encode('hex').upper())
                buf = buf[self.RECORD_STRUCT_SIZE+item_dump_len+to_pad_len:]

                self.__last_record_id = record_id
                if (start_record_id is None) or (record_id > start_record_id):
                    if operation_type == self.OT_REMOVE:
                        item_md = struct.unpack('<I', item_dump)[0]
                    else:
                        item_md = AbstractMetadataObject.load_md(item_dump)
                    logger.debug('J_ITER: record_id=%s, operation_type=%s, item_md=%s'%(record_id, operation_type, item_md))
                    yield record_id, operation_type, item_md
        finally:
            JLock.unlock()


class JournalSyncThread(threading.Thread):
    def __init__(self, journal):
        threading.Thread.__init__(self)
        self.__journal = journal
        self.__stop_flag = threading.Event()
        self.setName('JournalSyncThread')

    def stop(self):
        self.__stop_flag.set()
        self.join()

    def run(self):
        logger.info('thread is started')
        while not self.__stop_flag.is_set():
            if self.__journal.status() in (Journal.JS_NOT_SYNC, Journal.JS_SYNC_FAILED):
                try:
                    self.__journal._synchronize()
                except Exception, err:
                    logger.error('journal synchronization is failed with message: %s'%err)

            for i in xrange(JOURNAL_SYNC_CHECK_TIME):
                if self.__stop_flag.is_set():
                    break
                time.sleep(1)
        logger.info('thread is stopped')


    
