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

from id_client.media_storage import get_media_storage_manager

logger = logging.getLogger('fabnet-client')
curdir = os.path.abspath(os.path.dirname(__file__))
SUID_DEVICE_FORMATTER = os.path.join(curdir, 'rbd_format')
FAT_PART_FILE = os.path.join(curdir, 'fat_img.zip')
FAT_PART_NAME = 'fat.img'

DATA_START_SEEK = 2050 * 512 #start at 2050 sector 

def read_ub(data):
    # Read an unsigned byte from data block
    return struct.unpack('B', data[0])[0]
  
def read_us(data):
    # Read an unsigned short int (2 bytes) from data block    
    return struct.unpack('<H', data[0:2])[0]

def read_ui(data):
    # Read an unsigned int (4 bytes) from data block    
    return struct.unpack('<I', data[0:4])[0]

class PartitionEntry:
    def __init__(self):
        self.status = 0x00
        self.start_head = 0x00
        self.start_sector = 0x00
        self.start_cylinder = 0x00
        self.part_type = 0x00
        self.end_head = 0x00
        self.end_sector = 0x00
        self.end_cylinder = 0x00
        self.LBA = 0x00
        self.num_sectors = 0x00

    def generate(self):
        start_sc_spl = ((self.start_sector & 0x3F) | ((self.start_cylinder >> 2) & 0xC0)) | ((self.start_cylinder & 0xFF) << 8)
        ebs_sc_spl = ((self.end_sector & 0x3F) | ((self.end_cylinder >> 2) & 0xC0)) | ((self.end_cylinder & 0xFF) << 8)

        return struct.pack('<BBHBBHII', self.status, self.start_head, start_sc_spl, self.part_type,
                self.end_head, ebs_sc_spl, self.LBA, self.num_sectors)

    def parse(self, data):
        self.status = read_ub(data)
        self.start_head = read_ub(data[1])
        tmp = read_ub(data[2])
        self.start_sector = tmp & 0x3F
        self.start_cylinder = (((tmp & 0xC0)>>6)<<8) + read_ub(data[3])
        self.part_type = read_ub(data[4])
        self.end_head = read_ub(data[5])
        tmp = read_ub(data[6])
        self.end_sector = tmp & 0x3F
        self.end_cylinder = (((tmp & 0xC0)>>6)<<8) + read_ub(data[7])
        self.LBA = read_ui(data[8:12])
        self.num_sectors = read_ui(data[12:16])    
    
    def print_partition(self):
        self.check_status()
        print "CHS of first sector: %d %d %d" % \
            (self.start_cylinder, self.start_head, self.start_sector)
        print "Part type: 0x%02X" % self.part_type
        print "CHS of last sector: %d %d %d" % \
            (self.end_cylinder, self.end_head, self.end_sector)
        print "LBA of first absolute sector: %d" % (self.LBA)
        print "Number of sectors in partition: %d" % (self.num_sectors)
                
    def check_status(self):
        if (self.status == 0x00):
            print 'Non bootable'
        else:
            if (self.status == 0x80):
                print 'Bootable'
            else: 
                print 'Invalid bootable byte'
        
# Table of four primary partitions        
class PartitionTable:
    def __init__(self):
        self.partitions = [PartitionEntry() for i in range (0, 4)]

    def parse(self, data):
        for i in range(0, 4):
            self.partitions[i].parse(data[16*i:16*(i+1)])

    def generate(self):
        return struct.pack('<16s16s16s16s', *[p.generate() for p in self.partitions])


# Master Boot Record        
class MBR:
    def __init__(self):
        self.boot_code = '\x00'*440
        self.disk_sig = 0x0A0CFF09
        self.partition_table = PartitionTable()
        self.MBR_sig = 0xAA55

    def generate(self):
        return struct.pack('<440sIH64sH', self.boot_code, self.disk_sig, 0, self.partition_table.generate(), self.MBR_sig)

    def parse(self, data):
        self.boot_code = data[:440]        
        self.disk_sig = read_ui(data[440:444])
        unused = data[444:446]        
        self.partition_table.parse(data[446:510])        
        self.MBR_sig = read_us(data[510:512])
        
    def check_mbr_sig(self):
        mbr_sig = self.MBR_sig
        if (mbr_sig == 0xAA55):
            return True
        else:
            return False
            
    def get_disk_sig(self):        
        return self.disk_sig      
                      

class BlockDevice:
    MAC_OS = 'mac'
    LINUX = 'linux'

    cur_os = None

    @classmethod
    def get_current_os(cls):
        if cls.cur_os:
            return cls.cur_os
        
        if sys.platform.startswith('linux'):
            cls.cur_os = cls.LINUX
        elif sys.platform == 'darwin':
            cls.cur_os = cls.MAC_OS
        return cls.cur_os


    @classmethod
    def format_device(cls, device_path):
        cur_os = cls.get_current_os()
        if cur_os == cls.MAC_OS:
            block_dev = BlockDevice(device_path)
            block_dev.format()
        elif cur_os == cls.LINUX: 
            proc = Popen([SUID_DEVICE_FORMATTER, device_path], shell=False, stdin=PIPE, stdout=PIPE)
            stdout_value, stderr_value = proc.communicate(stdin)
            if proc.returncode != 0:
                out = stdout_value
                if stderr_value:
                    out += '\n%s'%stderr_value
                raise Exception(out)

    def __init__(self, dev_path):
        self.__dev_path = dev_path

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
        cur_os = self.get_current_os()
        if cur_os == self.MAC_OS:
            ret = os.system('diskutil unmountDisk %s'%self.__dev_path)
            if ret:
                raise Exception('Volumes at %s does not unmounted!'%self.__dev_path)
        elif cur_os == self.LINUX:
            import glob
            for partition in glob.glob('%s*'%self.__dev_path):
                ret = os.system('umount %s'%partition)
                if ret:
                    logger.error('Can not unmount %s...'%partition)

    def change_mbr(self):
        try:
            data = open(self.__dev_path, 'rb').read(512)
        except IOError, err:
            raise Exception('Can not read MBR from block device %s: %s'%(self.__dev_path, err))

        master_br = MBR()
        master_br.parse(data)
        if not master_br.check_mbr_sig():
            logger.info('No valid MBR found at device %s. Recreating it..'%self.__dev_path)
            master_br = MBR()
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


