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
import traceback
from datetime import datetime
from Queue import Queue
from nimbus_client.core.logger import logger
from nimbus_client.core.fri.fri_base import FabnetPacketResponse

logger.setLevel(logging.INFO)
from nimbus_client.core import constants
constants.MAX_DATA_BLOCK_SIZE = 100000
constants.READ_TRY_COUNT = 10
constants.READ_SLEEP_TIME = 0.2
constants.FG_ERROR_TIMEOUT = 0.2
constants.JOURNAL_SYNC_CHECK_TIME = 1

from nimbus_client.core.nibbler import Nibbler
from nimbus_client.core.data_block import DataBlock
from nimbus_client.core.transactions_manager import Transaction
from nimbus_client.core.security_manager import FileBasedSecurityManager
from nimbus_client.core.exceptions import *
from util_init_test_env import *
from util_mocked_id_client import MockedFriClient, FAIL, OK

DEBUG=False

CLIENT_KS_PATH = './tests/cert/test_cl_1024.ks'
PASSWD = 'qwerty123'


def wait_oper_status(inprocess_operations_func, file_path, status):
    for i in xrange(300):
        time.sleep(.1)
        op_list = inprocess_operations_func(only_inprogress=False)
        for oper_info in op_list:
            if oper_info.status == status and oper_info.file_path == file_path:
                return
    else:
        op_list = inprocess_operations_func(only_inprogress=False)
        for oper_info in op_list:
            print oper_info
        raise Exception('wait_oper_status(%s, %s) failed!'%(file_path, status))


class PutGetWorker(threading.Thread):
    def __init__(self, nibbler, queue, errors_q):
        threading.Thread.__init__(self)
        self.nibbler = nibbler
        self.queue = queue
        self.errors_q = errors_q

    def run(self):
        while True:
            try:
                task = self.queue.get()
                if not task:
                    break

                is_upload, f_name = task
                f_obj = self.nibbler.open_file(f_name, for_write=True)
                if is_upload:
                    data = ''.join(random.choice(string.letters) for i in xrange(100))
                    f_obj.write(data)
                    f_obj.close()
                else:
                    data = f_obj.read()
                    if len(data) != 100:
                        raise Exception('Infalid data in %s'%f_name)
                    f_obj.close()
            except Exception, err:
                logger.write = logger.error
                traceback.print_exc(file=logger)
                print 'PutGetWorker FAILED: %s' % err
                self.errors_q.put('PutGetWorker FAILED: %s' % err)
            finally:
                self.queue.task_done()



