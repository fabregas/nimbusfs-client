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
constants.MAX_DATA_BLOCK_SIZE = 100000

from nimbus_client.core.nibbler import Nibbler
from nimbus_client.core.transactions_manager import Transaction
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

        elif packet.method == 'PutKeysInfo':
            primary_key = packet.parameters.get('key', None)
            if not primary_key:
                primary_key = hashlib.sha1(datetime.utcnow().isoformat()+str(random.randint(0,1000000))).hexdigest()
            return FabnetPacketResponse(ret_parameters={'key_info': (primary_key, 'some_mode_addr')})

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
            return FabnetPacketResponse(ret_parameters={'key': primary_key, 'checksum': source_checksum})

        elif packet.method == 'GetDataBlock':
            time.sleep(0.1)

            raw_data = self.data_map.get(packet.parameters['key'], None)
            if raw_data is None:
                return FabnetPacketResponse(ret_code=324, ret_message='No data found!')

            return FabnetPacketResponse(binary_data=raw_data, ret_parameters={'checksum': hashlib.sha1(raw_data).hexdigest()})



class TestDHTInitProcedure(unittest.TestCase):
    NIBBLER_INST = None

    def test01_dht_init(self):
        os.system('rm -rf /tmp/dynamic_cache/*')
        os.system('rm -rf /tmp/static_cache/*')
        security_manager = FileBasedSecurityManager(CLIENT_KS_PATH, PASSWD)
        nibbler = Nibbler('127.0.0.1', security_manager)
        nibbler.fabnet_gateway.fri_client = MockedFriClient()
        TestDHTInitProcedure.NIBBLER_INST = nibbler
        with self.assertRaises(NoJournalFoundException):
            nibbler.start()
            
        self.assertEqual(nibbler.is_registered(), False)
        nibbler.register_user()
        #nibbler.fabnet_gateway.put('', key='ce86e852d68cf8e3eee83b8d453172fb3c4fefa6')
        nibbler.start()

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

        data = ''.join(random.choice(string.letters) for i in xrange(1024))
        data *= 5*1024
        checksum = hashlib.sha1(data).hexdigest()
    
        with self.assertRaises(PathException):
            f_obj = nibbler.open_file('/some/dir/file.fake')
            f_obj.write('test')
            f_obj.close()

        with self.assertRaises(ClosedFileException):
            f_obj.write('test')

        print 'writing data to NimbusFS...'
        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out')
        f_obj.write(data[:100])
        f_obj.write(data[100:])
        f_obj.close()

        with self.assertRaises(AlreadyExistsException):
            f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out')
            f_obj.write('test')
            f_obj.close()

        op_list = nibbler.inprocess_operations()
        self.assertEqual(len(op_list), 1)
        oper_info = op_list[0]
        self.assertEqual(oper_info.is_upload, True)
        self.assertEqual(oper_info.file_path, '/my_first_dir/my_first_subdir/test_file.out')
        self.assertEqual(oper_info.status, Transaction.TS_LOCAL_SAVED)
        self.assertEqual(oper_info.size, len(data))
        self.assertEqual(oper_info.progress_perc > 0, True)
        self.assertEqual(oper_info.progress_perc < 100, True)

        fs_item = nibbler.find('/my_first_dir/my_first_subdir/test_file.out')
        self.assertEqual(fs_item.name, 'test_file.out')
        self.assertEqual(fs_item.size, len(data))
        self.assertEqual(fs_item.is_file, True)
        self.assertEqual(fs_item.is_dir, False)
        self.assertNotEqual(fs_item.create_dt, None)
        self.assertEqual(fs_item.create_dt, fs_item.modify_dt)

        for i in xrange(20):
            time.sleep(.1)
            op_list = nibbler.inprocess_operations()
            oper_info = op_list[0]
            if oper_info.status == Transaction.TS_FINISHED:
                break
        else:
            raise Exception('transaction does not finished')

        with self.assertRaises(NotDirectoryException):
            f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out/subfile.lol')
            f_obj.write('test')
            f_obj.close()

        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/small_file')
        f_obj.write('test message')
        f_obj.close()

        s_data_len = len(data)
        checksum = hashlib.sha1(data).hexdigest()

        #clear cached data blocks...
        os.system('rm -rf /tmp/dynamic_cache/*')

        print 'reading data from NimbusFS file...'
        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out')
        data = ''
        while True:
            chunk = f_obj.read(1000)
            if not chunk:
                break
            data  += chunk
        f_obj.close()

        self.assertEqual(len(data), s_data_len)
        self.assertEqual(hashlib.sha1(data).hexdigest(), checksum)

        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out')
        data = f_obj.read()
        self.assertEqual(len(data), s_data_len)
        self.assertEqual(hashlib.sha1(data).hexdigest(), checksum)

        with self.assertRaises(PathException):
            f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out11111')
            f_obj.read()

        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/small_file')
        data = f_obj.read()
        f_obj.close()
        self.assertEqual(data, 'test message')
        print 'finished!'

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
        self.assertEqual(items[1].name, 'small_file')
        self.assertEqual(items[1].is_file, True)

        with self.assertRaises(PathException):
            nibbler.listdir('/some/imagine/path')

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
            nibbler.rmdir('/my_first_dir/my_first_subdir/small_file')

        nibbler.rmdir('/my_first_dir', recursive=True)
        items = nibbler.listdir()
        self.assertEqual(len(items), 2, items)
        self.assertEqual(items[0].name, 'my_second_dir')



if __name__ == '__main__':
    unittest.main()

