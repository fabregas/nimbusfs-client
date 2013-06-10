#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.security.block_device
@author Konstantin Andrusenko
@date May 15, 2013
"""
import os
import sys
import struct
import logging
from zipfile import ZipFile

from nimbus_client.core.utils import TempFile
from id_client.media_storage import get_media_storage_manager
from id_client.security.mbr import *
from nimbus_client.core.utils import Subprocess


logger = logging.getLogger('fabnet-client')
if not logger.handlers:
    console = logging.StreamHandler()
    logger.addHandler(console)

if hasattr(sys,"frozen") and sys.platform == 'win32':
    curdir = os.path.dirname(os.path.abspath(sys.executable))
else:
    curdir = os.path.dirname(__file__)

SUID_BLOCKDEV_MGR = os.path.abspath(os.path.join(curdir, '../../bin/rbd_manage'))

FAT_PART_FILE = os.path.join(curdir, 'fat_img.zip')

FAT_PART_NAME = 'fat.img'

BLOCK_SIZE = 512
IDEPOSITBOX_MBR_SIG = 0x42445049 #IDPB
DATA_START_SEEK = 2050 * BLOCK_SIZE #start at 2050 sector 


class KSSignature:
    SIGN_STRUCT = '<6sI'
    SIGN_LEN = struct.calcsize(SIGN_STRUCT)
    SIGN_ID = 'OIFS01' #one item file system...

    @classmethod
    def dump(cls, ks_len):
        return struct.pack(cls.SIGN_STRUCT, cls.SIGN_ID, ks_len)

    def __init__(self, dumped=None):
        self.sign_id = None
        self.ks_len = None
        if dumped:
            self.load(dumped)

    def load(self, dumped):
        self.sign_id, self.ks_len = struct.unpack(self.SIGN_STRUCT, dumped)

    def is_valid(self):
        if self.sign_id == self.SIGN_ID and self.ks_len > 0:
            return True
        return False



class BlockDevice:
    def __init__(self, dev_path):
        self.__dev_path = dev_path
        self.is_linux = sys.platform.startswith('linux')

    def __pad_data(self, data):
        remaining_len = BLOCK_SIZE - len(data)
        to_pad_len = remaining_len % BLOCK_SIZE
        return data + '\x00'*to_pad_len
    
    def __bdm_call(self, *params):
        cmd_p = [SUID_BLOCKDEV_MGR]
        cmd_p.extend(params)
        proc = Subprocess(' '.join(cmd_p), shell=False)
        stdout_value, stderr_value = proc.communicate()
        if proc.returncode != 0:
            out = stdout_value
            if stderr_value:
                out += '\n%s'%stderr_value
            raise Exception(out)

    def format_device(self):
        logger.info('formatting device at %s'%self.__dev_path)
        if self.is_linux:
            self.__bdm_call(self.__dev_path, 'format')
        else:
            self.format()

    def format(self):
        self.check_removable()
        self.unmount_partitions()
        self.change_mbr()
        self.restore_fat_partition()
        self.unmount_partitions(force=True)

    def check_removable(self):
        ms = get_media_storage_manager()
        if not ms.is_removable(self.__dev_path):
            raise Exception('Device %s is not removable!'%self.__dev_path)

    def unmount_partitions(self, force=False):
        ms = get_media_storage_manager()
        ms.unmount_media_device(self.__dev_path, force=force)

    def __open_dev(self, read_only=False):
        flags = 'rb'
        if not read_only:
            flags += '+'
        try:
            return open(self.__dev_path, flags)
        except IOError:
            raise IOError('Device %s does not opened for %s!'%(self.__dev_path,\
                    'read' if read_only else 'write'))

    def int_read(self):
        fd = self.__open_dev(read_only=True)
        try:
            fd.seek(DATA_START_SEEK)
            data = fd.read(KSSignature.SIGN_LEN)
            sign = KSSignature(data)
            if not sign.is_valid():
                raise Exception('Key chain does not found at %s'%self.__dev_path)
            return fd.read(sign.ks_len)
        except IOError, err:
            logger.warning('KS device open error: %s'%err)
            raise IOError('Device %s can not be read!'%self.__dev_path)

    def write(self, data, file_path=None):
        if self.is_linux:
            tmp_file = None
            if file_path is None: 
                tmp_file = TempFile()
                tmp_file.write(data)
                tmp_file.flush()
                file_path = tmp_file.name
            try:
                self.__bdm_call(self.__dev_path, 'write', file_path)
            finally:
                if tmp_file:
                    tmp_file.close()
        else:
            if file_path:
                try:
                    data = open(file_path, 'rb').read()
                except IOError:
                    raise IOError('Can not read from "%s"'%file_path)
            self.int_write(data)


    def int_write(self, data):
        fd = self.__open_dev()
        try:
            fd.seek(DATA_START_SEEK)
            header_data = KSSignature.dump(len(data))
            data = self.__pad_data(header_data+data)
            fd.write(data)
        except IOError:
            raise IOError('Key chain does not write to device %s!'%self.__dev_path)
        finally:
            fd.close()

    def write_from_file(self, source_file):
        self.write(None, source_file)

    def read(self):
        if self.is_linux:
            tmp_file = TempFile()
            file_path = tmp_file.name
            try:
                self.__bdm_call(self.__dev_path, 'read', file_path)
                data = open(file_path, 'rb').read()
                return data
            finally:
                if tmp_file:
                    tmp_file.close()
        else:
            return self.int_read()
        
    def is_valid(self):
        try:
            data = self.read()
            if not data:
                return False
            return True
        except Exception, err:
            return False

    def read_mbr(self):
        fd = self.__open_dev(read_only=True)
        try:
            data = fd.read(512)
        except IOError, err:
            raise Exception('Can not read MBR from block device %s: %s'%(self.__dev_path, err))
        finally:
            fd.close()
        master_br = MBR()
        master_br.parse(data)
        return master_br

    def check_id_mbr(self):
        master_br = self.read_mbr()
        if master_br.disk_sig != IDEPOSITBOX_MBR_SIG:
            raise Exception('Device %s does not formatted as iDepositBox key chain!'%self.__dev_path)
    
    def change_mbr(self):
        master_br = self.read_mbr()
        if not master_br.check_mbr_sig():
            logger.info('No valid MBR found at device %s. Recreating it..'%self.__dev_path)
            master_br = MBR()

        master_br.disk_sig = IDEPOSITBOX_MBR_SIG
        part = master_br.partition_table.partitions[0]

        part.start_head = 0
        part.start_sector = 2
        part.start_cylinder = 0
        part.part_type = 0xDB
        part.end_head = 34
        part.end_sector = 32
        part.end_cylinder = 0
        part.LBA = 0x01
        part.num_sectors = 2049

        part = master_br.partition_table.partitions[1]
        part.start_head = 35
        part.start_sector = 63
        part.start_cylinder = 0
        part.part_type = 0xAB
        part.end_head = 97
        part.end_sector = 63
        part.end_cylinder = 0
        part.LBA = 2050
        part.num_sectors = 2049

        master_br.partition_table.partitions[2] = PartitionEntry()
        master_br.partition_table.partitions[3] = PartitionEntry()

        '''
        Disk: /dev/disk2geometry: 981/128/63 [7913472 sectors]
        Signature: 0xABA55
         Starting       Ending
          #: id  cyl  hd sec -  cyl  hd sec [     start -       size]
          ------------------------------------------------------------------------
           1: DB    0   0   2 -    0  34  32 [         1 -       2049] CPM/C.DOS/C*
           2: AB    0  35  63 -    0  97  63 [      2050 -       2049] Darwin Boot 
           3: 00    0   0   0 -    0   0   0 [         0 -          0] unused      
           4: 00    0   0   0 -    0   0   0 [         0 -          0] unused 
        '''

        logger.debug("Disk signature: 0x%08X" % (master_br.get_disk_sig()))
        #for partition in master_br.partition_table.partitions:
        #    print ""
        #    partition.print_partition() 

        new_mbr = master_br.generate()
        logger.info('MBR is updated at device %s'%self.__dev_path)
        try:
            open(self.__dev_path,'r+b').write(new_mbr)
        except IOError, err:
            raise Exception('Can not update MBR at block device: %s'%err)


    def restore_fat_partition(self):
        fd = open(self.__dev_path,'r+b')
        try:
            fd.seek(512)
            data = ZipFile(FAT_PART_FILE).read(FAT_PART_NAME)
            data = self.__pad_data(data)
            logger.debug('writing %s bytes of FAT partition...'%len(data))
            fd.write(data)
        except IOError, err:
            raise Exception('Can not restore FAT partition at block device: %s'%err)
        finally:
            fd.close()


