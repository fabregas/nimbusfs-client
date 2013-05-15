#!/usr/bin/env python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.security.format_block_device
@author Konstantin Andrusenko
@date May 15, 2013

This script is used by rbd_format command
for formatting removable block devices
"""

import sys
import os
from id_client.security.block_device import BlockDevice

def format_bd(device):
    block_dev = BlockDevice(device)
    block_dev.format()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.stderr.write('usage: rbd_format <block device path>\n')
        sys.exit(1)

    try:
        format_bd(sys.argv[1])
    except Exception, err:
        sys.stderr.write('Error: %s\n'%err)
        sys.exit(1)

    sys.stderr.write('Device %s was formatted successfully!\n'%sys.argv[1])
    sys.exit(0)
