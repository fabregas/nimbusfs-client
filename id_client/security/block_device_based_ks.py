#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.security.block_device_based_ks
@author Konstantin Andrusenko
@date May 15, 2013
"""
import os
import struct

from nimbus_client.core.security_manager import FileBasedSecurityManager
from id_client.security.block_device import BlockDevice, DATA_START_SEEK

class KSSignature:
    SIGN_STRUCT = '<6sH'
    SIGN_LEN = struct.calcsize(SIGN_STRUCT)
    SING_ID = 'OFFS01'

    @classmethod
    def dump(cls, ks_len):
        return struct.pack(cls.SIGN_STRUCT, cls.SING_ID, ks_len)

    def __init__(self, dumped=None):
        self.sign_id = None
        self.ks_len = None
        if dumped:
            self.load(dumped)

    def load(self, dumped):
        self.sign_id, self.ks_len = struct.unpack(self.SIGN_STRUCT, dumped)

    def is_valid(self):
        if self.sign_id == self.SING_ID and self.ks_len > 0:
            return True
        return False



class FileOnBlockDevice:
    def __init__(self, path):
        self.__path = path

    def __open_dev(self, read_only=False):
        flags = 'rb'
        if not read_only:
            flags += '+'
        try:
            return open(self.__path, flags)
        except IOError:
            raise IOError('Device %s does not opened for %s!'%(self.__path,\
                    'read' if read_only else 'write'))

    def __read_signature(self, fd):
        try:
            fd.seek(DATA_START_SEEK)
            data = fd.read(KSSignature.SIGN_LEN)
            return KSSignature(data)
        except IOError:
            raise IOError('Device %s can not be read!'%self.__path)

    def __write(self, data):
        fd = self.__open_dev()
        try:
            fd.seek(DATA_START_SEEK)
            fd.write(KSSignature.dump(len(data)))
            fd.write(data)
        except IOError:
            raise IOError('Key chain does not write to device %s!'%self.__path)
        finally:
            fd.close()

    def exists(self):
        if not os.path.exists(self.__path):
            return False

        try:
            fd = self.__open_dev(read_only=True)
        except IOError:
            return False

        try:
            ks_sign = self.__read_signature(fd)
            if ks_sign.is_valid():
                return True
            return False
        finally:
            fd.close()
        
    def create_empty(self):
        BlockDevice.format_device(self.__path)
        self.__write('')

    def copy_from(self, dest_file):
        try:
            data = open(dest_file, 'rb').read()
        except IOError:
            raise IOError('Can not read from "%s"'%dest_file)
        self.__write(data)

    def read(self):
        fd = self.__open_dev(read_only=True)
        sign = self.__read_signature(fd)
        if not sign.is_valid():
            raise Exception('Key chain does not found at %s'%self.__path)
        try:
            return fd.read(sign.ks_len)
        except IOError:
            raise IOError('Key chain can not be read from %s!'%self.__path)

        

class BlockDeviceBasedSecurityManager(FileBasedSecurityManager):
    ks_file_class = FileOnBlockDevice

