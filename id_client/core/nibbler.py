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
import tempfile
import hashlib
from constants import FILE_ITER_BLOCK_SIZE, CHUNK_SIZE
from logger import logger
from fabnet_gateway import FabnetGateway
from metadata import *
from parallel_put import PutDataManager
from parallel_get import GetDataManager

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



class Nibbler:
    def __init__(self, fabnet_host, security_provider, parallel_put=3, parallel_get=3):
        self.security_provider = security_provider
        self.fabnet_gateway = FabnetGateway(fabnet_host, security_provider)
        self.metadata = None
        self.__not_sync_files = {}
        self.put_manager = PutDataManager(self.fabnet_gateway, self.__finish_file_put, parallel_put)
        self.get_manager = GetDataManager(self.fabnet_gateway, parallel_get)

        user_id = self.security_provider.get_client_cert()
        self.metadata_key = hashlib.sha1(user_id).hexdigest()

        self.put_manager.start()
        self.get_manager.start()

    def on_error(self, error_msg):
        pass

    def stop(self):
        self.put_manager.stop()
        self.get_manager.stop()

    def get_inprocess_uploads(self):
        return self.__not_sync_files.keys()


    def __get_metadata(self, reload_force=False, metadata_key=None):
        if self.metadata and not reload_force:
            return self.metadata

        self.metadata = None
        if not metadata_key:
            metadata_key = self.metadata_key

        metadata = self.fabnet_gateway.get(metadata_key)
        if metadata is None:
            raise Exception('No metadata found!')

        mdf = MetadataFile()
        mdf.load(metadata)
        self.metadata = mdf
        return self.metadata

    def __save_metadata(self):
        version_key = self.metadata.make_new_version(self.metadata_key)
        metadata = self.metadata.dump()
        try:
            self.fabnet_gateway.put(metadata, key=version_key)
        except Exception, err:
            self.metadata.remove_version(version_key)
            raise err

        try:
            self.fabnet_gateway.put(metadata, key=self.metadata_key)
        except Exception, err:
            self.__get_metadata(reload_force=True)
            raise err

    def register_user(self):
        if self.metadata:
            logger.warning('Trying register user in fabnet, but it is already registered!')
            return

        metadata = self.fabnet_gateway.get(self.metadata_key)
        if metadata is not None:
            logger.warning('Trying register user in fabnet, but it is already registered!')
            return

        mdf = MetadataFile()
        mdf.load('{}')
        self.fabnet_gateway.put(mdf.dump(), key=self.metadata_key)
        self.metadata = mdf
        logger.info('User is registered in fabnet successfully')

    @synchronized(lock)
    def get_resource(self, path):
        mdf = self.__get_metadata()
        try:
            path_obj = mdf.find(path)
            return path_obj
        except PathException, err:
            #logger.debug('[get_resource] %s'%str(err))
            return None

    @synchronized(lock)
    def get_versions(self):
        mdf = self.__get_metadata()
        return mdf.get_versions()

    @synchronized(lock)
    def load_version(self, version_key):
        self.__get_metadata(reload_force=True, metadata_key=version_key)

    @synchronized(lock)
    def listdir(self, path='/'):
        mdf = self.__get_metadata()
        dir_obj = mdf.find(path)
        if not dir_obj.is_dir():
            raise Exception('%s is a file!'%path)

        return dir_obj.items()

    @synchronized(lock)
    def mkdir(self, path, recursive=False):
        mdf = self.__get_metadata()
        if mdf.exists(path):
            raise Exception('Directory is already exists!'%path)

        base_path, new_dir = os.path.split(path)

        if not mdf.exists(base_path):
            if recursive:
                self.mkdir(base_path, recursive)
            else:
                raise Exception('Directory "%s" does not exists!'%base_path)

        base_path_obj = mdf.find(base_path)
        new_dir_obj = DirectoryMD(new_dir)
        base_path_obj.append(new_dir_obj)
        self.__save_metadata()

    @synchronized(lock)
    def rmdir(self, path, recursive=False):
        mdf = self.__get_metadata()

        dir_obj = mdf.find(path)
        if not dir_obj.is_dir():
            raise Exception('%s is a file!'%path)


        items = dir_obj.items()
        if items and not recursive:
            raise Exception('Directory "%s" is not empty!'%path)

        for item in items:
            full_path = os.path.join(path, item[0])
            if item[1]:
                self.remove_file(full_path)
            else:
                self.rmdir(full_path, recursive)

        base_path, rm_dir = os.path.split(path)
        base_dir = mdf.find(base_path)
        base_dir.remove(rm_dir)
        self.__save_metadata()

    @synchronized(lock)
    def save_file(self, file_path, file_name, dest_dir):
        if file_path and not os.path.exists(file_path):
            raise Exception('File %s does not found!'%file_path)

        mdf = self.__get_metadata()

        dir_obj = mdf.find(dest_dir)
        if not dir_obj.is_dir():
            raise Exception('%s is a file!'%dest_dir)

        if file_path:
            file_size = os.stat(file_path).st_size
        else:
            file_size = 0

        if isinstance(file_name, FileMD):
            file_md = file_name
            file_md.size = file_size
        else:
            file_md = FileMD(file_name, file_size)

        file_md.parent_dir = dir_obj

        if file_size > 0:
            self.__not_sync_files[file_md.name] = file_md
            logger.info('Saving file %s to fabnet'%file_md.name)
            self.put_manager.put_file(file_md, file_path)

    def __finish_file_put(self, file_md):
        lock.acquire()
        try:
            dir_obj = file_md.parent_dir
            dir_obj.append(file_md)

            is_error = False
            try:
                self.__save_metadata()
            except Exception, err:
                logger.error('Save metadata error: %s'%err)
                logger.info('Trying rollback file %s'%file_md.name)
                #TODO: remove file should be implemented!
                is_error = True
            finally:
                del self.__not_sync_files[file_md.name]
        finally:
            lock.release()

        if is_error:
            self.on_error('File %s was not uploaded to service!'%file_md.name)

    def load_file(self, file_path):
        lock.acquire()
        try:
            if isinstance(file_path, FileMD):
                file_obj = file_path
            else:
                mdf = self.__get_metadata()
                if not mdf.exists(file_path):
                    raise Exception('File %s does not found!'%file_path)
                file_obj = mdf.find(file_path)

            if not file_obj.is_file():
                raise Exception('%s is not a file!'%file_path)
        finally:
            lock.release()

        streem = self.get_manager.get_file(file_obj)
        streem.wait_get()
        return streem.get_file_obj()

    @synchronized(lock)
    def move(self, s_path, d_path):
        logger.info('mv %s to %s'%(s_path, d_path))
        mdf, d_obj, source, new_name, dst_path = self._cpmv_int(s_path, d_path)

        base_path, s_name = os.path.split(s_path)
        mdf.find(base_path).remove(s_name)

        if new_name:
            source.name = new_name

        d_obj.append(source)
        self.__save_metadata()

    @synchronized(lock)
    def copy(self, s_path, d_path):
        logger.info('cp %s to %s'%(s_path, d_path))
        mdf, d_obj, source, new_name, dst_path = self._cpmv_int(s_path, d_path)
        if not new_name:
            new_name = source.name

        if source.is_file():
            fhdl = self.load_file(s_path)
            try:
                self.save_file(fhdl.name, new_name, dst_path)
            finally:
                fhdl.close()
        else:
            dst_dir = os.path.join(dst_path, new_name)
            self.mkdir(dst_dir)
            for i_name, dummy in source.items():
                self.copy(os.path.join(s_path, i_name), dst_dir)

        self.__save_metadata()

    def _cpmv_int(self, s_path, d_path):
        mdf = self.__get_metadata()
        if not mdf.exists(s_path):
            raise Exception('Path %s does not found!'%s_path)

        if mdf.exists(d_path):
            new_name = None
            dst_path = d_path
            d_obj = mdf.find(d_path)
            if d_obj.is_file():
                raise Exception('File %s is already exists!'%d_path)
        else:
            dst_path, new_name = os.path.split(d_path)
            if not mdf.exists(dst_path):
                raise Exception('Directory %s does not found!'%dst_path)
            d_obj = mdf.find(dst_path)

        source = mdf.find(s_path)
        return mdf, d_obj, source, new_name, dst_path


    @synchronized(lock)
    def remove_file(self, file_path):
        mdf = self.__get_metadata()
        if not mdf.exists(file_path):
            raise Exception('File %s does not found!'%file_path)

        parent_dir, file_name = os.path.split(file_path)
        dir_obj = mdf.find(parent_dir)

        dir_obj.remove(file_name)
        self.__save_metadata()

