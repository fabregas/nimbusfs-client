
import os
import sys

OS_MAC = 'mac'
OS_LINUX = 'linux'
OS_UNKNOWN = 'unknown'

class WebdavMounter:
    def __init__(self):
        system = sys.platform
        if system.startswith('linux'):
            self.cur_os = OS_LINUX
        elif system == 'darwin':
            self.cur_os = OS_MAC
        else:
            self.cur_os = OS_UNKNOWN

    def mount(self, host, port):
        if self.cur_os == OS_MAC:
            return self.mount_mac(host, port)
        elif self.cur_os == OS_LINUX:
            return self.mount_linux(host, port)

    def unmount(self):
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

