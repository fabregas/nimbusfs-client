#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.nibbler
@author Konstantin Andrusenko
@date October 12, 2012

This module contains the implementation of user API to idepositbox service.
"""
import os
import hashlib
import time
import threading
from datetime import datetime, timedelta

from nimbus_client.core.exceptions import *
from nimbus_client.core.logger import logger
from nimbus_client.core.fabnet_gateway import FabnetGateway
from nimbus_client.core.data_block_cache import DataBlockCache
from nimbus_client.core.journal import Journal 
from nimbus_client.core.metadata import DirectoryMD, FileMD
from nimbus_client.core.metadata_file import MetadataFile 
from nimbus_client.core.transactions_manager import TransactionsManager, Transaction
from nimbus_client.core.workers_manager import WorkersManager, PutWorker, GetWorker 
from nimbus_client.core.smart_file_object import SmartFileObject
from nimbus_client.core.data_block import DataBlock, DBLocksManager
from nimbus_client.core.utils import to_nimbus_path
from nimbus_client.core.security_manager import AbstractSecurityManager


class InprogressOperation:
    def __init__(self, is_upload, file_path, status, size, progress_perc):
        self.is_upload = is_upload
        self.file_path = file_path
        self.status = status
        self.size = size
        self.progress_perc = progress_perc

    def __repr__(self):
        return '[%s][%s][%s perc] %s'%('UPLOAD' if self.is_upload else 'DOWNLOAD', \
                Transaction.TS_MAP.get(self.status, 'unknown'), self.progress_perc, self.file_path)

class FSItem:
    def __init__(self, item_name, is_dir, create_dt=None, modify_dt=None, size=0):
        if type(item_name) == str:
            item_name = item_name.decode('utf8')
        self.name = item_name
        self.is_dir = is_dir
        self.is_file = not is_dir
        if size is None:
            size = 0
        self.size = size

        if create_dt is None:
            self.create_dt = datetime.now()#.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            self.create_dt = datetime.fromtimestamp(create_dt)

        if modify_dt is None:
            self.modify_dt = self.create_dt
        else:
            self.modify_dt = datetime.fromtimestamp(create_dt)

    def __repr__(self):
        if self.is_dir:
            return '[dir][%s][%s] %s'%(self.create_dt, self.modify_dt, self.name)
        return '[file][%s][%s] %s'%(self.create_dt, self.size, self.name)


class Nibbler:
    def __init__(self, fabnet_host, security_provider, parallel_put_count=3, \
            parallel_get_count=3, cache_dir='/tmp', cache_size=None):
        if not isinstance(security_provider, AbstractSecurityManager):
            raise Exception('Invalid security provider type!')
        self.__parallel_put_count = parallel_put_count
        self.__parallel_get_count = parallel_get_count
        self.security_provider = security_provider
        self.fabnet_gateway = FabnetGateway(fabnet_host, security_provider)
        self.db_cache = DataBlockCache(cache_dir, cache_size)

        prikey = self.security_provider.get_prikey()
        self.metadata_key = hashlib.sha1(str(prikey)).hexdigest()
        self.metadata_f_name = 'md-%s.bin'%self.metadata_key

        self.journal = None
        self.metadata = None
        self.transactions_manager = None
        self.put_manager = None
        self.get_manager = None

        DataBlock.SECURITY_MANAGER = self.security_provider
        DataBlock.LOCK_MANAGER = DBLocksManager()

        self.journal = Journal(self.metadata_key, \
                self.db_cache.get_static_cache_path('journal.bin'), self.fabnet_gateway)

    def get_security_provider(self):
        return self.security_provider
        
    def start(self):
        if not self.journal.foreign_exists():
            raise NoJournalFoundException('No journal for key = %s'%self.metadata_key)

        self.metadata = MetadataFile(self.db_cache.get_static_cache_path(self.metadata_f_name), self.journal)
        self.transactions_manager = TransactionsManager(self.metadata, self.db_cache)

        SmartFileObject.setup_transaction_manager(self.transactions_manager)

        self.put_manager = WorkersManager(PutWorker, self.fabnet_gateway, \
                self.transactions_manager, self.__parallel_put_count)  
        self.get_manager = WorkersManager(GetWorker, self.fabnet_gateway, \
                self.transactions_manager, self.__parallel_get_count)  

        self.put_manager.start()
        self.get_manager.start()

    def is_registered(self):
        return self.journal.foreign_exists()

    def register_user(self):
        self.journal.init()
        if self.metadata:
            self.metadata.close()
            self.metadata = MetadataFile(self.db_cache.get_static_cache_path(self.metadata_f_name), self.journal)

    def on_error(self, error_msg):
        pass

    def stop(self):
        if self.put_manager:
            self.put_manager.stop()
        if self.get_manager:
            self.get_manager.stop()
        if self.metadata:
            self.metadata.close()
        if self.journal:
            self.journal.close()
        if self.transactions_manager:
            self.transactions_manager.close()
        self.db_cache.stop()

    def __make_item_fs(self, item_md):
        return FSItem(item_md.name, item_md.is_dir(), item_md.create_date, item_md.last_modify_date, item_md.size)

    def find(self, path):
        path = to_nimbus_path(path)
        path_obj = self.transactions_manager.find_inprogress_file(path)
        if not path_obj:
            try:
                path_obj = self.metadata.find(path)
            except PathException, err:
                #logger.debug('[get_resource] %s'%str(err))
                return

        if path_obj:
            return self.__make_item_fs(path_obj)

    def listdir(self, path='/'):
        path = to_nimbus_path(path)
        ret_lst = []
        inc_tr_l = []

        #try to find uploading files in @path (fully saved into data blocks cache)
        for is_upload, file_path, status, size, _ in self.transactions_manager.iterate_transactions():
            if not is_upload:
                continue
            if status != Transaction.TS_LOCAL_SAVED:
                continue
            base_path, file_name = os.path.split(file_path)
            if base_path == path:
                ret_lst.append(self.__make_item_fs(FileMD(name=file_name, size=size)))
                inc_tr_l.append(file_name)

        items = self.metadata.listdir(path)
        for item in items:
            if item.name not in inc_tr_l:
                ret_lst.append(self.__make_item_fs(item))

        return ret_lst


    def mkdir(self, path, recursive=False):
        path = to_nimbus_path(path)
        logger.debug('mkdir %s ...'%path)
        mdf = self.metadata
        if mdf.exists(path):
            raise AlreadyExistsException('Directory "%s" is already exists!'%path)

        base_path, new_dir = os.path.split(path)

        if not mdf.exists(base_path):
            if recursive:
                self.mkdir(base_path, recursive)
            else:
                raise PathException('Directory "%s" does not exists!'%base_path)

        new_dir_obj = DirectoryMD(name=new_dir)
        mdf.append(base_path, new_dir_obj)


    def rmdir(self, path, recursive=False):
        path = to_nimbus_path(path)
        logger.debug('rmdir %s ...'%path)
        mdf = self.metadata

        dir_obj = mdf.find(path)
        if not dir_obj.is_dir():
            raise NotDirectoryException('%s is a file!'%path)

        items = mdf.listdir(path)
        if items and not recursive:
            raise NotEmptyException('Directory "%s" is not empty!'%path)

        for item in items:
            full_path = '%s/%s'%(path, item.name)
            if item.is_file():
                self.remove_file(full_path)
            else:
                self.rmdir(full_path, recursive)

        mdf.remove(dir_obj)

    def move(self, s_path, d_path):
        s_path = to_nimbus_path(s_path)
        d_path = to_nimbus_path(d_path)
        logger.debug('moving %s to %s ...'%(s_path, d_path))

        mdf = self.metadata
        source = mdf.find(s_path)
        if mdf.exists(d_path):
            d_obj = mdf.find(d_path)
            if d_obj.is_file():
                raise AlreadyExistsException('File %s is already exists!'%d_path)
            source.parent_dir_id = d_obj.item_id
        else:
            dst_path, new_name = os.path.split(d_path)
            source.name = new_name
            mdf.find(dst_path) #check existance

        mdf.update(source)
        logger.debug('%s is moved to %s!'%(s_path, d_path))

    def remove_file(self, file_path):
        file_path = to_nimbus_path(file_path)
        logger.debug('removing file %s ...'%file_path)
        self.transactions_manager.remove_file(file_path)
        logger.debug('file %s is removed!'%file_path)

    def open_file(self, file_path, for_write=False):
        file_path = to_nimbus_path(file_path)
        return SmartFileObject(file_path, for_write)

    def inprocess_operations(self, only_inprogress=True):
        ret_list = []
        for is_upload, file_path, status, size, progress_perc in self.transactions_manager.iterate_transactions():
            if only_inprogress and status in (Transaction.TS_FINISHED, Transaction.TS_FAILED):
                continue
            ret_list.append(InprogressOperation(is_upload, file_path, status, size, progress_perc))
        return ret_list

    def has_incomlete_operations(self):
        for _, _, status, _, _ in self.transactions_manager.iterate_transactions():
            if status not in (Transaction.TS_FINISHED, Transaction.TS_FAILED):
                return True
        return False

    def transactions_progress(self):
        up_data_sum = 0
        up_data_all = 0
        down_data_sum = 0
        down_data_all = 0

        for is_upload, _, status, size, progress_perc in self.transactions_manager.iterate_transactions():
            if status not in (Transaction.TS_FINISHED, Transaction.TS_FAILED):
                if is_upload:
                    up_data_sum += (size * progress_perc)/100.
                    up_data_all += size
                else:
                    down_data_sum += (size * progress_perc)/100. 
                    down_data_all += size

        if up_data_all == 0:
            up_perc = 100 #all data is upladed
        else:
            up_perc = (100 * up_data_sum) / up_data_all

        if down_data_all == 0:
            down_perc = 100 #all data is downloaded
        else:
            down_perc = (100 * down_data_sum) / down_data_all

        if up_data_all == down_data_all == 0:
            sum_perc = 100
        else:
            sum_perc = (100 * (up_data_sum + down_data_sum)) / (up_data_all + down_data_all)

        return up_perc, down_perc, sum_perc


