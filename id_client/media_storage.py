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

from id_client.constants import SPT_TOKEN_BASED, SPT_FILE_BASED, SPT_BLOCKDEV_BASED
from id_client.utils import Subprocess, logger

ALLOW_HOME_KS = False #ks in HOME is used for test purpose only
KS_PATH = os.path.join('iDepositBox', 'key.ks')

def cmd_call(cmd, err_msg=''):
    p = Subprocess(cmd)
    cout, cerr = p.communicate()
    if p.returncode != 0:
        cerr = ' '.join([cout, cerr])
        raise Exception('%s "%s" failed with message "%s"'%(err_msg, cmd, cerr))
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
        st_list = []
        if ALLOW_HOME_KS:
            home_path = os.path.expanduser('~')
            st_list += [MediaStorage('HOME - %s'%home_path, os.path.join(home_path, KS_PATH))]
        st_list += cls.get_removable_storages()
        return st_list

    @classmethod
    def get_removable_storages(cls):
        return []

    @classmethod
    def is_removable(self, device):
        return False

    @classmethod
    def unmount_media_device(cls, device, force=False):
        pass



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

    @classmethod
    def unmount_media_device(cls, device, force=False):
        import glob
        for partition in glob.glob('%s*'%device):
            if partition == device:
                continue
            os.system('mount | grep -q %s && umount %s'%(partition,partition))


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

    @classmethod
    def unmount_media_device(cls, device, force=False):
        cmd_call('diskutil unmountDisk %s'%device, \
                'Volumes at %s does not unmounted!'%device)


class WindowsMediaStoragesManager(AbstractMediaStoragesManager):
    @classmethod
    def is_removable(cls, device):
        rem_list = cls.get_removable_storages()
        for media_storage in rem_list:
            if media_storage.path == device:
                return True
        return False

    @classmethod
    def get_removable_storages(cls):
        st_list = []
        
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        strComputer = "."
        objWMIService = win32com.client.Dispatch("WbemScripting.SWbemLocator")
        objSWbemServices = objWMIService.ConnectServer(strComputer,"root\cimv2")
        colItems = objSWbemServices.ExecQuery("Select * from Win32_DiskDrive")
        for objItem in colItems:
            #logger.debug('detected disk drive: [%s] %s (%s)'%(str(objItem.Name), \
            #        str(objItem.Caption), str(objItem.MediaType)))

            if 'Removable' not in str(objItem.MediaType):
            #if 'Fixed hard disk media' not in str(objItem.MediaType):
                #print('media %s is not removable, skipping it...'%objItem.Name)
                continue
            st_list.append(MediaStorage(objItem.Caption, objItem.DeviceID, SPT_BLOCKDEV_BASED))
        return st_list

    @classmethod
    def unmount_media_device(cls, device, force=False):
        logic_drives = []

        #found logical drives on device
        import win32com.client
        import pythoncom
        import win32file
        import win32con
        import win32api
        pythoncom.CoInitialize()
        strComputer = "."
        objWMIService = win32com.client.Dispatch("WbemScripting.SWbemLocator")
        objSWbemServices = objWMIService.ConnectServer(strComputer,"root\cimv2")
        logger.debug('unmounting %s ... %s'%(device, type(device)))
        device_id = device.replace('\\', '\\\\')
        partitions= objSWbemServices.ExecQuery('ASSOCIATORS OF {Win32_DiskDrive.DeviceID="%s"} \
                WHERE AssocClass = Win32_DiskDriveToDiskPartition'%device_id)

        for part in partitions:
            logical_disks = objSWbemServices.ExecQuery('ASSOCIATORS OF \
                    {Win32_DiskPartition.DeviceID="%s"} \
                    WHERE AssocClass = Win32_LogicalDiskToPartition'%part.DeviceID)
            for logic in logical_disks:
                logic_drives.append(logic.DeviceID)

        #unmounting all logical drives
        FSCTL_DISMOUNT_VOLUME = 0x00090020
        for vol in logic_drives:
            if force:
                p = Subprocess('mountvol %s /d'%vol)
                out, err = p.communicate()
                if p.returncode:
                    logger.warning('"mountvol %s /d" failed with message: %s %s'%(vol, out, err))
                continue

            try:
                hh = win32file.CreateFile('\\\\.\\%s'%str(vol),  
                                     win32con.GENERIC_READ,
                                     win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                                     None,
                                     win32file.OPEN_EXISTING,
                                     win32file.FILE_ATTRIBUTE_NORMAL,
                                     None)
            except Exception, err:
                raise Exception('Volume %s does not opened: %s'%(vol, err))

            try:
                ret = win32file.DeviceIoControl(hh, FSCTL_DISMOUNT_VOLUME, None, None)
                if ret:
                    raise Exception('Volume %s does not unmounted! Error code: %s'%(str(vol), win32api.GetLastError()))
            finally:
                win32file.CloseHandle(hh)




def get_media_storage_manager():
    if sys.platform.startswith('linux'):
        return LinuxMediaStoragesManager
    elif sys.platform == 'darwin':
        return MacOsMediaStoragesManager
    elif sys.platform == 'win32':
        return WindowsMediaStoragesManager
    else:
        raise Exception('Unsupported platform "%s"!'%sys.platform)


