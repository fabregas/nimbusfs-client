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
import base64
from datetime import datetime
from Queue import Queue

from nimbus_client.core.logger import logger
from nimbus_client.core.data_block import DataBlock
from nimbus_client.core.metadata import FileMD, ChunkMD
from nimbus_client.core.base_safe_object import LockObject
from nimbus_client.core.exceptions import AlreadyExistsException, \
                                NotDirectoryException, PathException

GTLock = LockObject()
TLock = LockObject()

MAX_TR_LOG_ITEMS = 100

class Transaction:
    TS_INIT = 0
    TS_LOCAL_SAVED = 1
    TS_FINISHED = 2
    TS_FAILED = 3

    TT_UPLOAD = 1
    TT_DOWNLOAD = 2

    TS_MAP = {0: 'INIT', 1: 'LOCAL_SAVED', 2: 'FINISHED', 3: 'FAILED'}

    def __init__(self, transaction_type, file_path, replica_count, transaction_id=None):
        if transaction_type not in (self.TT_UPLOAD, self.TT_DOWNLOAD):
            raise RuntimeError('Unknown transaction type: %s'%transaction_type)
        self.__start_dt = datetime.now()
        self.__replica_count = replica_count
        self.__transaction_type = transaction_type
        self.__status = Transaction.TS_INIT
        self.__file_path = file_path
        self.__data_blocks_info = {}
        if transaction_id:
            self.__transaction_id = transaction_id
        else:
            self.__transaction_id = hashlib.sha1(str(self.__start_dt)).hexdigest()

    def __repr__(self):
        return '<Transaction[%s][%s] %s %s>'%(self.__transaction_id, self.TS_MAP[self.__status],\
                'UPLOAD' if self.__transaction_type==self.TT_UPLOAD else 'DOWNLOAD',\
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
    def get_transaction_type(self):
        return self.__transaction_type

    @TLock
    def is_uploading(self):
        return self.__transaction_type == self.TT_UPLOAD

    @TLock
    def is_downloading(self):
        return self.__transaction_type == self.TT_DOWNLOAD

    @TLock
    def is_failed(self):
        return self.__status == self.TS_FAILED

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
        for _,data_block,_,finished in self.__data_blocks_info.values():
            if finished is None: #no data block transfer
                continue
            seek, exp_s = data_block.get_progress()
            p_size += seek
            t_size += exp_s
        if t_size == 0:
            return 0
        return (p_size * 100.) / t_size

    @TLock
    def append_data_block(self, seek, size, data_block, foreign_name=None, no_transfer=False):
        if size == 0:
            raise RuntimeError('Data block with size=0 is not supported!')

        if no_transfer:
            finished = None
        else:
            finished = False

        self.__data_blocks_info[seek] = [size, data_block, foreign_name, finished]

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
        if self.__status == Transaction.TS_FINISHED:
            True
        if self.__status == Transaction.TS_FAILED or \
                (self.__status == Transaction.TS_INIT and self.__transaction_type == self.TT_UPLOAD):
            return False

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
    def get_data_block(self, seek,  noclone=False):
        sorted_seeks = sorted(self.__data_blocks_info.keys())
        if seek not in sorted_seeks:
            return None, None

        next_seek_idx = sorted_seeks.index(seek) + 1 
        if len(sorted_seeks) <= next_seek_idx:
            next_seek = None
        else:
            next_seek = sorted_seeks[next_seek_idx]
        data_block = self.__data_blocks_info[seek][1]
        if noclone is False:
            data_block = data_block.clone()
        return data_block, next_seek



class TransactionsManager:
    def __init__(self, metadata, db_cache, transactions_window_len=10):
        self.__metadata = metadata
        self.__db_cache = db_cache
        self.__put_queue = Queue()
        self.__get_queue = Queue()
        self.__trlog_path = db_cache.get_static_cache_path('transactions.log')
        self.__transactions = {}
        self.__tr_log = open(self.__trlog_path, 'a+')
        self.__tr_log_items_count = 0
        self.__tr_window_len = transactions_window_len

        self.__restore_from_log()

    def close(self):
        if not self.__tr_log.closed:
            self.__tr_log.close()

    def get_upload_queue(self):
        return self.__put_queue

    def get_download_queue(self):
        return self.__get_queue

    def new_data_block(self, size=None, new_db_hash=None):
        if not new_db_hash:
            new_db_hash = hashlib.sha1(str(datetime.now())).hexdigest() 
        path = self.__db_cache.get_cache_path(new_db_hash)
        return DataBlock(path, size, create_if_none=True)

    def iterate_transactions(self):
        GTLock.lock()
        try:
            tr_list = sorted(self.__transactions.values(), \
                    cmp=lambda x,y: \
                    cmp(x.get_start_datetime(), y.get_start_datetime())) 

            for transaction in tr_list:
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
    def start_download_transaction(self, file_path):
        file_md = self.__find_file(file_path)

        if (not file_md) or (not file_md.is_file()):
            raise PathException('No file found at %s'%file_path)

        transaction = Transaction(Transaction.TT_DOWNLOAD, file_path, file_md.replica_count)
        transaction_id = transaction.get_id()
        stored_transaction = False

        try:
            for chunk in file_md.chunks:
                db_path = self.__db_cache.get_cache_path(chunk.key)
                if os.path.exists(db_path):
                    data_block = self.new_data_block(chunk.size, chunk.key)
                    if data_block.full():
                        transaction.append_data_block(chunk.seek, \
                                chunk.size, data_block, chunk.key, no_transfer=True)
                        continue
                    else:
                        data_block.remove()

                if not stored_transaction:
                    self.__transactions[transaction_id] = transaction
                    self.__tr_log_start_transaction(transaction)
                    stored_transaction = True
                
                data_block = self.new_data_block(chunk.size, chunk.key)
                self.transfer_data_block(transaction_id, chunk.seek, chunk.size, data_block, chunk.key)
        except Exception, err:
            if stored_transaction:
                self.update_transaction_state(transaction_id, Transaction.TS_FAILED)
            raise err

        return transaction

    @GTLock
    def start_upload_transaction(self, file_path):
        save_path, file_name = os.path.split(file_path)
        parent_dir = self.__metadata.find(save_path)
        if not parent_dir.is_dir():
            raise NotDirectoryException('Directory "%s" does not found!'%save_path)

        if self.__find_file(file_path):
            raise AlreadyExistsException('File %s already exists!'%file_path)

        replica_count = 2 #FIXME ... replica_count = parent_dir.replica_count
        transaction = Transaction(Transaction.TT_UPLOAD, file_path, replica_count)
        transaction_id = transaction.get_id()
        self.__transactions[transaction_id] = transaction
        self.__tr_log_start_transaction(transaction)

        return transaction_id


    @GTLock
    def update_transaction_state(self, transaction_id, status):
        transaction = self.__get_transaction(transaction_id)
        if transaction.get_transaction_type() == Transaction.TT_UPLOAD:
            if status == Transaction.TS_FINISHED:
                try:
                    self.__mv_local_data_blocks(transaction)
                    self.__save_metadata(transaction)
                except Exception, err:
                    #FIXME log message...
                    logger.error("Can't update metadata! Details: %s"%err)
                    return self.update_transaction_state(transaction_id, Transaction.TS_FAILED)
            elif status == Transaction.TS_FAILED:
                #should be removed data block from backend
                for _,_,data_block, foreign_name in transaction.iter_data_blocks():
                    self.__cancel_data_block_upload(foreign_name, data_block)

        transaction.change_status(status)

        self.__tr_log_update_state(transaction.get_id(), status)

    @GTLock
    def update_transaction(self, transaction_id, seek, is_failed=False, foreign_name=None):
        transaction = self.__get_transaction(transaction_id)

        transaction.finish_data_block_transfer(seek, foreign_name)
        self.__tr_log_update(transaction_id, seek, None, None, foreign_name)

        if is_failed:
            self.update_transaction_state(transaction_id, Transaction.TS_FAILED)

        if transaction.get_status() == Transaction.TS_FAILED:
            return

        if transaction.finished():
            self.update_transaction_state(transaction_id, Transaction.TS_FINISHED)

    @GTLock
    def transfer_data_block(self, transaction_id, seek, size, data_block, foreign_name=None):
        transaction = self.__get_transaction(transaction_id)
        transaction.append_data_block(seek, size, data_block, foreign_name)

        self.__tr_log_update(transaction_id, seek, size, data_block.get_name(), foreign_name)

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

    def __cancel_data_block_upload(self, foreign_name, data_block):
        self.__db_cache.remove_data_block(data_block.get_name())
        if foreign_name:
            #FIXME REMOVE_FROM_BACKEND(foreign_name)
            pass

    def __save_metadata(self, transaction):
        file_path = transaction.get_file_path()
        save_path, file_name = os.path.split(file_path)

        file_md = FileMD(name=file_name, size=transaction.total_size(), \
                    replica_count=transaction.get_replica_count())

        for seek, size, data_block, block_hash in transaction.iter_data_blocks():
            chunk = ChunkMD(checksum=data_block.checksum(), size=size, seek=seek, key=block_hash)
            file_md.append_chunk(chunk)

        self.__metadata.append(save_path, file_md)

    def __remove_oldest_stransaction(self):
        oldest_tr_list = sorted(self.__transactions.values(), \
                cmp=lambda x,y: \
                cmp(x.get_start_datetime(), y.get_start_datetime())) 

        tr_for_del = None
        for oldest_tr in oldest_tr_list:
            if oldest_tr.get_status() not in (Transaction.TS_FAILED, Transaction.TS_FINISHED):
                continue
            tr_for_del = oldest_tr.get_id()
            break

        if tr_for_del:
            del self.__transactions[tr_for_del]
            return True
        return False


    def __tr_log_start_transaction(self, transaction):
        while len(self.__transactions) > self.__tr_window_len:
            if not self.__remove_oldest_stransaction():
                break

        self.__tr_log.write('%s ST %s %s %s\n'%(transaction.get_id(), transaction.get_transaction_type(),\
                    base64.b64encode(transaction.get_file_path()), transaction.get_replica_count()))
        self.__tr_log.flush()
        self.__tr_log_items_count += 1
        if (self.__tr_log_items_count >= MAX_TR_LOG_ITEMS) \
                and (len(self.__transactions) <= self.__tr_window_len):
            self.__tr_log_items_count = 0
            self.__normalize_tr_log()

    def __tr_log_update_state(self, transaction_id, status):
        self.__tr_log.write('%s US %s\n'%(transaction_id, status))
        self.__tr_log.flush()

    def __tr_log_update(self, transaction_id, seek, size, local_name, foreign_name):
        self.__tr_log.write('%s UT %s %s %s %s\n'%(transaction_id, seek, size, local_name, foreign_name))
        self.__tr_log.flush()

    def __resume_transaction(self, transaction, progress_info):
        file_path = transaction.get_file_path()
        transaction_id = transaction.get_id()
        if transaction.is_downloading():
            file_md = self.__find_file(file_path)
            if (not file_md) or (not file_md.is_file()):
                logger.error('No file found at %s'%file_path)
            else:
                for chunk in file_md.chunks:
                    db_path = self.__db_cache.get_cache_path(chunk.key)
                    if chunk.seek in progress_info:
                        transaction.append_data_block(chunk.seek, chunk.size, self.new_data_block(chunk.size, chunk.key), chunk.key)
                    else:
                        self.__db_cache.remove_data_block(chunk.key)

            self.update_transaction_state(transaction.TS_FAILED)
        else:
            for seek, (size, local_name, foreign_name) in progress_info.items():
                if foreign_name and foreign_name != 'None':
                    db = self.new_data_block(None, foreign_name)
                    transaction.append_data_block(seek, size, db, foreign_name)
                else:
                    self.transfer_data_block(transaction_id, seek, size, self.new_data_block(size, local_name))


    def __parse_tr_log(self):
        def parse_int(val):
            if val in [None, 'None']:
                return None
            return int(val)

        def parse_str(val):
            if val in [None, 'None']:
                return None
            return val

        transactions = {}
        tr_log = open(self.__trlog_path, 'r')
        for line in tr_log.readlines():
            if not line:
                break

            parts = line.split()
            transaction_id = parts[0]
            r_type = parts[1]
            if r_type == 'ST':
                transaction = Transaction(int(parts[2]), base64.b64decode(parts[3]), int(parts[4]), transaction_id)
                transactions[transaction_id] = [transaction, {}] 
            elif r_type == 'US':
                transactions[transaction_id][0].change_status(int(parts[2]))
            elif r_type == 'UT':
                seek = int(parts[2])
                size = parse_int(parts[3])
                local_name = parse_str(parts[4])
                foreign_name = parse_str(parts[5])
                cur_vals = transactions[transaction_id][1].get(seek, [None, None, None])
                if size:
                    cur_vals[0] = size
                if local_name:
                    cur_vals[1] = local_name
                if foreign_name:
                    cur_vals[2] = foreign_name
                transactions[transaction_id][1][seek] = cur_vals

        tr_log.close()
        return sorted(transactions.values(), cmp=lambda x,y: cmp(x[0].get_start_datetime(), y[0].get_start_datetime())) 

    def __normalize_tr_log(self):
        transactions = self.__parse_tr_log() 
        rest = len(transactions) - self.__tr_window_len
        self.close()
        self.__tr_log = open(self.__trlog_path, 'w')

        for transaction, progress_info in transactions:
            status = transaction.get_status()
            if status in (transaction.TS_FINISHED, transaction.TS_FAILED):
                if rest > 0:
                    rest -= 1
                    continue  

            self.__tr_log_start_transaction(transaction)

            for seek, (size, local_name, foreign_name) in progress_info.items():
                self.__tr_log_update(transaction.get_id(), seek, size, local_name, foreign_name)

            self.__tr_log_update_state(transaction.get_id(), transaction.get_status())

    
    def __restore_from_log(self):
        transactions = self.__parse_tr_log() 
        rest = len(transactions) - self.__tr_window_len
        self.close()
        self.__tr_log = open(self.__trlog_path, 'w')

        for transaction, progress_info in transactions:
            status = transaction.get_status()
            if status != transaction.TS_LOCAL_SAVED:
                if status == transaction.TS_INIT:
                    transaction.change_status(transaction.TS_FAILED)
                    for seek, (size, local_name, foreign_name) in progress_info.items():
                        self.__db_cache.remove_data_block(local_name)

                if rest > 0:
                    rest -= 1
                    continue  

            self.__transactions[transaction.get_id()] = transaction
            self.__tr_log_start_transaction(transaction)

            self.__tr_log_update_state(transaction.get_id(), transaction.get_status())

            if status == transaction.TS_LOCAL_SAVED:
                self.__resume_transaction(transaction, progress_info)

