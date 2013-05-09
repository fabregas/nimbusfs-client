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

from id_client.constants import SPT_TOKEN_BASED, SPT_FILE_BASED

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
        st_list = [MediaStorage('HOME', home_path)]
        st_list += cls.get_removable_storages()
        for item in st_list:
            item.path = os.path.join(item.path, KS_PATH)

        return st_list

    @classmethod
    def get_removable_storages(cls):
        pass


class LinuxMediaStoragesManager(AbstractMediaStoragesManager):
    @classmethod
    def get_removable_storages(cls):
        mounted_map = {}
        st_list = []
        df_res = cmd_call('df')
        for line in df_res.splitlines():
            if line[0] != '/':
                continue
            parts = line.split()
            if parts[-1] in ('/', '/home'):
                continue
            dev = parts[0]
            if os.path.islink(dev):
                dev = os.path.join('/dev', os.readlink(dev))

            mounted_map[dev] = parts[-1]

        for dev in os.listdir('/sys/block/'):
            removable_flag = '/sys/block/%s/removable' % dev
            if not os.path.exists(removable_flag):
                continue
            if int(open(removable_flag).read()) == 0:
                continue

            for mdev in mounted_map:
                if dev in mdev:
                    st_list.append(MediaStorage(None, mounted_map[mdev]))
                    break
            #else:
            #    print 'found removable device %s but it does not mounted...'%dev

        return st_list


def get_media_storage_manager():
    if sys.platform.startswith('linux'):
        return LinuxMediaStoragesManager
    else:
        raise Exception('Unsupported platform "%s"!'%sys.platform)


