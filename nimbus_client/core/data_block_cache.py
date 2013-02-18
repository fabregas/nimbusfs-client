#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.data_block_cache
@author Konstantin Andrusenko
@date February 17, 2013

This module contains the implementation of DataBlockCache class
"""
import os
import time
import threading
from logger import logger

CHECK_CAPACITY_TIME = 5
MIN_FREE_CAPACITY = 10

class DataBlockCache:
    def __init__(self, cache_dir, allow_capacity=None):
        if not os.path.exists(cache_dir):
            raise Exception('No cache dir found at %s'%cache_dir)

        self.__cache_dir = os.path.abspath(cache_dir)
        self.__dyn_cache = os.path.join(self.__cache_dir, 'dynamic_cache')
        self.__stat_cache = os.path.join(self.__cache_dir, 'static_cache')
        self.__allow_capacity = allow_capacity
        self.__lock = threading.RLock()
        self.__check_capacity_thrd = CheckCapacityThrd(self)

        if not os.path.exists(self.__dyn_cache):
            os.mkdir(self.__dyn_cache)
        if not os.path.exists(self.__stat_cache):
            os.mkdir(self.__stat_cache)
        self.__check_capacity_thrd.start()

    def stop(self):
        self.__check_capacity_thrd.stop()
    
    def __calculate_busy_size(self, dir_path):
        busy_size = 0
        self.__lock.acquire()
        try:
            for item in os.listdir(dir_path):
                path = os.path.join(dir_path, item)
                if os.path.islink(path):
                    continue
                busy_size += os.path.getsize(path)
        finally:
            self.__lock.release()
        return busy_size

    def busy_size(self):
        return self.__calculate_busy_size(self.__dyn_cache) + \
                self.__calculate_busy_size(self.__stat_cache)

    def mklink(self, cur_db_hash, new_db_hash):
        cur_path = self.get_cache_path(cur_db_hash)
        new_path = self.get_cache_path(new_db_hash)
        os.symlink(cur_path, new_path)
        return new_path

    def get_cache_path(self, db_hash):
        self.__lock.acquire()
        try:
            path = os.path.join(self.__dyn_cache, db_hash)
            if os.path.exists(path) and os.path.islink(path):
                path = os.readlink(path)
                if not os.path.exists(path):
                    path = os.path.join(self.__dyn_cache, path)
            return path
        finally:
            self.__lock.release()

    def get_static_cache_path(self, db_hash):
        return os.path.join(self.__stat_cache, db_hash)

    def can_store(self, need_size):
        self.__lock.acquire()
        try:
            if self.__ph_free_size < need_size:
                if not self.__clear_dyn_cache(need_size-self.__ph_free_size):
                    return False
            return True
        finally:
            self.__lock.release()

    def clear_old(self):
        self.__lock.acquire()
        try:
            stat = os.statvfs(self.__cache_dir)
            self.__ph_free_size = stat.f_bsize * stat.f_bavail
        finally:
            self.__lock.release()

        busy_size = self.busy_size()
        if busy_size == 0:
            return

        if self.__allow_capacity:
            free_size = self.__allow_capacity - busy_size
            if free_size < 0:
                free_size = self.__ph_free_size
            free_size = min(free_size, self.__ph_free_size)
        else:
            free_size = self.__ph_free_size

        free_perc = (free_size * 100.) / (free_size + busy_size)
        if free_perc < MIN_FREE_CAPACITY:
            min_free_allowed = (MIN_FREE_CAPACITY * (free_size + busy_size)) / 100.
            min_for_del = min_free_allowed - free_size

            self.__clear_dyn_cache(min_for_del)

    def __clear_dyn_cache(self, del_size):
        removed_size = 0
        self.__lock.acquire()
        try:
            del_lst = []
            for item in os.listdir(self.__dyn_cache):
                path = os.path.join(self.__dyn_cache, item) 
                if os.path.islink(path):
                    continue
                if DataBlock.is_locked(path):
                    continue

                del_lst.append(path, os.stat(path))
                            
            del_lst = sorted(del_lst, lambda a,b: cmp(a[1].st_atime, b[1].st_atime))
            for path, stat in del_lst:
                os.remove(path)
                removed_size += stat.st_size
                if removed_size >= del_size:
                    break

            for item in os.listdir(self.__dyn_cache):
                path = os.path.join(self.__dyn_cache, item)
                if os.path.islink(path) and not os.path.exists(path):
                    os.remove(path)

            self.__ph_free_size += removed_size
        finally:
            self.__lock.release()

        if removed_size < del_size:
            return False
        return True


class CheckCapacityThrd(threading.Thread):
    def __init__(self, data_block_cache):
        threading.Thread.__init__(self)
        self.__db_cache = data_block_cache
        self.__stop_event = threading.Event()

    def stop(self):
        self.__stop_event.set()
        self.join()

    def run(self):
        logger.info('CheckCapacityThrd is started')
        while True:
            try:
                self.__db_cache.clear_old()
                for i in xrange(CHECK_CAPACITY_TIME):
                    time.sleep(1)
                    if self.__stop_event.is_set():
                        logger.info('CheckCapacityThrd is stopped')
                        return
            except Exception, err:
                logger.error('CheckCapacityThrd: %s'%err)

