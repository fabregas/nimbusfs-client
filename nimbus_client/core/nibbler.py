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
from datetime import datetime, timedelta
from constants import FILE_ITER_BLOCK_SIZE, CHUNK_SIZE, \
            OT_SAVE, OT_LOAD, ASYNC_WAIT_TIMEOUT
from logger import logger
from fabnet_gateway import FabnetGateway
from metadata import *
from parallel_put import PutDataManager
from parallel_get import GetDataManager
from nimbus_client.core.exceptions import *
import threading
lock = threading.RLock()


def synchronized(lock):
    """ Synchronization decorator. """
    def wrap(f):
        def wrapFunction(*args, **kw):
            lock.acquire()
            try:
                return f(*args, **kw)
            finally:
                lock.release()
        return wrapFunction
    return wrap


class FSItem:
    def __init__(self, item_name, is_dir, create_dt=None, modify_dt=None, size=0):
        self.name = item_name
        self.is_dir = is_dir
        self.is_file = not is_dir
        self.size = size

        if create_dt is None:
            create_dt = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        if modify_dt is None:
            modify_dt = create_dt
        self.create_dt = create_dt
        self.modify_dt = modify_dt

class RunnedOperation:
    def __init__(self, op_type, file_name):
        self.op_type = op_type
        self.file_name = file_name


