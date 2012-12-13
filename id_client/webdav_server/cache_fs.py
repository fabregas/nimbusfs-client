#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package webdav_server.cache_fs
@author Konstantin Andrusenko
@date December 3, 2012
"""
import os
import tempfile
import threading


class CacheFS:
    def __init__(self, cache_dir, max_size=0):
        self.__cache_dir = cache_dir
        self.__max_size = max_size
        self.__prefix = 'webdav-cache-'
        self.__cache = {}
        self.__lock = threading.RLock()
        self.__clear_cache()

    def __clear_cache(self):
        self.__lock.acquire()
        try:
            for file_name in os.listdir(self.__cache_dir):
                if not file_name.startswith(self.__prefix):
                    continue
                os.unlink(os.path.join(self.__cache_dir, file_name))
        finally:
            self.__lock.release()

    def get_dir_content(self, path):
        self.__lock.acquire()
        try:
            dir_c = self.__cache.get(path, {})
            return dir_c.keys()
        finally:
            self.__lock.release()

    def get(self, path):
        dirname, filename = os.path.split(path)
        self.__lock.acquire()
        try:
            dir_c = self.__cache.get(dirname, None)
            if not dir_c:
                return None
            return self.__cache[dirname].get(filename, None)
        finally:
            self.__lock.release()

    def put(self, path, cache_file_name):
        dirname, filename = os.path.split(path)
        self.__lock.acquire()
        try:
            if not self.__cache.has_key(dirname):
                self.__cache[dirname] = {}

            self.__cache[dirname][filename] = cache_file_name
        finally:
            self.__lock.release()

    def remove(self, path):
        dirname, filename = os.path.split(path)
        self.__lock.acquire()
        try:
            if self.__cache.has_key(dirname) and self.__cache[dirname].has_key(filename):
                f_path = self.__cache[dirname][filename]
                os.unlink(f_path)
                del self.__cache[dirname][filename]
        finally:
            self.__lock.release()

    def make_cache_file(self, path):
        dirname, filename = os.path.split(path)
        self.__lock.acquire()
        try:
            old_f = self.get(path)
            if old_f:
                os.unlink(old_f)

            f_idx, tmpfl = tempfile.mkstemp(prefix=self.__prefix, dir=self.__cache_dir)
            f = os.fdopen(f_idx)
            f.close()

            self.put(path, tmpfl)
            return tmpfl
        finally:
            self.__lock.release()

