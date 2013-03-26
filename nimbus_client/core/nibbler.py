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
from nimbus_client.core.utils import to_str


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
        self.__parallel_put_count = parallel_put_count
        self.__parallel_get_count = parallel_get_count
        self.security_provider = security_provider
        self.fabnet_gateway = FabnetGateway(fabnet_host, security_provider)
        self.db_cache = DataBlockCache(cache_dir, cache_size)

        user_id = self.security_provider.get_client_cert()
        self.metadata_key = hashlib.sha1(user_id).hexdigest()

        self.journal = None
        self.metadata = None
        self.transactions_manager = None
        self.put_manager = None
        self.get_manager = None

        DataBlock.SECURITY_MANAGER = self.security_provider
        DataBlock.LOCK_MANAGER = DBLocksManager()

        self.journal = Journal(self.metadata_key, \
                self.db_cache.get_static_cache_path('journal.bin'), self.fabnet_gateway)
        
    def start(self):
        if not self.journal.foreign_exists():
            raise NoJournalFoundException('No journal for key = %s'%self.metadata_key)

        self.metadata = MetadataFile(self.db_cache.get_static_cache_path('md.bin'), self.journal)
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
            self.metadata = MetadataFile(self.db_cache.get_static_cache_path('md.bin'), self.journal)

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
        path = to_str(path)
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
        path = to_str(path)
        items = self.metadata.listdir(path)
        ret_lst = [self.__make_item_fs(i) for i in items]
 
        #try to find uploading files in @path (fully saved into data blocks cache)
        for is_upload, file_path, status, size, _ in self.transactions_manager.iterate_transactions():
            if not is_upload:
                continue
            if status != Transaction.TS_LOCAL_SAVED:
                continue
            base_path, file_name = os.path.split(file_path)
            if base_path == path:
                ret_lst.append(self.__make_item_fs(FileMD(name=file_name, size=size)))
        return ret_lst


    def mkdir(self, path, recursive=False):
        path = to_str(path)
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
        path = to_str(path)
        logger.debug('rmdir %s ...'%path)
        mdf = self.metadata

        dir_obj = mdf.find(path)
        if not dir_obj.is_dir():
            raise NotDirectoryException('%s is a file!'%path)

        items = mdf.listdir(path)
        if items and not recursive:
            raise NotEmptyException('Directory "%s" is not empty!'%path)

        for item in items:
            full_path = os.path.join(path, item.name)
            if item.is_file():
                self.remove_file(full_path)
            else:
                self.rmdir(full_path, recursive)

        mdf.remove(dir_obj)

    def move(self, s_path, d_path):
        s_path = to_str(s_path)
        d_path = to_str(d_path)
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

    def remove_file(self, file_path):
        file_path = to_str(file_path)
        logger.debug('removing file %s ...'%file_path)
        file_md = self.metadata.find(file_path)
        if not file_md.is_file():
            raise NotFileException('%s is not a file!'%dest_dir)
        self.metadata.remove(file_md)
        #TODO: remove file from NimbusFS should be implemented!

    def open_file(self, file_path, for_write=False):
        file_path = to_str(file_path)
        logger.debug('opening file %s for %s...'%(file_path, 'write' if for_write else 'read'))
        return SmartFileObject(file_path, for_write)

    def inprocess_operations(self):
        ret_list = []
        for is_upload, file_path, status, size, progress_perc in self.transactions_manager.iterate_transactions():
            ret_list.append(InprogressOperation(is_upload, file_path, status, size, progress_perc))
        return ret_list

    def has_incomlete_operations(self):
        for _, _, status, _, _ in self.transactions_manager.iterate_transactions():
            if status not in (Transaction.TS_FINISHED, Transaction.TS_FAILED):
                return True
        return False

