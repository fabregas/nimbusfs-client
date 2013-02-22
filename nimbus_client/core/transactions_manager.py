#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.transactions_manager
@author Konstantin Andrusenko
@date February 17, 2013

This module contains the implementation of Transaction and TransactionsManager classes
"""
import os
import hashlib
from datetime import datetime
from Queue import Queue

from nimbus_client.core.data_block import DataBlock
from nimbus_client.core.metadata import FileMD, ChunkMD
from nimbus_client.core.base_safe_object import LockObject
from nimbus_client.core.exceptions import AlreadyExistsException, \
                                NotDirectoryException, PathException

GTLock = LockObject()
TLock = LockObject()

class Transaction:
    TS_INIT = 0
    TS_LOCAL_SAVED = 1
    TS_FINISHED = 2
    TS_FAILED = 3

    TT_WRITE = 1
    TT_READ = 2

    def __init__(self, transaction_type, file_path, replica_count):
        if transaction_type not in (self.TT_READ, self.TT_WRITE):
            raise RuntimeError('Unknown transaction type: %s'%transaction_type)

        self.__start_dt = datetime.now()
        self.__replica_count = replica_count
        self.__transaction_id = hashlib.sha1(str(self.__start_dt)).hexdigest()
        self.__transaction_type = transaction_type
        self.__status = Transaction.TS_INIT
        self.__file_path = file_path
        self.__data_blocks_info = {}

    def __repr__(self):
        return '<Transaction[%s] %s %s>'%(self.__transaction_id, \
                'UPLOAD' if self.__transaction_type==self.TT_WRITE else 'DOWNLOAD',\
                self.__file_path)

    def get_start_datetime(self):
        return self.__start_dt

    @TLock
    def get_replica_count(self):
        return self.__replica_count
    
    @TLock
    def get_id(self):
        return self.__transaction_id

    @TLock
    def get_file_path(self):
        return self.__file_path

    @TLock
    def is_uploading(self):
        return self.__transaction_type == self.TT_WRITE

    @TLock
    def is_downloading(self):
        return self.__transaction_type == self.TT_READ

    @TLock
    def get_status(self):
        return self.__status

    @TLock
    def total_size(self):
        t_size = 0
        for size,_,_,_ in self.__data_blocks_info.values():
            t_size += size
        return t_size

    @TLock
    def progress_perc(self):
        p_size = 0
        t_size = 0
        for _,data_block,_,_ in self.__data_blocks_info.values():
            seek, exp_s = data_block.get_progress()
            p_size += seek
            t_size += exp_s
        return (p_size * 100.) / t_size

    @TLock
    def append_data_block(self, seek, size, data_block, foreign_name=None):
        if size == 0:
            raise RuntimeError('Data block with size=0 is not supported!')
        self.__data_blocks_info[seek] = [size, data_block, foreign_name, False]

    @TLock
    def get_data_block(self, seek):
        if self.__data_blocks_info.has_key(seek):
            raise Exception('No data block with seek %s found in transaction %s'%(seek, self.__transaction_id))

        return self.__data_blocks_info[seek][:3]

    @TLock
    def finish_data_block_transfer(self, seek, foreign_name=None):
        if not self.__data_blocks_info.has_key(seek):
            raise Exception('No data block with seek %s found in transaction %s'%(seek, self.__transaction_id))

        if foreign_name:
            self.__data_blocks_info[seek][2] = foreign_name
        self.__data_blocks_info[seek][3] = True
            
    @TLock
    def change_status(self, new_status):
        self.__status = new_status

    @TLock
    def finished(self):
        if self.__status == Transaction.TS_INIT:
            return False
        if self.__status == self.TS_LOCAL_SAVED:
            for _,_,_, is_finished in self.__data_blocks_info.values():
                if not is_finished:
                    return False
        return True

    def iter_data_blocks(self):
        TLock.lock()
        try:
            sorted_seeks = sorted(self.__data_blocks_info.keys())
            for seek in sorted_seeks:
                dbi = self.__data_blocks_info[seek]
                yield seek, dbi[0], dbi[1], dbi[2]
        finally:
            TLock.unlock()

    @TLock
    def get_data_block(self, seek):
        sorted_seeks = sorted(self.__data_blocks_info.keys())
        if seek not in sorted_seeks:
            return None, None

        next_seek_idx = sorted_seeks.index(seek) + 1 
        if len(sorted_seeks) <= next_seek_idx:
            next_seek = None
        else:
            next_seek = sorted_seeks[next_seek_idx]
        return self.__data_blocks_info[seek][1], next_seek



class TransactionsManager:
    def __init__(self, metadata, db_cache):
        self.__metadata = metadata
        self.__db_cache = db_cache
        self.__put_queue = Queue()
        self.__get_queue = Queue()
        self.__trlog_path = db_cache.get_static_cache_path('transactions.log')
        self.__transactions = {}
        self.__tr_log = open(self.__trlog_path, 'a+')

    def get_upload_queue(self):
        return self.__put_queue

    def get_download_queue(self):
        return self.__get_queue

    def new_data_block(self, size=None, new_db_hash=None):
        if not new_db_hash:
            new_db_hash = hashlib.sha1(str(datetime.now())).hexdigest() 
        path = self.__db_cache.get_cache_path(new_db_hash)
        return DataBlock(path, size)

    def iterate_transactions(self):
        GTLock.lock()
        try:
            for transaction in self.__transactions.values():
                yield transaction.is_uploading(), transaction.get_file_path(), \
                        transaction.get_status(), transaction.total_size(), transaction.progress_perc()
        finally:
            GTLock.unlock()

    def __find_file(self, file_path):
        try:
            file_md = self.__metadata.find(file_path)
            return file_md
        except PathException:
            pass

        return self.__find_inprogress_file(file_path)

    def __find_inprogress_file(self, file_path):
        for transaction in self.__transactions.values():
            if (not transaction.is_uploading()) or (transaction.get_file_path() != file_path) \
                    or (transaction.get_status() != Transaction.TS_LOCAL_SAVED):
                continue
            file_md = FileMD(name=os.path.basename(file_path), \
                    replica_count=transaction.get_replica_count(), size=transaction.total_size())
            for seek, size, data_block, block_hash in transaction.iter_data_blocks():
                chunk = ChunkMD(size=size, seek=seek, key=data_block.get_name())
                file_md.append_chunk(chunk)

            return file_md

    @GTLock
    def find_inprogress_file(self, file_path):
        return self.__find_inprogress_file(file_path)

    @GTLock
    def start_transaction(self, transaction_type, file_path):
        if transaction_type == Transaction.TT_READ:
            file_md = self.__find_file(file_path)

            if (not file_md) or (not file_md.is_file()):
                raise PathException('No file found at %s'%file_path)

            transaction = Transaction(transaction_type, file_path, file_md.replica_count)
            transaction_id = transaction.get_id()
            self.__transactions[transaction_id] = transaction

            for chunk in file_md.chunks:
                db_path = self.__db_cache.get_cache_path(chunk.key)
                if os.path.exists(db_path):
                    transaction.append_data_block(chunk.seek, chunk.size, self.new_data_block(chunk.size, chunk.key), chunk.key)
                else:
                    self.transfer_data_block(transaction_id, chunk.seek, chunk.size, self.new_data_block(chunk.size, chunk.key), chunk.key)
        else:
            save_path, file_name = os.path.split(file_path)
            parent_dir = self.__metadata.find(save_path)
            if not parent_dir.is_dir():
                raise NotDirectoryException('Directory "%s" does not found!'%save_path)

            if self.__find_file(file_path):
                raise AlreadyExistsException('File %s already exists!'%file_path)

            replica_count = 2 #FIXME ... replica_count = parent_dir.replica_count
            transaction = Transaction(transaction_type, file_path, replica_count)
            transaction_id = transaction.get_id()
            self.__transactions[transaction_id] = transaction

        self.__tr_log_start_transaction(transaction.get_id(), transaction_type, file_path)
        return transaction_id


    @GTLock
    def get_data_block(self, transaction_id, seek):
        transaction = self.__get_transaction(transaction_id)
        db, next_seek = transaction.get_data_block(seek)
        return db, next_seek

    @GTLock
    def update_transaction_state(self, transaction_id, status):
        transaction = self.__get_transaction(transaction_id)
        if status == Transaction.TS_FINISHED:
            self.__mv_local_data_blocks(transaction)
            self.__save_metadata(transaction)

        transaction.change_status(status)

        self.__tr_log_update_state(transaction.get_id(), status)


    @GTLock
    def update_transaction(self, transaction_id, seek, is_failed=False, foreign_name=None):
        transaction = self.__get_transaction(transaction_id)
        if transaction.get_status() == Transaction.TS_FAILED:
            #should be removed data block from backend
            raise Exception('Transaction is failed!')

        if is_failed:
            self.update_transaction_state(transaction_id, Transaction.TS_FAILED)

        transaction.finish_data_block_transfer(seek, foreign_name)
        self.__tr_log_update(transaction_id, seek, None, foreign_name)

        if transaction.finished():
            self.update_transaction_state(transaction_id, Transaction.TS_FINISHED)

    @GTLock
    def transfer_data_block(self, transaction_id, seek, size, data_block, foreign_name=None):
        transaction = self.__get_transaction(transaction_id)
        transaction.append_data_block(seek, size, data_block, foreign_name)

        self.__tr_log_update(transaction_id, seek, data_block.get_name(), foreign_name)

        if transaction.is_uploading():
            self.__put_queue.put((transaction, seek))
        else:
            self.__get_queue.put((transaction, seek))

    def __get_transaction(self, transaction_id):
        tr = self.__transactions.get(transaction_id, None)
        if tr is None:
            raise Exception('No transaction found with ID=%s'%transaction_id)
        return tr

    def __mv_local_data_blocks(self, transaction):
        for seek, size, data_block, foreign_name in transaction.iter_data_blocks():
            self.__db_cache.mklink(data_block.get_name(), foreign_name)


    def __save_metadata(self, transaction):
        file_path = transaction.get_file_path()
        save_path, file_name = os.path.split(file_path)

        file_md = FileMD(name=file_name, size=transaction.total_size(), \
                    replica_count=transaction.get_replica_count())

        for seek, size, data_block, block_hash in transaction.iter_data_blocks():
            chunk = ChunkMD(checksum=data_block.checksum(), size=size, seek=seek, key=block_hash)
            file_md.append_chunk(chunk)

        self.__metadata.append(save_path, file_md)


    def __tr_log_start_transaction(self, transaction_id, transaction_type, file_path):
        self.__tr_log.write('%s ST %s %s\n'%(transaction_id, transaction_type, file_path))

    def __tr_log_update_state(self, transaction_id, status):
        self.__tr_log.write('%s US %s\n'%(transaction_id, status))

    def __tr_log_update(self, transaction_id, seek, local_name, foreign_name):
        self.__tr_log.write('%s UT %s %s %s\n'%(transaction_id, seek, local_name, foreign_name))
        

