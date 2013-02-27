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

from nimbus_client.core.data_block import DataBlock
from nimbus_client.core.encdec_provider import BLOCK_SIZE, PAD 
from nimbus_client.core.metadata import AbstractMetadataObject, DirectoryMD

class Journal:
    OT_APPEND = 1
    OT_UPDATE = 2
    OT_REMOVE = 3

    RECORD_STRUCT = '<IBQ'
    RECORD_STRUCT_SIZE = struct.calcsize(RECORD_STRUCT)

    def __init__(self, journal_key, journal_path, fabnet_gateway):
        self.__journal_key = journal_key
        self.__journal_path = journal_path
        if os.path.exists(self.__journal_path):
            os.remove(self.__journal_path)
        self.__journal = DataBlock(self.__journal_path, create_if_none=True)
        self.__fabnet_gateway = fabnet_gateway
        self.__last_record_id = 0
        self.__no_foreign = True

    def close(self):
        self.__journal.close()

    def __recv_journal(self):
        is_recv = self.__fabnet_gateway.get(self.__journal_key, 2, self.__journal)
        if is_recv:
            self.__no_foreign = False
        else:
            self.__no_foreign = True

    def __send_journal(self):
        self.__journal.finalize()
        j_data = DataBlock(self.__journal_path, actsize=True)
        return self.__fabnet_gateway.put(j_data, key=self.__journal_key)

    def foreign_exists(self):
        if self.__no_foreign:
            self.__recv_journal()
        return not self.__no_foreign

    def init(self):
        if self.__journal.get_actual_size() > 0:
            raise RuntimeError('Journal is already initialized')

        #append root directory
        self.__int_append(self.OT_APPEND, DirectoryMD(item_id=0, parent_dir_id=0, name='/'))
        saved = self.__send_journal() #full initialized journal should be send
        if saved:
            self.__no_foreign = False


    def append(self, operation_type, item_md):
        self.__int_append(operation_type, item_md)
        self.__send_journal() #TODO incremental journal changes should be send

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

    def iter(self, start_record_id=None):
        j_data = DataBlock(self.__journal_path, actsize=True)
        buf = ''
        while True:
            if len(buf) < self.RECORD_STRUCT_SIZE:
                buf += j_data.read(1024)
                if not buf:
                    break

            item_dump_len, operation_type, record_id = struct.unpack(self.RECORD_STRUCT, buf[:self.RECORD_STRUCT_SIZE])

            if len(buf) < (self.RECORD_STRUCT_SIZE + item_dump_len):
                buf += j_data.read(1024)

            item_dump = buf[self.RECORD_STRUCT_SIZE:self.RECORD_STRUCT_SIZE+item_dump_len]

            remaining_len = BLOCK_SIZE - self.RECORD_STRUCT_SIZE - item_dump_len
            to_pad_len = remaining_len % BLOCK_SIZE
            buf = buf[self.RECORD_STRUCT_SIZE+item_dump_len+to_pad_len:]

            if (start_record_id is None) or (record_id >= start_record_id):
                if operation_type == self.OT_REMOVE:
                    item_md = struct.unpack('<I', item_dump)
                else:
                    item_md = AbstractMetadataObject.load_md(item_dump)
                yield record_id, operation_type, item_md

