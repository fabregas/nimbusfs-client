#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.media_storage
@author Konstantin Andrusenko
@date May 08, 2013
"""
import os
import sys
import subprocess

from id_client.constants import SPT_TOKEN_BASED, SPT_FILE_BASED, SPT_BLOCKDEV_BASED

KS_PATH = 'iDepositBox/key.ks'

def cmd_call(cmd):
    p = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cout, cerr = p.communicate()
    if p.returncode != 0:
        raise Exception('"%s" failed! Details: %s'%(cmd, cerr))
    return cout

class MediaStorage:
    def __init__(self, label, path, ks_type=SPT_FILE_BASED):
        self.label = label
        self.ks_type = ks_type
        self.path = path

class AbstractMediaStoragesManager:
    @classmethod
    def get_available_storages(cls):
        '''return list of available storages for saving
            key chain (objects of MediaStorage)
        '''
        home_path = os.path.expanduser('~')
        st_list = [MediaStorage('HOME - %s'%home_path, os.path.join(home_path, KS_PATH))]
        st_list += cls.get_removable_storages()
        return st_list

    @classmethod
    def get_removable_storages(cls):
        return []

    @classmethod
    def is_removable(self, device):
        return False

class LinuxMediaStoragesManager(AbstractMediaStoragesManager):
    @classmethod
    def is_removable(self, device):
        dev = device.split('/')[-1]
        removable_flag = '/sys/block/%s/removable' % dev
        dev_type_fp = '/sys/block/%s/device/type' % dev
        if not os.path.exists(removable_flag):
            return False
        if int(open(removable_flag).read()) == 0:
            return False
        if not os.path.exists(dev_type_fp):
            return False
        if int(open(dev_type_fp).read()) != 0: #TYPE_DISK, include/scsi/scsi.h 
            return False
        return True

    @classmethod
    def get_device_label(self, device):
        dev = device.split('/')[-1]
        vendor_fp = '/sys/block/%s/device/vendor' % dev
        model_fp = '/sys/block/%s/device/model' % dev
        if not (os.path.exists(model_fp) and os.path.exists(vendor_fp)):
            return 'unknown device /dev/%s'%dev
        return '%s %s (/dev/%s)'%(open(vendor_fp).read(), open(model_fp).read(), dev)

    @classmethod
    def get_removable_storages(cls):
        st_list = []
        for dev in os.listdir('/sys/block/'):
            if not cls.is_removable(dev):
                continue
            label = cls.get_device_label(dev)
            st_list.append(MediaStorage(label, '/dev/%s'%dev, SPT_BLOCKDEV_BASED))
        return st_list

class MacOsMediaStoragesManager(AbstractMediaStoragesManager):
    @classmethod
    def is_removable(self, device):
        dev = device.split('/')[-1]
        res = cmd_call('diskutil info %s'%dev)
        vol_name = None
        for line in res.splitlines():
            line = line.strip()
            if not line.startswith('Ejectable:'):
                continue
            if 'No' in line:
                return False
            return True

    @classmethod
    def get_device_label(self, device):
        dev = device.split('/')[-1]
        res = cmd_call('diskutil info %s'%dev)
        for line in res.splitlines():
            line = line.strip()
            if 'Media Name:' in line:
                return '%s (/dev/%s)'%(line.split('Media Name:')[-1].strip(), dev)

    @classmethod
    def get_removable_storages(cls):
        st_list = []
        res = cmd_call('diskutil list')
        for line in res.splitlines():
            line = line.strip()
            if not line.startswith('/dev'):
                continue
            device = line
            if not cls.is_removable(device):
                continue
            st_list.append(MediaStorage(cls.get_device_label(device), device, SPT_BLOCKDEV_BASED))
        return st_list

class WindowsMediaStoragesManager(AbstractMediaStoragesManager):
    #FIXME: implement me...
    pass

def get_media_storage_manager():
    if sys.platform.startswith('linux'):
        return LinuxMediaStoragesManager
    elif sys.platform == 'darwin':
        return MacOsMediaStoragesManager
    elif sys.platform == 'win32':
        return WindowsMediaStoragesManager
    else:
        raise Exception('Unsupported platform "%s"!'%sys.platform)


