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
from subprocess import Popen, PIPE
from zipfile import ZipFile

from nimbus_client.core.utils import TempFile
from id_client.media_storage import get_media_storage_manager
from id_client.security.mbr import *

logger = logging.getLogger('fabnet-client')
if not logger.handlers:
    console = logging.StreamHandler()
    logger.addHandler(console)

curdir = os.path.abspath(os.path.dirname(__file__))
SUID_BLOCKDEV_MGR = os.path.join(curdir, '../../bin/rbd_manage')
FAT_PART_FILE = os.path.join(curdir, 'fat_img.zip')
FAT_PART_NAME = 'fat.img'

IDEPOSITBOX_MBR_SIG = 0x42445049 #IDPB
DATA_START_SEEK = 2050 * 512 #start at 2050 sector 
                      

class KSSignature:
    SIGN_STRUCT = '<6sI'
    SIGN_LEN = struct.calcsize(SIGN_STRUCT)
    SING_ID = 'OIFS01' #one item file system...

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



class BlockDevice:
    MAC_OS = 'mac'
    LINUX = 'linux'

    def __init__(self, dev_path):
        self.__dev_path = dev_path
        self.cur_os = None
    
        if sys.platform.startswith('linux'):
            self.cur_os = self.LINUX
        elif sys.platform == 'darwin':
            self.cur_os = self.MAC_OS

    def __bdm_call(self, *params):
        cmd_p = [SUID_BLOCKDEV_MGR]
        cmd_p.extend(params)
        proc = Popen(cmd_p, shell=False, stdin=PIPE, stdout=PIPE)
        stdout_value, stderr_value = proc.communicate()
        if proc.returncode != 0:
            out = stdout_value
            if stderr_value:
                out += '\n%s'%stderr_value
            raise Exception(out)

    def format_device(self):
        if self.cur_os == self.MAC_OS:
            self.format()
        elif self.cur_os == self.LINUX: 
            self.__bdm_call(self.__dev_path, 'format')

    def format(self):
        self.check_removable()
        self.unmount_partitions()
        self.change_mbr()
        self.restore_fat_partition()

    def check_removable(self):
        ms = get_media_storage_manager()
        if not ms.is_removable(self.__dev_path):
            raise Exception('Device %s is not removable!'%self.__dev_path)

    def unmount_partitions(self):
        if self.cur_os == self.MAC_OS:
            ret = os.system('diskutil unmountDisk %s'%self.__dev_path)
            if ret:
                raise Exception('Volumes at %s does not unmounted!'%self.__dev_path)
        elif self.cur_os == self.LINUX:
            import glob
            for partition in glob.glob('%s*'%self.__dev_path):
                if partition == self.__dev_path:
                    continue
                ret = os.system('mount | grep -q %s && umount %s'%(partition,partition))
                if ret:
                    logger.debug('Can not unmount %s...'%partition)

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
        except IOError:
            raise IOError('Device %s can not be read!'%self.__dev_path)

    def write(self, data, file_path=None):
        if self.cur_os == self.MAC_OS:
            if file_path:
                try:
                    data = open(file_path, 'rb').read()
                except IOError:
                    raise IOError('Can not read from "%s"'%file_path)
            self.int_write(data)
        elif self.cur_os == self.LINUX:
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

    def int_write(self, data):
        fd = self.__open_dev()
        try:
            fd.seek(DATA_START_SEEK)
            fd.write(KSSignature.dump(len(data)))
            fd.write(data)
        except IOError:
            raise IOError('Key chain does not write to device %s!'%self.__dev_path)
        finally:
            fd.close()

    def write_from_file(self, source_file):
        self.write(None, source_file)

    def read(self):
        if self.cur_os == self.MAC_OS:
            return self.int_read()
        elif self.cur_os == self.LINUX:
            tmp_file = TempFile()
            file_path = tmp_file.name
            try:
                self.__bdm_call(self.__dev_path, 'read', file_path)
                data = open(file_path, 'rb').read()
                return data
            finally:
                if tmp_file:
                    tmp_file.close()
        
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
            fd.write(ZipFile(FAT_PART_FILE).read(FAT_PART_NAME))
        except IOError, err:
            raise Exception('Can not restore FAT partition at block device: %s'%err)
        finally:
            fd.close()


