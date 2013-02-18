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
from Queue import Queue, Empty

from nimbus_client.core.smart_file_object import SmartFileObject
from nimbus_client.core.transactions_manager import *
from nimbus_client.core.data_block_cache import DataBlockCache
from nimbus_client.core.metadata_file import MDFile
from nimbus_client.core.data_block import DataBlock, DBLocksManager
from nimbus_client.core.security_manager import FileBasedSecurityManager

CLIENT_KS_PATH = './tests/cert/test_client_ks.zip'
PASSWD = 'qwerty123'

class MockedGetThread(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        transaction, seek = self.queue.get()
        data_block,_ = transaction.get_data_block(seek)
        w_db = data_block.clone()
        w_db.write('this is test message for one data block!')
        w_db.close()

class TestSmartFileObject(unittest.TestCase):

    def test_base(self):
        ks = FileBasedSecurityManager(CLIENT_KS_PATH, PASSWD)
        DataBlock.SECURITY_MANAGER = ks
        DataBlock.LOCK_MANAGER = DBLocksManager()
        p_queue = Queue()
        g_queue = Queue()
        os.system('rm -rf /tmp/dynamic_cache/*')
        os.system('rm /tmp/test_tr.log')
        os.system('rm /tmp/test_md.bin')
        db_cache = DataBlockCache('/tmp')
        tr_manager = TransactionsManager(MDFile('/tmp/test_md.bin'), db_cache, '/tmp/test_tr.log', p_queue, g_queue)
        SmartFileObject.setup_transaction_manager(tr_manager)

        test_file = SmartFileObject('/test.file')
        test_file.write('this is test message for one data block!')
        test_file.close()
        put_obj = p_queue.get(False)
        transaction, seek = put_obj
        self.assertEqual(seek, 0)
        data_block, next_seek = transaction.get_data_block(seek)
        self.assertNotEqual(data_block, None)
        self.assertEqual(next_seek, None)
        data_block.close()

        tr_manager.update_transaction(transaction.get_id(), seek, is_failed=False, foreign_name='%040x'%123456)
        self.assertEqual(transaction.get_status(), Transaction.TS_FINISHED)


        test_file = SmartFileObject('/test.file')
        data = test_file.read(4)
        self.assertEqual(data, 'this')
        self.assertTrue(DataBlock.is_locked(db_cache.get_cache_path('%040x'%123456)))
        data = test_file.read()
        self.assertEqual(data, ' is test message for one data block!')
        test_file.close()
        self.assertFalse(DataBlock.is_locked(db_cache.get_cache_path('%040x'%123456)))
        with self.assertRaises(Empty):
            get_obj = g_queue.get(False)

        mgt = MockedGetThread(g_queue)
        mgt.start()
        os.system('rm -rf /tmp/dynamic_cache/*')
        test_file = SmartFileObject('/test.file')
        data = test_file.read()
        self.assertEqual(data, 'this is test message for one data block!')
        test_file.close()

        self.assertFalse(DataBlock.is_locked(db_cache.get_cache_path('%040x'%123456)))

        db_cache.stop()


if __name__ == '__main__':
    unittest.main()

