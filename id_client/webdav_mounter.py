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
from subprocess import Popen, PIPE

from nimbus_client.core.logger import logger

LINUX_MOUNTER_BIN = os.path.abspath(os.path.join(os.path.dirname(__file__), '../bin/webdav_mount'))

OS_MAC = 'mac'
OS_LINUX = 'linux'
OS_UNKNOWN = 'unknown'

class WebdavMounter:
    def __init__(self, nofork=False):
        system = sys.platform
        if system.startswith('linux'):
            self.cur_os = OS_LINUX
        elif system == 'darwin':
            self.cur_os = OS_MAC
        else:
            self.cur_os = OS_UNKNOWN
        self.nofork = nofork

    def __run_linux_mounter(self, cmd):
        proc = Popen([LINUX_MOUNTER_BIN, cmd], stdout=PIPE, stderr=PIPE)
        cout, cerr = proc.communicate()
        if proc.returncode:
            logger.error('webdav mounter error: %s %s'%(cout, cerr))
        return proc.returncode 

    def mount(self, host, port):
        if self.cur_os == OS_MAC:
            return self.mount_mac(host, port)
        elif self.cur_os == OS_LINUX:
            if not self.nofork:
                return self.__run_linux_mounter('mount')
            return self.mount_linux(host, port)

    def unmount(self):
        if self.cur_os == OS_LINUX:
            if not self.nofork:
                return self.__run_linux_mounter('umount')

        if self.cur_os in (OS_MAC, OS_LINUX):
            self.unmount_unix(self.get_mount_point())

    def mount_linux(self, bind_host, bind_port):
        mount_point = self.get_mount_point()
        if os.path.exists(mount_point):
            self.unmount_unix(mount_point)
        else:
            os.mkdir(mount_point)
        return os.system('mount.davfs2 http://%s:%s/ %s'\
                            % (bind_host, bind_port, mount_point))

    def get_mount_point(self):
        if self.cur_os == OS_MAC:
            return '/Volumes/iDepositBox'
        elif self.cur_os == OS_LINUX:
            return '/mnt/iDepositBox'
        else:
            raise Exception('unsupported OS')


    def mount_mac(self, bind_host, bind_port):
        mount_point = self.get_mount_point()
        if os.path.exists(mount_point):
            os.system('umount %s'%mount_point)
        else:
            os.mkdir(mount_point)

        if bind_host == '127.0.0.1':
            bind_host = 'localhost'
        return os.system('mount_webdav -v iDepositBox http://%s:%s/ %s'\
                            % (bind_host, bind_port, mount_point))


    def unmount_unix(self, mount_point):
        if os.path.exists(mount_point):
            os.system('umount %s'%mount_point)

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

