
import os
import platform

from id_client.config import Config

OS_MAC = 'mac'
OS_UNKNOWN = 'unknown'

class WebdavMounter:
    def __init__(self):
        system = platform.system()
        if system == 'Darwin':
            self.cur_os = OS_MAC
        else:
            self.cur_os = OS_UNKNOWN

    def mount(self):
        config = Config()
        if self.cur_os == OS_MAC:
            return self.mount_mac(config.webdav_bind_host, config.webdav_bind_port)
            ret = os.system('')

    def unmount(self):
        if self.cur_os == OS_MAC:
            return self.unmount_mac()

    def mount_mac(self, bind_host, bind_port):
        mount_point = '/Volumes/iDepositBox'
        if os.path.exists(mount_point):
            os.system('umount %s'%mount_point)
        else:
            os.mkdir(mount_point)

        if bind_host == '127.0.0.1':
            bind_host = 'localhost'
        return os.system('mount_webdav -v iDepositBox http://%s:%s/ %s'\
                            % (bind_host, bind_port, mount_point))


    def unmount_mac(self):
        mount_point = '/Volumes/iDepositBox'
        if os.path.exists(mount_point):
            os.system('umount %s'%mount_point)

