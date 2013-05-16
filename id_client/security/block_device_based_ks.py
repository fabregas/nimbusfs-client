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
from id_client.security.block_device import BlockDevice

class FileOnBlockDevice:
    def __init__(self, path):
        self.__path = path
        self.__dev = BlockDevice(path)

    def exists(self):
        if not os.path.exists(self.__path):
            return False
        if self.__dev.is_valid():
            return True
        return False

    def create_empty(self):
        self.__dev.format_device()
        self.__dev.write('')

    def copy_from(self, dest_file):
        self.__dev.write_from_file(dest_file)

    def read(self):
        return self.__dev.read()

        

class BlockDeviceBasedSecurityManager(FileBasedSecurityManager):
    ks_file_class = FileOnBlockDevice

