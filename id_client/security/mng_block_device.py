#!/usr/bin/env python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.security.format_block_device
@author Konstantin Andrusenko
@date May 15, 2013

This script is used by rbd_manage command
for formatting removable block devices
"""

import sys
import os
from id_client.security.block_device import BlockDevice

def format_bd(device):
    block_dev = BlockDevice(device)
    block_dev.format()

def write_to_dev(device, s_path):
    if not os.path.exists(s_path):
        raise Exception('source path %s does not found!'%s_path)

    block_dev = BlockDevice(device)
    block_dev.check_id_mbr()
    try:
        data = open(s_path, 'rb').read()
    except IOError:
        raise IOError('Can not read from "%s"'%s_path)
    block_dev.int_write(data)

def read_from_dev(device, d_path):
    try:
        fd = open(d_path, 'wb')
    except IOError:
        raise Exception('permission denied to %s!'%d_path)
    try:
        block_dev = BlockDevice(device)
        block_dev.check_id_mbr()
        data = block_dev.int_read()
        fd.write(data)
    finally:
        fd.close()

def usage():
    sys.stderr.write('usage: rbd_manage <block device path> [format | write <path to source file> | read <path to dest file>]\n')
    sys.exit(1)

if __name__ == '__main__':
    #print 'uid=%s, gid=%s'%(os.getuid(), os.getgid())
    if len(sys.argv) < 3:
        usage()

    dev = sys.argv[1]
    if not os.path.exists(dev):
        sys.stderr.write('Device %s does not found!\n'%dev)
        sys.exit(1)

    cmd = sys.argv[2]
    try:
        if cmd == 'format':
            format_bd(dev)
            sys.stdout.write('Device %s was formatted successfully!\n'%dev)
        elif cmd == 'write':
            if len(sys.argv) != 4:
                usage()
            s_path = sys.argv[3]
            write_to_dev(dev, s_path)
            sys.stdout.write('Data was writed successfully to device!\n')
        elif cmd == 'read':
            if len(sys.argv) != 4:
                usage()
            d_path = sys.argv[3]
            read_from_dev(dev, d_path)
            sys.stdout.write('Data was read successfully from device!\n')
        else:
            raise Exception('Unknown command "%s"'%cmd)
    except Exception, err:
        sys.stderr.write('Error: %s\n'%err)
        sys.exit(1)

    sys.exit(0)
