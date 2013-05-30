#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.utils
@author Konstantin Andrusenko
@date March 20, 2013
"""
import os
import sys
import tempfile

def to_str(val):
    if type(val) == unicode:
        return val.encode('utf8')
    return val

def to_nimbus_path(path):
    path = to_str(path)
    if os.sep != '/':
        return path.replace(os.sep, '/')
    return path

class TempFile:
    def __init__(self):
        self.__fd = None
        self.__path = None
        fd, self.__path = tempfile.mkstemp('-nimbusfs')
        self.__fd = os.fdopen(fd, 'wb')

    @property
    def name(self):
        return self.__path

    def write(self, data):
        self.__fd.write(data)

    def flush(self):
        self.__fd.flush()

    def close(self):
        if self.__fd:
            self.__fd.close()
            self.__fd = None
        if self.__path:
            os.remove(self.__path)
            self.__path = None

    def __del__(self):
        self.close()


def is_windows_os():
    return sys.platform == 'win32'

if is_windows_os():
    def get_free_space(folder):
        import ctypes
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value
else:
    def get_free_space(folder):
        st = os.statvfs(folder)
        return st.f_bavail * st.f_frsize
