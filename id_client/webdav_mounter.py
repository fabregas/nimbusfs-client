#!/usr/bin/env python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.webdav_mounter
@author Konstantin Andrusenko
@date May 08, 2013
"""

import os
import sys
import string
from id_client.utils import Subprocess

from nimbus_client.core.logger import logger

LINUX_MOUNTER_BIN = os.path.abspath(os.path.join(os.path.dirname(__file__), '../bin/webdav_mount'))

#-------- for win32 ----------
ALL_DRIVES_LIST = list(string.ascii_uppercase)
ALL_DRIVES_LIST.reverse() #for win32
#-----------------------------

OS_MAC = 'mac'
OS_LINUX = 'linux'
OS_WINDOWS = 'windows'
OS_UNKNOWN = 'unknown'

class WebdavMounter:
    def __init__(self, nofork=False):
        system = sys.platform
        if system.startswith('linux'):
            self.cur_os = OS_LINUX
        elif system == 'darwin':
            self.cur_os = OS_MAC
        elif system == 'win32':
            self.cur_os = OS_WINDOWS
        else:
            self.cur_os = OS_UNKNOWN
        self.nofork = nofork
        self.__mountpoint = ''

    def get_mount_point(self):
        return self.__mountpoint

    def __run_linux_mounter(self, cmd):
        proc = Subprocess('%s %s'%(LINUX_MOUNTER_BIN, cmd))
        cout, cerr = proc.communicate()
        if proc.returncode:
            logger.error('webdav mounter error: %s %s'%(cout, cerr))
        return proc.returncode 

    def mount(self, host, port):
        if self.cur_os == OS_MAC:
            return self.mount_mac(host, port)
        elif self.cur_os == OS_LINUX:
            try:
                if not self.nofork:
                    return self.__run_linux_mounter('mount')
                return self.mount_linux(host, port)
            finally:
                self.__update_linux_mountpoint('%s:%s'%(host, port))
        elif self.cur_os == OS_WINDOWS:
            self.mount_windows(host, port)

    def unmount(self):
        try:
            if self.cur_os == OS_LINUX:
                if not self.nofork:
                    return self.__run_linux_mounter('umount')

            if self.cur_os in (OS_MAC, OS_LINUX):
                self.unmount_unix(self.get_mount_point())
            elif self.cur_os == OS_WINDOWS:
                self.umount_windows()
        finally:
            self.__mountpoint = ''


    def __update_linux_mountpoint(self, url):
        p = Subprocess('df') 
        out, err = p.communicate()
        for line in out.splitlines():
            if url in line:
                self.__mountpoint = line.split()[-1]
                return

    def mount_linux(self, bind_host, bind_port):
        mount_point = '/media/iDepositBox'
        if os.path.exists(mount_point):
            self.unmount_unix(mount_point)
        else:
            os.makedirs(mount_point)

        p = Subprocess('mount -t davfs -o rw,user,dir_mode=0777 http://%s:%s/ %s'\
                % (bind_host, bind_port, mount_point), with_input=True)
        out, err = p.communicate('anonymous\nanonymous')
        if p.returncode:
            sys.stderr.write('%s\n'%err)
        return p.returncode

    def mount_mac(self, bind_host, bind_port):
        self.__mountpoint = mount_point = '/Volumes/iDepositBox'
        if os.path.exists(mount_point):
            os.system('umount %s'%mount_point)
        else:
            os.mkdir(mount_point)

        if bind_host == '127.0.0.1':
            bind_host = 'localhost'
        return os.system('mount_webdav -v iDepositBox http://%s:%s/ %s'\
                            % (bind_host, bind_port, mount_point))


    def __get_win_unused_drive(self):
        import win32api
        drives = win32api.GetLogicalDriveStrings()
        drives = drives.split('\000')
        a_drives = []
        for s in drives:
            s = s.strip()
            if s: a_drives.append(s[0])
        for drive in ALL_DRIVES_LIST:
            if drive in a_drives:
                continue
            return '%s:'%drive

    def mount_windows(self, host, port):
        self.umount_windows()
        drive = self.__get_win_unused_drive()
        self.__mountpoint = 'drive %s'%drive
        p = Subprocess(['sc', 'create', 'iDepositBoxMount', 'binPath=', 'cmd /b /c net use %s http://%s:%s/'%\
                (drive, host, port), 'type=', 'share'])

        p = Subprocess(['sc', 'create', 'iDepositBoxUnmount', 'binPath=', 'cmd /b /c net use /delete %s /Y'%\
                drive, 'type=', 'share'])
        out, err = p.communicate()
        logger.debug('sc create iDepositBoxUnmount: [%s] %s %s'%(p.returncode, out, err))
        
        p = Subprocess('net start iDepositBoxMount')
        p.communicate()    
        return 0

    def umount_windows(self):
        p = Subprocess('sc query iDepositBoxUnmount')
        out, err = p.communicate()
        if p.returncode:
            logger.debug('no iDepositBoxUnmount service found...')
            return

        p = Subprocess('net start iDepositBoxUnmount')
        p.communicate()

        p = Subprocess('sc delete iDepositBoxMount')
        out, err = p.communicate()
        logger.debug('sc delete iDepositBoxMount: %s %s'%(out, err))

        p = Subprocess('sc delete iDepositBoxUnmount')
        out, err = p.communicate()
        logger.debug('sc delete iDepositBoxUnmount: %s %s'%(out, err))


    def unmount_unix(self, mount_point):
        if os.path.exists(mount_point):
            p = Subprocess('umount %s'%mount_point)
            p.communicate()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.stderr.write('usage: webdav_mount mount|umount\n')
        sys.exit(1)

    from id_client.config import Config
    wdm = WebdavMounter(nofork=True)
    config = Config()
    cmd = sys.argv[1]
    if cmd == 'mount':
        err = ''
        try:
            ret_code = wdm.mount('127.0.0.1', config.webdav_bind_port)
        except Exception, err:
            ret_code = 1
        if ret_code:
            sys.stderr.write('Webdav does not mounted locally! %s\n'%err)
            sys.exit(1)
    elif cmd == 'umount':
        wdm.unmount()
    else:
        sys.stderr.write('unknown command "%s"!\n'%cmd)
        sys.exit(1)

    sys.stdout.write('ok\n')
    sys.exit(0)

