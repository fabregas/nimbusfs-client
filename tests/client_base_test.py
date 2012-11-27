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
from nimbus_client.core.logger import logger

logger.setLevel(logging.WARNING)
from nimbus_client.core import constants
constants.CHUNK_SIZE = 100000

from nimbus_client.core.nibbler import Nibbler
from nimbus_client.core.security_manager import init_security_manager
from nimbus_client.core.exceptions import *

DEBUG=False

CLIENT_KS_PATH = './tests/cert/test_client_ks.zip'
VALID_STORAGE = './tests/cert/test_keystorage.zip'
PASSWD = 'qwerty123'

TMP_FILE = '/tmp/test_file.out'

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

        time.sleep(0.1)
        return primary_key, source_checksum

    def get(self, primary_key, replica_count=2):
        logger.info('MockedFabnetGateway.get: key=%s replica_count=%s'%(primary_key, replica_count))
        time.sleep(0.1)

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

        with self.assertRaises(PathException):
            nibbler.mkdir('/this/is/not/exists/path')

        with self.assertRaises(AlreadyExistsException):
            nibbler.mkdir('/my_first_dir')

        nibbler.mkdir('/my_third_dir/subdir01/subdir02', recursive=True)


    def test03_save_file(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST
        fb = open(TMP_FILE, 'wb')
        data = ''.join(random.choice(string.letters) for i in xrange(1024))
        data *= 5*1024
        fb.write(data)
        fb.close()
        checksum = hashlib.sha1(data).hexdigest()

        def callback(error):
            self.assertEqual(error, None)

        with self.assertRaises(LocalPathException):
            nibbler.save_file('/some/dir/file.fake', 'test_file.out', '/my_first_dir/my_first_subdir')

        with self.assertRaises(PathException):
            nibbler.save_file(TMP_FILE, 'test_file.out', '/bad/path')

        op_id = nibbler.save_file(TMP_FILE, 'test_file.out', '/my_first_dir/my_first_subdir')
        self.assertNotEqual(op_id, None)
        with self.assertRaises(TimeoutException):
            nibbler.wait_async_operation(op_id, 1)
        nibbler.wait_async_operation(op_id, 20)

        with self.assertRaises(AlreadyExistsException):
            nibbler.save_file(TMP_FILE, 'test_file.out', '/my_first_dir/my_first_subdir')

        with self.assertRaises(NotDirectoryException):
            nibbler.save_file(TMP_FILE, 'test_file_copy.out', '/my_first_dir/my_first_subdir/test_file.out')

        op_id = nibbler.save_file(TMP_FILE, 'test_file_copy.out', '/my_first_dir/my_first_subdir', callback)
        nibbler.wait_async_operation(op_id, 20)

        fs_item = nibbler.find('/my_first_dir/my_first_subdir/test_file.out')
        self.assertNotEqual(fs_item, None)
        self.assertEqual(fs_item.name, 'test_file.out')
        self.assertEqual(fs_item.is_dir, False)
        self.assertEqual(fs_item.is_file, True)

        #get file
        op_id = nibbler.load_file('/my_first_dir/my_first_subdir/test_file.out', TMP_FILE, callback)
        self.assertNotEqual(op_id, None)
        nibbler.wait_async_operation(op_id, 20)
        sha1 = hashlib.sha1()
        sha1.update(open(TMP_FILE, 'rb').read())
        os.remove(TMP_FILE)

        self.assertEqual(sha1.hexdigest(), checksum)

    def test05_listdir(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST
        items = nibbler.listdir()
        self.assertEqual(len(items), 3, items)
        self.assertEqual(items[0].name, 'my_first_dir')
        self.assertEqual(items[0].is_dir, True)
        self.assertEqual(items[1].name, 'my_second_dir')
        self.assertEqual(items[1].is_dir, True)
        self.assertEqual(items[2].name, 'my_third_dir')
        self.assertEqual(items[2].is_dir, True)

        items = nibbler.listdir('/my_first_dir/my_first_subdir')
        self.assertEqual(len(items), 2, items)
        self.assertEqual(items[0].name, 'test_file.out')
        self.assertEqual(items[0].is_file, True)
        self.assertEqual(items[1].name, 'test_file_copy.out')
        self.assertEqual(items[1].is_file, True)

        with self.assertRaises(PathException):
            nibbler.listdir('/some/imagine/path')

    '''
    def test06_versions(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST
        versions = nibbler.get_versions()
        self.assertEqual(len(versions), 4)

        nibbler.load_version(versions[0][1])
        items = nibbler.listdir('/')
        self.assertEqual(len(items), 1, items)
        self.assertEqual(items[0], ('my_first_dir', False))

        nibbler.load_version(versions[-1][1])
    '''


    def test07_remove_file(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST

        nibbler.remove_file('/my_first_dir/my_first_subdir/test_file.out')
        with self.assertRaises(PathException):
            nibbler.remove_file('/my_first_dir/my_first_subdir/test_file.out')
        items = nibbler.listdir('/my_first_dir/my_first_subdir')
        self.assertEqual(len(items), 1, items)


    def test08_rmdir(self):
        nibbler = TestDHTInitProcedure.NIBBLER_INST
        with self.assertRaises(PathException):
            nibbler.rmdir('/some/imagine/path')
        with self.assertRaises(NotEmptyException):
            nibbler.rmdir('/my_first_dir')
        with self.assertRaises(NotDirectoryException):
            nibbler.rmdir('/my_first_dir/my_first_subdir/test_file_copy.out')

        nibbler.rmdir('/my_first_dir', recursive=True)
        items = nibbler.listdir()
        self.assertEqual(len(items), 2, items)
        self.assertEqual(items[0].name, 'my_second_dir')



if __name__ == '__main__':
    unittest.main()

