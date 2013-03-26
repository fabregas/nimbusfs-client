#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.base_safe_object
@author Konstantin Andrusenko
@date February 18, 2013

This module contains the implementation of LockObject class
"""
import threading

class LockObject:
    def __init__(self):
        self.__lock = threading.RLock()

    def __call__(self, f):
        """Decorator for methods synchronization"""
        def wrapFunction(*args, **kw):
            self.__lock.acquire()
            try:
                return f(*args, **kw)
            finally:
                self.__lock.release()
        return wrapFunction

    def lock(self):
        self.__lock.acquire()

    def unlock(self):
        self.__lock.release()

