import unittest
import time
import os
import logging
import shutil
import threading
import json
import random
import subprocess
import signal
import string
import hashlib
from datetime import datetime
from id_client.core.logger import logger

logger.setLevel(logging.DEBUG)
from id_client.core import constants
constants.CHUNK_SIZE = 100000

from id_client.core.nibbler import Nibbler
from id_client.core.security_manager import init_security_manager

DEBUG=False

CLIENT_KS_PATH = './tests/cert/test_client_ks.zip'
VALID_STORAGE = './tests/cert/test_keystorage.zip'
PASSWD = 'qwerty123'

class MockedFabnetGateway:
    def __init__(self):
        self.data_map = {}

    def put(self, data, key=None, replica_count=2, wait_writes_count=2):
        logger.info('MockedFabnetGateway.put: key=%s replica_count=%s wait_writes_count=%s'%(key, replica_count, wait_writes_count))

        if key:
            primary_key = key
        else:
            primary_key = hashlib.sha1(datetime.utcnow().isoformat()).hexdigest()
        source_checksum = hashlib.sha1(data).hexdigest()

        self.data_map[primary_key] = data
        return primary_key, source_checksum

    def get(self, primary_key, replica_count=2):
        logger.info('MockedFabnetGateway.get: key=%s replica_count=%s'%(primary_key, replica_count))
        raise Exception('somebody failed')

        return self.data_map.get(primary_key, None)

class TestDHTInitProcedure(unittest.TestCase):
    NIBBLER_INST = None

    def test01_dht_init(self):
        security_manager = init_security_manager(constants.SPT_FILE_BASED, CLIENT_KS_PATH, PASSWD)
        nibbler = Nibbler('127.0.0.1', security_manager)
        mocked = MockedFabnetGateway()
        nibbler.fabnet_gateway.put = mocked.put
        nibbler.fabnet_gateway.get = mocked.get
        TestDHTInitProcedure.NIBBLER_INST = nibbler

        nibbler.register_user()

    def test99_dht_stop(self):
        TestDHTInitProcedure.NIBBLER_INST.stop()
        time.sleep(1)

    def test02_create_dir(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST
        nibbler.mkdir('/my_first_dir')
        nibbler.mkdir('/my_second_dir')
        nibbler.mkdir('/my_first_dir/my_first_subdir')

        try:
            nibbler.mkdir('/my_first_dir')
        except Exception, err:
            pass
        else:
            raise Exception('should be exception in this case')

    def test03_save_file(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST
        fb = open('/tmp/test_file.out', 'wb')
        data = ''.join(random.choice(string.letters) for i in xrange(1024))
        data *= 2*1024
        fb.write(data)
        fb.close()
        checksum = hashlib.sha1(data).hexdigest()

        nibbler.save_file('/tmp/test_file.out', 'test_file.out', '/my_first_dir/my_first_subdir')

        for i in xrange(20):
            time.sleep(1)
            if nibbler.get_resource('/my_first_dir/my_first_subdir/test_file.out'):
                break
        else:
            raise Exception('File does not uploaded!')

        os.remove('/tmp/test_file.out')

        #get file
        file_iterator = nibbler.load_file('/my_first_dir/my_first_subdir/test_file.out')
        sha1 = hashlib.sha1()
        for data in file_iterator:
            sha1.update(data)
        file_iterator.close()

        self.assertEqual(sha1.hexdigest(), checksum)

    def test05_listdir(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST
        items = nibbler.listdir()
        self.assertEqual(len(items), 2, items)
        self.assertEqual(items[0], ('my_first_dir', False))
        self.assertEqual(items[1], ('my_second_dir', False))

        items = nibbler.listdir('/my_first_dir/my_first_subdir')
        self.assertEqual(len(items), 1, items)
        self.assertEqual(items[0], ('test_file.out', True))

    def test06_versions(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST
        versions = nibbler.get_versions()
        self.assertEqual(len(versions), 4)

        nibbler.load_version(versions[0][1])
        items = nibbler.listdir('/')
        self.assertEqual(len(items), 1, items)
        self.assertEqual(items[0], ('my_first_dir', False))

        nibbler.load_version(versions[-1][1])


    def test07_remove_file(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST

        nibbler.remove_file('/my_first_dir/my_first_subdir/test_file.out')
        items = nibbler.listdir('/my_first_dir/my_first_subdir')
        self.assertEqual(len(items), 0, items)


    def test08_rmdir(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST
        try:
            nibbler.rmdir('/my_first_dir')
        except Exception, err:
            pass
        else:
            raise Exception('should be exception in this case')

        nibbler.rmdir('/my_first_dir', recursive=True)
        items = nibbler.listdir()
        self.assertEqual(len(items), 1, items)
        self.assertEqual(items[0], ('my_second_dir', False))



if __name__ == '__main__':
    unittest.main()

