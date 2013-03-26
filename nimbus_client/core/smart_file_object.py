#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.smart_file_object
@author Konstantin Andrusenko
@date February 17, 2013

This module contains the implementation of SmartFileObject class
"""
from nimbus_client.core.transactions_manager import TransactionsManager, Transaction
from nimbus_client.core.constants import MAX_DATA_BLOCK_SIZE
from nimbus_client.core.exceptions import ClosedFileException, PermissionsException
from nimbus_client.core.logger import logger

class SmartFileObject:
    TRANSACTIONS_MANAGER = None
    @classmethod
    def setup_transaction_manager(cls, transactions_manager):
        if not isinstance(transactions_manager, TransactionsManager):
            raise RuntimeError('Unknown type of transactions manager: %s'%type(transaction_manager))
        cls.TRANSACTIONS_MANAGER = transactions_manager

    def __init__(self, file_path, for_write=False):
        self.__file_path = file_path
        self.__seek = 0
        self.__cur_data_block = None
        self.__cur_db_seek = 0
        self.__transaction_id = None #used for write()
        self.__transaction = None #used for read()
        self.__unsync = False
        self.__closed = False
        self.__for_write = for_write

    def write(self, data):
        if not self.__for_write:
            raise PermissionsException('File %s is openned for read!'%self.__file_path)

        if not data:
            return

        try:
            if self.__closed:
                raise ClosedFileException('closed file!')
            if self.__cur_data_block is None:
                self.__cur_data_block = self.TRANSACTIONS_MANAGER.new_data_block()

            data_len = len(data)
            rest = self.__cur_db_seek + data_len - MAX_DATA_BLOCK_SIZE
            if rest > 0:
                rest_data = data[data_len-rest:]
                data = data[:data_len-rest]
            else:
                rest_data = ''

            self.__cur_data_block.write(data)
            self.__cur_db_seek += len(data)
            self.__unsync = True

            if rest_data:
                self.__send_data_block()
                self.write(rest_data)
        except Exception, err:
            self.__failed_transaction(err)
            raise err

    def get_seek(self):
        return self.__seek

    def seek(self, seek_v):
        if not self.__transaction:
            self.__transaction = self.TRANSACTIONS_MANAGER.start_download_transaction(self.__file_path)

        if not seek_v:
            return

        while True:
            cur_seek = self.__seek
            self.__cur_data_block, self.__seek = self.__transaction.get_data_block(self.__seek)
            if self.__cur_data_block is None:
                return

            if (not self.__seek) or (seek_v <= self.__seek and seek_v >= cur_seek):
                self.read(seek_v - cur_seek)
                return
            


    def read(self, read_len=None):
        if self.__for_write:
            raise PermissionsException('File %s is openned for write!'%self.__file_path)
        if self.__closed:
            raise ClosedFileException('closed file!')

        self.seek(0)

        try:
            ret_data = ''
            while True:
                if not self.__cur_data_block:
                    if self.__seek is None:
                        break
                    self.__cur_data_block, self.__seek = self.__transaction.get_data_block(self.__seek)
                    if not self.__cur_data_block:
                        break

                data = self.__cur_data_block.read(read_len)
                if data:
                    ret_data += data

                if read_len and len(ret_data) >= read_len:
                    break
                self.__cur_data_block.close()
                self.__cur_data_block = None
        except Exception, err:
            self.__failed_transaction(err)
            raise err

        return ret_data


    def close(self):
        if self.__closed:
            return
        try:
            if self.__for_write:
                try:
                    if self.__unsync and self.__cur_data_block:
                        self.__send_data_block()
                    else:
                        if not self.__transaction_id:
                            self.TRANSACTIONS_MANAGER.save_empty_file(self.__file_path)

                    if self.__transaction_id:
                        self.TRANSACTIONS_MANAGER.update_transaction_state(self.__transaction_id, Transaction.TS_LOCAL_SAVED)
                except Exception, err: 
                    self.__failed_transaction(err)
                    raise err
            else:
                if self.__cur_data_block:
                    self.__cur_data_block.close()
        finally:
            self.__closed = True
            
    def __send_data_block(self):
        self.__cur_data_block.finalize()
        if self.__cur_data_block.get_actual_size():
            if not self.__transaction_id:
                self.__transaction_id = self.TRANSACTIONS_MANAGER.start_upload_transaction(self.__file_path)

            self.TRANSACTIONS_MANAGER.transfer_data_block(self.__transaction_id, self.__seek, self.__cur_db_seek, self.__cur_data_block)

        self.__seek += self.__cur_db_seek
        self.__cur_db_seek = 0
        self.__cur_data_block = None
        self.__unsync = False

    def __failed_transaction(self, err):
        #TODO: implement error writing to events log
        if self.__cur_data_block:
            self.__cur_data_block.remove()

        if self.__transaction_id:
            self.TRANSACTIONS_MANAGER.update_transaction_state(self.__transaction_id, Transaction.TS_FAILED)



