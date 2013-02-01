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

import time
import hashlib

from nimbus_client.core.exceptions import TimeoutException
from nimbus_client.core.constants import BUF_LEN, READ_TRY_COUNT, READ_SLEEP_TIME

class DataBlock:
    SECURITY_MANAGER = None

    def __init__(self, path, raw_len):
        self.__path = path
        self.__checksum = hashlib.sha1()
        self.__f_obj = None
        self.__encdec = None
        self.__seek = 0
        self.__rest_str = ''
        if self.SECURITY_MANAGER:
            self.__encdec = self.SECURITY_MANAGER.get_encoder(raw_len)
        else:
            self.__encdec = None
        self.__expected_len = self.__encdec.get_expected_data_len()

    def __del__(self):
        self.close()

    def checksum(self):
        return self.__checksum.hexdigest()

    def write(self, data):
        """Encode (if security manager is setuped) and write to file
        data block.
        NOTICE: file object will be not closed after this method call.
        """
        if self.__encdec:
            data = self.__encdec.encrypt(data)

        self.__checksum.update(data)

        if not self.__f_obj:
            self.__f_obj = open(self.__path, 'ab')

        self.__f_obj.write(data)
        self.__seek += len(data)

        return data

    def close(self):
        if self.__f_obj and not self.__f_obj.closed:
            self.__f_obj.close()


    def read_raw(self, rlen=None):
        ret_str = ''
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


    def __is_closed(self):
        return ((not self.__f_obj) or self.__f_obj.closed)

    def __read_buf(self, read_buf_len):
        if self.__expected_len <= self.__seek:
            return None

        ret_data = ''
        remained_read_len = read_buf_len
        for i in xrange(READ_TRY_COUNT):
            if self.__is_closed():
                self.__f_obj = open(self.__path, 'rb')
                self.__f_obj.seek(self.__seek)

            data = self.__f_obj.read(remained_read_len)
            read_data_len = len(data)
            self.__seek += read_data_len
            ret_data += data
            remained_read_len -= read_data_len

            if remained_read_len:
                self.__f_obj.close()
                if self.__expected_len <= self.__seek:
                    break
                else:
                    time.sleep(READ_SLEEP_TIME)    
            else:
                break
        else:
            raise TimeoutException('read data block timeouted at %s'%self.__path)

        return ret_data