class BaseNibblerTest(unittest.TestCase):
    NIBBLER_INST = None

    def test01_nibbler_init(self):
        remove_dir(tmp('client_base_test'))
        os.makedirs(tmp('client_base_test/dynamic_cache'))
        os.makedirs(tmp('client_base_test/static_cache'))

        security_manager = FileBasedSecurityManager(CLIENT_KS_PATH, PASSWD)
        nibbler = Nibbler('127.0.0.1', security_manager, cache_dir=tmp('client_base_test'))
        nibbler.fabnet_gateway.fri_client = MockedFriClient()
        BaseNibblerTest.NIBBLER_INST = nibbler
        with self.assertRaises(NoJournalFoundException):
            nibbler.start()
            
        self.assertEqual(nibbler.is_registered(), False)
        nibbler.register_user()
        nibbler.start()

    def test99_nibbler_stop(self):
        BaseNibblerTest.NIBBLER_INST.stop()
        try:
            lock_list = DataBlock.LOCK_MANAGER.locks()
            self.assertEqual(len(lock_list), 0, lock_list)
        finally:
            time.sleep(1)
        remove_dir(tmp('client_base_test'))

    def test02_create_dir(self):
        nibbler = BaseNibblerTest.NIBBLER_INST
        nibbler.mkdir('/my_first_dir')
        nibbler.mkdir('/my_second_dir')
        nibbler.mkdir('/my_first_dir/my_first_subdir')

        with self.assertRaises(PathException):
            nibbler.mkdir('/this/is/not/exists/path')

        with self.assertRaises(AlreadyExistsException):
            nibbler.mkdir('/my_first_dir')

        nibbler.mkdir('/my_third_dir/subdir01/subdir02', recursive=True)

    def test03_save_file(self):
        nibbler = BaseNibblerTest.NIBBLER_INST

        data = ''.join(random.choice(string.letters) for i in xrange(1024))
        data *= 5*1024
        checksum = hashlib.sha1(data).hexdigest()
    
        f_obj = nibbler.open_file('/some/dir/file.fake', for_write=True)
        with self.assertRaises(PathException):
            f_obj.write('test')
        f_obj.close()
        with self.assertRaises(ClosedFileException):
            f_obj.write('test')

        with self.assertRaises(PermissionsException):
            f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out')
            f_obj.write('test data')

        print 'writing data to NimbusFS...'
        f_obj = nibbler.open_file(os.path.join('/my_first_dir/my_first_subdir','test_file.out'), for_write=True)
        f_obj.write('')
        f_obj.close()
        f_obj = nibbler.open_file(os.path.join('/my_first_dir/my_first_subdir','test_file.out'))
        e_data = f_obj.read()
        f_obj.close()
        self.assertEqual(e_data, '')

        #tmp files saved locally only
        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/._temp_file.tmp', for_write=True)
        f_obj.write('some data')
        f_obj.close()

        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/._temp_file.tmp', for_write=True)
        f_obj.write('test data')
        f_obj.write(' for local save')
        f_obj.close()

        f_obj = nibbler.open_file(os.path.join('/my_first_dir/my_first_subdir', 'test_file.out'), for_write=True)
        f_obj.write(data[:100])
        f_obj.write(data[100:])
        f_obj.close()

        op_list = nibbler.inprocess_operations(only_inprogress=False)
        self.assertEqual(len(op_list), 2, op_list)
        oper_info = op_list[1]
        self.assertEqual(oper_info.is_upload, True)
        self.assertEqual(oper_info.file_path, '/my_first_dir/my_first_subdir/test_file.out')
        self.assertEqual(oper_info.status, Transaction.TS_LOCAL_SAVED, oper_info)
        self.assertEqual(oper_info.size, len(data))
        self.assertEqual(oper_info.progress_perc > 0, True)
        self.assertEqual(oper_info.progress_perc < 100, True, oper_info.progress_perc)
        up_perc, down_perc, sum_perc = nibbler.transactions_progress()
        self.assertTrue(up_perc < 100)
        self.assertTrue(sum_perc == up_perc)
        self.assertTrue(down_perc == 100)

        fs_item = nibbler.find('/my_first_dir/my_first_subdir/test_file.out')
        self.assertEqual(fs_item.name, 'test_file.out')
        self.assertEqual(fs_item.size, len(data))
        self.assertEqual(fs_item.is_file, True)
        self.assertEqual(fs_item.is_dir, False)
        self.assertNotEqual(fs_item.create_dt, None)
        self.assertEqual(fs_item.create_dt, fs_item.modify_dt)

        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/small_file', for_write=True)
        f_obj.write('test message')
        f_obj.close()

        for i in xrange(20):
            time.sleep(.1)
            op_list = nibbler.inprocess_operations(only_inprogress=False)
            oper_info = op_list[1]
            if oper_info.status == Transaction.TS_FINISHED:
                break
        else:
            raise Exception('transaction does not finished')

        with self.assertRaises(NotDirectoryException):
            f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out/subfile.lol', for_write=True)
            f_obj.write('test')
            f_obj.close()

        s_data_len = len(data)
        checksum = hashlib.sha1(data).hexdigest()


        print 'reading data from NimbusFS file...'

        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/._temp_file.tmp')
        data = f_obj.read()
        f_obj.close()
        self.assertEqual(data, 'test data for local save')

        #clear cached data blocks...
        nibbler.db_cache.clear_all()

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

        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out', for_write=True)
        f_obj.write('test')
        f_obj.close()
        time.sleep(0.2)
        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out')
        self.assertEqual(f_obj.read(), 'test')
        f_obj.close()

        with self.assertRaises(PathException):
            f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out11111')
            f_obj.read()

        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/small_file')
        data = f_obj.read()
        f_obj.close()
        self.assertEqual(data, 'test message')

        f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/._temp_file.tmp')
        with self.assertRaises(NoLocalFileFound):
            data = f_obj.read()
        f_obj.close()
        print 'finished!'

    def test05_listdir(self):
        nibbler = BaseNibblerTest.NIBBLER_INST
        items = nibbler.listdir()
        self.assertEqual(len(items), 3, items)
        self.assertEqual(items[0].name, 'my_first_dir')
        self.assertEqual(items[0].is_dir, True)
        self.assertEqual(items[1].name, 'my_second_dir')
        self.assertEqual(items[1].is_dir, True)
        self.assertEqual(items[2].name, 'my_third_dir')
        self.assertEqual(items[2].is_dir, True)

        items = nibbler.listdir('/my_first_dir/my_first_subdir')
        self.assertEqual(len(items), 3, items)
        self.assertEqual(items[0].name, 'test_file.out')
        self.assertEqual(items[0].is_file, True)
        self.assertEqual(items[1].name, '._temp_file.tmp')
        self.assertEqual(items[1].is_file, True)
        self.assertEqual(items[2].name, 'small_file')
        self.assertEqual(items[2].is_file, True)

        with self.assertRaises(PathException):
            nibbler.listdir('/some/imagine/path')

    def test07_failed_read_transactions(self):
        nibbler = BaseNibblerTest.NIBBLER_INST
        nibbler.db_cache.clear_all()
        try:
            nibbler.fabnet_gateway.fri_client.change_mode(FAIL)
            f_obj = nibbler.open_file('/my_first_dir/my_first_subdir/test_file.out')
            with self.assertRaises(IOException):
                data = f_obj.read()
            f_obj.close()
            time.sleep(0.5)
            data_blocks = os.listdir(nibbler.db_cache.get_dynamic_cache_dir())
            self.assertEqual(len(data_blocks), 0)
        finally:
            nibbler.fabnet_gateway.fri_client.change_mode(OK)

    def test07_failed_write_transactions(self):
        nibbler = BaseNibblerTest.NIBBLER_INST
        nibbler.db_cache.clear_all()
        try:
            nibbler.fabnet_gateway.fri_client.change_mode(FAIL)
            f_obj = nibbler.open_file('/my_first_dir/new_file_with_up_fails', for_write=True)
            f_obj.write('test data block')
            f_obj.close()

            time.sleep(0.2)
        finally:
            nibbler.fabnet_gateway.fri_client.change_mode(OK)

        self.__wait_oper_status('/my_first_dir/new_file_with_up_fails', Transaction.TS_FINISHED)

        #fail on DB saving into local cache
        nibbler.db_cache.clear_all()
        f_obj = nibbler.open_file('/my_first_dir/new_file.failed', for_write=True)
        f_obj.write('*'*100100)
        def mocked_write(data, finalize):
            raise IOError('no free space mock')
        db_write_routine = f_obj._SmartFileObject__cur_data_block.write
        f_obj._SmartFileObject__cur_data_block.write = mocked_write
        with self.assertRaises(IOError):
            f_obj.close()
        time.sleep(0.2)

        self.__wait_oper_status('/my_first_dir/new_file.failed', Transaction.TS_FAILED)

        data_blocks = os.listdir(nibbler.db_cache.get_dynamic_cache_dir())
        self.assertEqual(len(data_blocks), 0, data_blocks)
        f_obj._SmartFileObject__cur_data_block.write = db_write_routine

        #fail on Metadata update
        f_obj = nibbler.open_file('/my_first_dir/new_file_2.failed', for_write=True)
        f_obj.write('*'*100100)
        def md_append_mocked(save_path, file_md, dummy=False):
            raise Exception('Oh! this is some exception from metadata ;(')
        md_append_func = nibbler.metadata.append
        nibbler.metadata.append = md_append_mocked
        f_obj.close()
        self.__wait_oper_status('/my_first_dir/new_file_2.failed', Transaction.TS_FAILED)
        data_blocks = os.listdir(nibbler.db_cache.get_dynamic_cache_dir())
        self.assertEqual(len(data_blocks), 0, data_blocks)
        nibbler.metadata.append = md_append_func

        #fail on Journal sync
        def sync_journal_mock():
            raise Exception('This is mocked exception')
        sync_journal_func = nibbler.journal._synchronize
        nibbler.journal._synchronize = sync_journal_mock
        f_obj = nibbler.open_file('/my_first_dir/new_file.saved', for_write=True)
        f_obj.write('*'*100100)
        f_obj.close()
        self.__wait_oper_status('/my_first_dir/new_file.saved', Transaction.TS_FINISHED)
        time.sleep(1.1)
        nibbler.journal._synchronize = sync_journal_func
        time.sleep(1.1)
        status = nibbler.journal.status()
        self.assertEqual(status, nibbler.journal.JS_SYNC)

    def __wait_oper_status(self, file_path, status):
        nibbler = BaseNibblerTest.NIBBLER_INST
        wait_oper_status(nibbler.inprocess_operations, file_path, status)

    def test08_remove_file(self):
        nibbler = BaseNibblerTest.NIBBLER_INST

        items = nibbler.listdir('/my_first_dir/my_first_subdir')
        self.assertEqual(len(items), 3, items)
        
        nibbler.remove_file('/my_first_dir/my_first_subdir/test_file.out')
        nibbler.remove_file('/my_first_dir/my_first_subdir/._temp_file.tmp')
        items = nibbler.listdir('/my_first_dir/my_first_subdir')
        self.assertEqual(len(items), 1, items)
        
    def test09_rmdir(self):
        nibbler = BaseNibblerTest.NIBBLER_INST
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

    def DISABLED_test10_profile(self):
        nibbler = BaseNibblerTest.NIBBLER_INST
        data = ''.join(random.choice(string.letters) for i in xrange(100))
        FILES_CNT = 100
        def put_files():
            for i in xrange(FILES_CNT):
                f_name = '/test_profile_%s.file'%i
                f_obj = nibbler.open_file(f_name, for_write=True)
                f_obj.write(data)
                f_obj.close()

        def get_files():
            for i in xrange(FILES_CNT):
                f_name = '/test_profile_%s.file'%i
                f_obj = nibbler.open_file(f_name)
                data = f_obj.read()
                f_obj.close()
                if len(data) != 100:
                    raise Exception('Infalid data in %s'%f_name)

        import cProfile
        import pstats
        cProfile.runctx('put_files()', globals(), locals(), 'put_files')
        cProfile.runctx('get_files()', globals(), locals(), 'get_files')

        print '========= put files stat ======='
        p = pstats.Stats('put_files')  
        p.strip_dirs().sort_stats('cumulative').print_stats()

        print '========= get files stat ======='
        p = pstats.Stats('get_files')  
        p.strip_dirs().sort_stats('cumulative').print_stats()


    def DISABLED_test10_stress(self):
        nibbler = BaseNibblerTest.NIBBLER_INST
        queue = Queue()
        err_queue = Queue()
        THREADS_CNT = 10
        FILES_CNT = 500
        for i in xrange(THREADS_CNT):
            worker = PutGetWorker(nibbler, queue, err_queue)
            worker.start()

        try:
            t0 = datetime.now()
            print '==> Put %s files to NimbusFS...'%FILES_CNT
            for i in xrange(FILES_CNT):
                queue.put((True, '/my_test_%s.file'%i))
            queue.join()
            print ' ==> finished (%s)!'%(datetime.now()-t0)

            if not err_queue.empty():
                raise Exception('Parallel upload failed!')

            t0 = datetime.now()
            print '==> check files existance in NimbusFS...'
            for i in xrange(FILES_CNT):
                self.assertNotEqual(nibbler.find('/my_test_%s.file'%i), None)
            print ' ==> finished (%s)!'%(datetime.now()-t0)

            t0 = datetime.now()
            print '==> get files from NimbusFS...'
            for i in xrange(FILES_CNT):
                queue.put((False, '/my_test_%s.file'%i))
            queue.join()
            print ' ==> finished (%s)!'%(datetime.now()-t0)
            if not err_queue.empty():
                raise Exception('Parallel download failed!')

        finally:
            for i in xrange(THREADS_CNT):
                queue.put(None)
            queue.join()



if __name__ == '__main__':
    unittest.main()

