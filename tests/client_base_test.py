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
from nimbus_client.core.fri.fri_base import FabnetPacketResponse

logger.setLevel(logging.WARNING)
from nimbus_client.core import constants
constants.CHUNK_SIZE = 100000

from nimbus_client.core.nibbler import Nibbler
from nimbus_client.core.security_manager import FileBasedSecurityManager
from nimbus_client.core.exceptions import *

DEBUG=False

CLIENT_KS_PATH = './tests/cert/test_client_ks.zip'
VALID_STORAGE = './tests/cert/test_keystorage.zip'
PASSWD = 'qwerty123'

TMP_FILE = '/tmp/test_file.out'

class MockedFriClient:
    def __init__(self, is_ssl=None, cert=None, session_id=None):
        self.data_map = {}

    def call_sync(self, node_addr, packet, FRI_CLIENT_TIMEOUT):
        if packet.method == 'GetKeysInfo':
            ret_keys = []
            key = packet.parameters.get('key', None)
            ret_keys.append((key, False, 'some_mode_addr'))
            return FabnetPacketResponse(ret_parameters={'keys_info': ret_keys})

        elif packet.method == 'ClientPutData':
            key = packet.parameters.get('key', None)
            if key:
                primary_key = key
            else:
                primary_key = hashlib.sha1(datetime.utcnow().isoformat()+str(random.randint(0,1000000))).hexdigest()

            data = packet.binary_data.data()
            source_checksum = hashlib.sha1(data).hexdigest()

            self.data_map[primary_key] = data

            time.sleep(.1)
            return FabnetPacketResponse(ret_parameters={'key': primary_key})

        elif packet.method == 'GetDataBlock':
            time.sleep(0.1)

            raw_data = self.data_map.get(packet.parameters['key'], None)
            if not raw_data:
                return FabnetPacketResponse(ret_code=324, ret_message='No data found!')
            return FabnetPacketResponse(binary_data=raw_data, ret_parameters={'checksum': hashlib.sha1(raw_data).hexdigest()})



class TestDHTInitProcedure(unittest.TestCase):
    NIBBLER_INST = None

    def test01_dht_init(self):
        security_manager = FileBasedSecurityManager(CLIENT_KS_PATH, PASSWD)
        nibbler = Nibbler('127.0.0.1', security_manager)
        nibbler.fabnet_gateway.fri_client = MockedFriClient()
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