class Nibbler:
    def __init__(self, fabnet_host, security_provider, parallel_put_count=3, parallel_get_count=3):
        self.security_provider = security_provider
        self.fabnet_gateway = FabnetGateway(fabnet_host, security_provider)
        self.metadata = None
        self.__inprogress_oplist = {}
        self.put_manager = PutDataManager(self.fabnet_gateway, self.__finish_file_put, parallel_put_count)
        self.get_manager = GetDataManager(self.fabnet_gateway, parallel_get_count, self.__finish_file_load)

        user_id = self.security_provider.get_client_cert()
        self.metadata_key = hashlib.sha1(user_id).hexdigest()

        self.put_manager.start()
        self.get_manager.start()

    def on_error(self, error_msg):
        pass

    def stop(self):
        self.put_manager.stop()
        self.get_manager.stop()


    def __get_metadata(self, reload_force=False):
        if self.metadata and not reload_force:
            return self.metadata

        self.metadata = None
        metadata = self.fabnet_gateway.get(self.metadata_key)
        if metadata is None:
            raise NoMetadataException('No metadata found!')

        mdf = MetadataFile()
        mdf.load(metadata)
        self.metadata = mdf
        return self.metadata

    def __save_metadata(self):
        metadata = self.metadata.save()
        try:
            self.fabnet_gateway.put(metadata, key=self.metadata_key)
        except Exception, err:
            self.__get_metadata(reload_force=True)
            raise err

    def __make_item_fs(self, item_md):
        create_dt = getattr(item_md, 'create_date', None)
        modify_dt = getattr(item_md, 'last_modify_date', None)
        size = getattr(item_md, 'size', 0)

        return FSItem(item_md.name, item_md.is_dir(), create_dt, modify_dt, size)

    def is_registered(self):
        if self.metadata:
            return True

        metadata = self.fabnet_gateway.get(self.metadata_key)
        if metadata is not None:
            return True

        return False

    def register_user(self):
        if self.is_registered():
            logger.warning('Trying register user in fabnet, but it is already registered!')
            return

        mdf = MetadataFile()
        mdf.load('{}')
        self.fabnet_gateway.put(mdf.save(), key=self.metadata_key)
        self.metadata = mdf
        logger.info('User is registered in fabnet successfully')

    @synchronized(lock)
    def find(self, path):
        path = path.decode('utf8')
        mdf = self.__get_metadata()
        try:
            path_obj = mdf.find(path)

            return self.__make_item_fs(path_obj)
        except PathException, err:
            #logger.debug('[get_resource] %s'%str(err))
            return None

    @synchronized(lock)
    def listdir(self, path='/'):
        path = path.decode('utf8')
        mdf = self.__get_metadata()
        dir_obj = mdf.find(path)
        if not dir_obj.is_dir():
            raise NotDirectoryException('%s is a file!'%path)

        return [self.__make_item_fs(i) for i in dir_obj.items()]

    @synchronized(lock)
    def mkdir(self, path, recursive=False):
        path = path.decode('utf8')
        mdf = self.__get_metadata()
        if mdf.exists(path):
            raise AlreadyExistsException('Directory "%s" is already exists!'%path)

        base_path, new_dir = os.path.split(path)

        if not mdf.exists(base_path):
            if recursive:
                self.mkdir(base_path, recursive)
            else:
                raise PathException('Directory "%s" does not exists!'%base_path)

        new_dir_obj = DirectoryMD(new_dir)
        mdf.append(base_path, new_dir_obj)
        self.__save_metadata()

    @synchronized(lock)
    def rmdir(self, path, recursive=False):
        path = path.decode('utf8')
        mdf = self.__get_metadata()

        dir_obj = mdf.find(path)
        if not dir_obj.is_dir():
            raise NotDirectoryException('%s is a file!'%path)

        items = dir_obj.items()
        if items and not recursive:
            raise NotEmptyException('Directory "%s" is not empty!'%path)

        for item in items:
            full_path = os.path.join(path, item.name)
            if item.is_file():
                self.remove_file(full_path)
            else:
                self.rmdir(full_path, recursive)

        mdf.remove(path)
        self.__save_metadata()

    @synchronized(lock)
    def save_file(self, local_file_path, save_name, dest_dir, callback_func=None):
        save_name = save_name.decode('utf8')
        dest_dir = dest_dir.decode('utf8')
        if local_file_path and not os.path.exists(local_file_path):
            raise LocalPathException('File %s does not found!'%local_file_path)

        mdf = self.__get_metadata()
        dir_obj = mdf.find(dest_dir)
        if not dir_obj.is_dir():
            raise NotDirectoryException('%s is a file!'%dest_dir)

        out_path = os.path.join(dest_dir, save_name)
        if mdf.exists(out_path):
            raise AlreadyExistsException('File %s is already exists'%out_path)

        if local_file_path:
            file_size = os.stat(local_file_path).st_size
        else:
            file_size = 0

        file_md = FileMD(save_name, file_size)
        file_md.parent_dir = dest_dir
        file_md.callback = callback_func

        if file_size == 0:
            return None

        logger.info('Saving file %s to fabnet'%file_md.name)
        self.__inprogress_oplist[file_md.id] = (OT_SAVE, file_md)
        self.put_manager.put_file(file_md, local_file_path)
        return file_md.id


    def __finish_file_put(self, file_md):
        lock.acquire()
        try:
            mdf = self.__get_metadata()
            mdf.append(file_md.parent_dir, file_md)

            err_msg = None
            try:
                self.__save_metadata()
            except Exception, err:
                logger.error('Save metadata error: %s'%err)
                logger.info('Trying rollback file %s'%file_md.name)
                #TODO: remove file should be implemented!
                err_msg = 'File %s was not uploaded to service! Details: %s'%(file_md.name, err)
            finally:
                del self.__inprogress_oplist[file_md.id]
        finally:
            lock.release()

        if file_md.callback:
            try:
                file_md.callback(err_msg)
            except Exception, err:
                logger.error('Callback function error: %s'%err)

        del file_md.parent_dir
        del file_md.callback

        if err_msg:
            self.on_error(err_msg)

    def load_file(self, file_path, out_local_file, callback_func=None):
        file_path = file_path.decode('utf8')
        lock.acquire()
        try:
            mdf = self.__get_metadata()
            file_obj = mdf.find(file_path)

            if not file_obj.is_file():
                raise NotFileException('%s is not a file!'%file_path)

            file_obj.callback = callback_func
            self.__inprogress_oplist[file_obj.id] = (OT_LOAD, file_obj)
        finally:
            lock.release()

        self.get_manager.get_file(file_obj, out_local_file)
        return file_obj.id

    def __finish_file_load(self, file_id, error):
        lock.acquire()
        try:
            _, file_md = self.__inprogress_oplist[file_id]
            del self.__inprogress_oplist[file_id]
        finally:
            lock.release()

        if file_md.callback:
            try:
                file_md.callback(error)
            except Exception, err:
                logger.error('Callback function error: %s'%err)

        del file_md.callback
        if error:
            self.on_error(error)

    @synchronized(lock)
    def move(self, s_path, d_path):
        s_path = s_path.decode('utf8')
        d_path = d_path.decode('utf8')

        mdf = self.__get_metadata()
        source = mdf.find(s_path)

        if mdf.exists(d_path):
            new_name = None
            dst_path = d_path
            d_obj = mdf.find(d_path)
            if d_obj.is_file():
                raise AlreadyExistsException('File %s is already exists!'%d_path)
        else:
            dst_path, new_name = os.path.split(d_path)
            mdf.find(dst_path) #check existance

        mdf.remove(s_path)
        if new_name:
            source.name = new_name
        mdf.append(dst_path, source)
        self.__save_metadata()


    @synchronized(lock)
    def remove_file(self, file_path):
        file_path = file_path.decode('utf8')
        mdf = self.__get_metadata()
        #TODO: remove file from NimbusFS should be implemented!
        mdf.remove(file_path)
        self.__save_metadata()

    def wait_async_operation(self, operation_id, timeout=None):
        if timeout:
            exp_time = datetime.now() + timedelta(0, int(timeout))

        while True:
            time.sleep(ASYNC_WAIT_TIMEOUT)

            lock.acquire()
            try:
                if not self.__inprogress_oplist.has_key(operation_id):
                    break
            finally:
                lock.release()

            if timeout and exp_time < datetime.now():
                raise TimeoutException('Operation with ID %s is timeouted!'%operation_id)

    def inprocess_operations(self):
        ret_list = []
        lock.acquire()
        try:
            for op_type, item_md in self.__inprogress_oplist.values():
                ret_list.append(RunnedOperation(op_type, item_md.name))
        finally:
            lock.release()

        return ret_list

    """
    @synchronized(lock)
    def get_versions(self):
        mdf = self.__get_metadata()
        return mdf.get_versions()

    @synchronized(lock)
    def load_version(self, version_key):
        self.__get_metadata(reload_force=True, metadata_key=version_key)
    """
