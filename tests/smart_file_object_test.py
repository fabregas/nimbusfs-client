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
import logging
from Queue import Queue, Empty

from nimbus_client.core import transactions_manager
transactions_manager.MAX_TR_LOG_ITEMS = 10

from nimbus_client.core.smart_file_object import SmartFileObject
from nimbus_client.core.transactions_manager import *
from nimbus_client.core.data_block_cache import DataBlockCache
from nimbus_client.core.metadata_file import MetadataFile
from nimbus_client.core.data_block import DataBlock, DBLocksManager
from nimbus_client.core.security_manager import FileBasedSecurityManager
from util_init_test_env import *


CLIENT_KS_PATH = './tests/cert/test_cl_1024.ks'
PASSWD = 'qwerty123'

class MockedGetThread(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            transaction, seek = self.queue.get()
            if transaction is None:
                break
            data_block,_,_ = transaction.get_data_block(seek)
            w_db = data_block.clone()
            w_db.write('this is test message for one data block!')
            w_db.close()

class TestSmartFileObject(unittest.TestCase):

    def test00_base(self):
        ks = FileBasedSecurityManager(CLIENT_KS_PATH, PASSWD)
        DataBlock.SECURITY_MANAGER = ks
        DataBlock.LOCK_MANAGER = DBLocksManager()
        remove_dir(tmp('smart_file_test'))
        os.makedirs(tmp('smart_file_test/dynamic_cache'))
        os.makedirs(tmp('smart_file_test/static_cache'))

        db_cache = DataBlockCache(tmp('smart_file_test'))
        md = MetadataFile(db_cache.get_static_cache_path('test_md.bin'))
        tr_manager = None
        try:
            tr_manager = TransactionsManager(md, db_cache)
            p_queue = tr_manager.get_upload_queue()
            g_queue = tr_manager.get_download_queue()
            SmartFileObject.setup_transaction_manager(tr_manager)

            e_file = SmartFileObject('/empty_file', for_write=True)
            e_file.close()

            e_file = SmartFileObject('/empty_file')
            data = e_file.read()
            self.assertEqual(data, '')
            e_file.close()

            test_file = SmartFileObject('/test.file', for_write=True)
            test_file.write('this is test message for one data block!')
            test_file.close()
            put_obj = p_queue.get(False)
            transaction, seek = put_obj
            self.assertEqual(seek, 0)
            data_block, next_seek, _ = transaction.get_data_block(seek, noclone=True)
            self.assertNotEqual(data_block, None)
            self.assertEqual(next_seek, None)
            data_block.close()

            tr_manager.update_transaction(transaction.get_id(), seek, is_failed=False, foreign_name='%040x'%123456)
            self.assertEqual(transaction.get_status(), Transaction.TS_FINISHED)

            db_path = '%s.%s'%(transaction.get_id(), seek)
            self.assertFalse(DataBlock.is_locked(db_cache.get_cache_path(db_path)))

            test_file = SmartFileObject('/test.file')
            data = test_file.read(4)
            self.assertEqual(data, 'this')
            self.assertTrue(DataBlock.is_locked(db_cache.get_cache_path(db_path)))
            data = test_file.read()
            self.assertEqual(data, ' is test message for one data block!')
            test_file.close()
            self.assertFalse(DataBlock.is_locked(db_cache.get_cache_path(db_path)))
            with self.assertRaises(Empty):
                get_obj = g_queue.get(False)

            mgt = MockedGetThread(g_queue)
            mgt.start()

            open(db_cache.get_cache_path(db_path), 'w').write('invalid data') #failed local data block
            test_file = SmartFileObject('/test.file')
            data = test_file.read()
            self.assertEqual(data, 'this is test message for one data block!')
            test_file.close()

            remove_dir(tmp('smart_file_test/dynamic_cache'))
            os.makedirs(tmp('smart_file_test/dynamic_cache'))

            test_file = SmartFileObject('/test.file')
            data = test_file.read()
            self.assertEqual(data, 'this is test message for one data block!')
            test_file.close()

            self.assertFalse(DataBlock.is_locked(db_cache.get_cache_path('%040x'%123456)))
        finally:
            if tr_manager:
                g_queue.put((None,None))
                tr_manager.close()
            md.close()
            db_cache.stop()


    def test01_trans_manager(self):
        db_cache = DataBlockCache(tmp('smart_file_test'))
        open(db_cache.get_static_cache_path('transactions.log'), 'w').close()
        try:
            remove_dir(tmp('smart_file_test/dynamic_cache'))
            os.makedirs(tmp('smart_file_test/dynamic_cache'))

            md = MetadataFile(db_cache.get_static_cache_path('test_md.bin'))
            tr_manager = TransactionsManager(md, db_cache, 2)

            transaction_id = tr_manager.start_upload_transaction('/not_cached_test.file')
            tr_manager.transfer_data_block(transaction_id, 0, 3500, \
                    DataBlock(db_cache.get_cache_path('fake_for_delete'), force_create=True))
            self.assertTrue(os.path.exists(db_cache.get_cache_path('fake_for_delete')))
            fake_for_delete_name = '%s.%s'%(transaction_id, 0)

            transaction_id = tr_manager.start_upload_transaction('/my_second_test.file')
            tr_manager.transfer_data_block(transaction_id, 0, 1000, DataBlock(db_cache.get_cache_path('fake')))
            tr_manager.transfer_data_block(transaction_id, 1000, 2000, DataBlock(db_cache.get_cache_path('fake1')))
            tr_manager.update_transaction_state(transaction_id, Transaction.TS_LOCAL_SAVED)
            tr_manager.transfer_data_block(transaction_id, 0, 1000, DataBlock(db_cache.get_cache_path('fake2')), '%040x'%123456)

            transaction = tr_manager.start_download_transaction('/test.file')
            db,_,_ = transaction.get_data_block(0)
            read_block_name = '%s.%s'%(transaction.get_id(), 0)
            self.assertTrue(os.path.exists(db_cache.get_cache_path(read_block_name)))
            db.close()

            md.close()
            tr_manager.close()
            self.assertFalse(DataBlock.is_locked(db_cache.get_cache_path(read_block_name)))

            md = MetadataFile(db_cache.get_static_cache_path('test_md.bin'))
            tr_manager = TransactionsManager(md, db_cache, 2)

            up_queue = tr_manager.get_upload_queue()
            self.assertEqual(up_queue.qsize(), 1)

            self.assertFalse(os.path.exists(db_cache.get_cache_path(fake_for_delete_name)))
            self.assertFalse(os.path.exists(db_cache.get_cache_path(read_block_name)), read_block_name)
            md.close()
            tr_manager.close()

            open(db_cache.get_static_cache_path('transactions.log'), 'w').close()

            md = MetadataFile(db_cache.get_static_cache_path('test_md.bin'))
            tr_manager = TransactionsManager(md, db_cache, 5)
            transactions = []
            for i in xrange(7):
                transaction_id = tr_manager.start_upload_transaction('/%s_test.file'%i)
                transactions.append(transaction_id)

            cnt = 0
            for i, (is_up, path, stat, size, progress) in enumerate(tr_manager.iterate_transactions()):
                self.assertEqual(path, '/%s_test.file'%i)
                cnt += 1
            self.assertEqual(cnt, 7)

            for tr_id in transactions:
                tr_manager.update_transaction_state(tr_id, Transaction.TS_FAILED)

            cnt = 0
            tr_manager.start_upload_transaction('/7_test.file')
            for i, (is_up, path, stat, size, progress) in enumerate(tr_manager.iterate_transactions()):
                self.assertEqual(path, '/%s_test.file'%(i+3))
                cnt += 1
            self.assertEqual(cnt, 5)

            for i in xrange(5):
                tr_manager.start_upload_transaction('/%s_2_test.file'%i)
        finally:
            db_cache.stop()

    def test99_finally(self):
        remove_dir(tmp('smart_file_test'))

if __name__ == '__main__':
    unittest.main()

