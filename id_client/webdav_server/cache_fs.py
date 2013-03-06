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
    def __init__(self):
        self.__cache = {}
        self.__lock = threading.RLock()
        self.__clear_cache()

    def __clear_cache(self):
        self.__lock.acquire()
        try:
            self.__cache = {}
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

    def put(self, path, file_obj):
        dirname, filename = os.path.split(path)
        self.__lock.acquire()
        try:
            if not self.__cache.has_key(dirname):
                self.__cache[dirname] = {}

            self.__cache[dirname][filename] = file_obj
        finally:
            self.__lock.release()

    def remove(self, path):
        dirname, filename = os.path.split(path)
        self.__lock.acquire()
        try:
            if self.__cache.has_key(dirname) and self.__cache[dirname].has_key(filename):
                f_path = self.__cache[dirname][filename]
                del self.__cache[dirname][filename]
        finally:
            self.__lock.release()

