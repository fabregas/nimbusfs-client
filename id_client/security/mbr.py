#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.security.mbr
@author Konstantin Andrusenko
@date May 16, 2013
"""
import struct

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

