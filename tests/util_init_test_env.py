import os
import sys
import shutil
import tempfile
import logging

from nimbus_client.core.logger import logger

logger.setLevel(logging.DEBUG)

def tmp(fname):
    return os.path.join(tempfile.gettempdir(), fname)


def remove_dir(dir_path):
    if not os.path.exists(dir_path):
        return
    shutil.rmtree(dir_path)

if sys.platform == 'win32' and 'OPENSSL_EXEC' not in os.environ:
    os.environ['OPENSSL_EXEC'] = './third-party/OpenSSL/bin/openssl.exe'
