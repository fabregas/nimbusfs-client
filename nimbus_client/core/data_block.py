#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.data_block
@author Konstantin Andrusenko
@date February 04, 2013

This module contains the implementation of DataBlock class
"""
import os
import time
import copy
import shutil
import hashlib
import threading

from nimbus_client.core.exceptions import TimeoutException, IOException
from nimbus_client.core.constants import BUF_LEN, READ_TRY_COUNT, READ_SLEEP_TIME

class DBLocksManager:
    def __init__(self):
        self.__locks = {}
        self.__thrd_lock = threading.RLock()

    def set(self, lock_obj):
        self.__thrd_lock.acquire()
        try:
            cur_locks = self.__locks.get(lock_obj, 0)
            self.__locks[lock_obj] = cur_locks+1
        finally:
            self.__thrd_lock.release()

    def release(self, lock_obj):
        self.__thrd_lock.acquire()
        try:
            cur_locks = self.__locks.get(lock_obj, 0)
            if cur_locks <= 1:
                del self.__locks[lock_obj]
            else:
                self.__locks[lock_obj] = cur_locks-1
        finally:
            self.__thrd_lock.release()

    def locked(self, lock_obj):
        self.__thrd_lock.acquire()
        try:
            cur_locks = self.__locks.get(lock_obj, 0)
            if cur_locks <= 0:
                return False
            return True
        finally:
            self.__thrd_lock.release()

    def locks(self):
        self.__thrd_lock.acquire()
        try:
            return [copy.copy(lock_obj) for lock_obj in self.__locks]
        finally:
            self.__thrd_lock.release()



class DataBlock:
    SECURITY_MANAGER = None
    LOCK_MANAGER = None

    @classmethod
    def is_locked(cls, path):
        if cls.LOCK_MANAGER:
            return cls.LOCK_MANAGER.locked(path)
        return False

    def __init__(self, path, raw_len=None, actsize=False, create_if_none=False):
        self.__path = path
        self.__checksum = hashlib.sha1()
        self.__f_obj = None
        self.__encdec = None
        self.__seek = 0
        self.__rest_str = ''
        self.__locked = False
        self.__raw_len = raw_len
        self.__lock = threading.RLock()

        if create_if_none and (not os.path.exists(self.__path)):
            open(self.__path, 'wb').close()

        if self.SECURITY_MANAGER:
            self.__encdec = self.SECURITY_MANAGER.get_encoder(raw_len)
            self.__expected_len = self.__encdec.get_expected_data_len()
        else:
            self.__encdec = None
            self.__expected_len = None

        if actsize:
            self.__expected_len = self.get_actual_size()
            self.__encdec.set_expected_data_len(self.__expected_len)


    def exists(self):
        return os.path.exists(self.__path)

    def get_actual_size(self):
        if not os.path.exists(self.__path):
            return 0
        return os.path.getsize(self.__path)

    def full(self):
        return self.get_actual_size() == self.__expected_len

    def get_progress(self):
        self.__lock.acquire()
        try:
            return self.__seek, self.__expected_len
        finally:
            self.__lock.release()

    def __del__(self):
        self.close()

    def clone(self):
        return DataBlock(self.__path, self.__raw_len)

    def checksum(self):
        return self.__checksum.hexdigest()

    def get_name(self):
        return os.path.basename(self.__path)

    def remove(self):
        self.close()
        if os.path.exists(self.__path):
            os.remove(self.__path)

    def write(self, data, finalize=False, encrypt=True):
        """Encode (if security manager is setuped) and write to file
        data block.
        NOTICE: file object will be not closed after this method call.
        """
        if self.__is_closed():
            self.__backup_db()
            self.__f_obj = self.__open_file('wb')
            self.__restore_db()

        if encrypt and self.__encdec:
            data = self.__encdec.encrypt(data, finalize)

        self.__checksum.update(data)

        self.__f_obj.write(data)
        self.__lock.acquire()
        try:
            self.__seek += len(data)
        finally:
            self.__lock.release()

        return data

    def finalize(self):
        self.write('', finalize=True)
        self.__f_obj.close()
        self.__expected_len = self.__seek
        self.__seek = 0
        self.__checksum = hashlib.sha1()

    def flush(self):
        if self.__f_obj:
            self.__f_obj.flush()

    def close(self):
        if self.__f_obj and not self.__f_obj.closed:
            self.__f_obj.close()

        if self.__locked:
            self.LOCK_MANAGER.release(self.__path)
            self.__locked = False


    def read_raw(self, rlen=None):
        ret_str = ''
        try:
            if rlen is None:
                while True:
                    buf = self.__read_buf(BUF_LEN)
                    if not buf:
                        break
                    ret_str += buf
            else:
                ret_str = self.__read_buf(rlen)

            if ret_str:
                self.__checksum.update(ret_str)
        except IOError, err:
            raise IOException("Can't read data block! Details: %s"%err)

        return ret_str

    def read(self, rlen=None):
        ret_str = self.__rest_str
        self.__rest_str = ''
        while True:
            if rlen and len(ret_str) >= rlen:
                self.__rest_str = ret_str[rlen:]
                ret_str = ret_str[:rlen]
                break

            data = self.read_raw(BUF_LEN)
            if not data:
                break

            data = self.__encdec.decrypt(data)
            ret_str += data

        return ret_str

    def __open_file(self, open_flags):
        if self.LOCK_MANAGER and not self.__locked:
            self.LOCK_MANAGER.set(self.__path)
            self.__locked = True

        return open(self.__path, open_flags)

    def __is_closed(self):
        return ((not self.__f_obj) or self.__f_obj.closed)

    def __read_buf(self, read_buf_len):
        if self.__expected_len is None:
            raise RuntimeError('Unknown data block size!')
        if self.__expected_len <= self.__get_seek():
            return None

        ret_data = ''
        remained_read_len = read_buf_len
        for i in xrange(READ_TRY_COUNT):
            if self.__is_closed():
                self.__f_obj = self.__open_file('rb')
                self.__f_obj.seek(self.__get_seek())

            data = self.__f_obj.read(remained_read_len)
            read_data_len = len(data)

            self.__lock.acquire()
            try:
                self.__seek += read_data_len
            finally:
                self.__lock.release()

            ret_data += data
            remained_read_len -= read_data_len

            if remained_read_len:
                self.__f_obj.close()
                if self.__expected_len <= self.__get_seek():
                    break
                else:
                    time.sleep(READ_SLEEP_TIME)    
            else:
                break
        else:
            raise TimeoutException('read data block timeouted at %s'%self.__path)

        return ret_data

    def __get_seek(self):
        self.__lock.acquire()
        try:
            return self.__seek
        finally:
            self.__lock.release()

    def __backup_db(self):
        if os.path.exists(self.__path):
            shutil.move(self.__path, self.__path+'.back')

    def __restore_db(self):
        if not os.path.exists(self.__path+'.back'):
            return

        bdb = DataBlock(self.__path+'.back', actsize=True)
        while True:
            data = bdb.read(BUF_LEN)
            if not data:
                break
            self.write(data)
        bdb.remove()
