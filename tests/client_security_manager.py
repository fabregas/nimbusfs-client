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
import tempfile
import sys

from nimbus_client.core.security_manager import FileBasedSecurityManager
from nimbus_client.core import constants
constants.READ_TRY_COUNT = 100
constants.READ_SLEEP_TIME = 0.2
from nimbus_client.core.data_block import DataBlock
from util_init_test_env import *

CLIENT_KS_1024_PATH = './tests/cert/test_cl_1024.ks'
CLIENT_KS_4096_PATH = './tests/cert/test_client_ks.ks'

PASSWD = 'qwerty123'


class DBWriter(threading.Thread):
    def __init__(self, path, f_len):
        threading.Thread.__init__(self)
        self.path = path
        if os.path.exists(self.path):
            os.remove(self.path)
        open(self.path, 'w').close()
        self.f_len = f_len
        print 'simulating data block with size = %s ...'%f_len
        self.db = None
        self.checksum = hashlib.sha1()

    def run(self):
        self.db = DataBlock(self.path)# self.f_len)
        f_len = self.f_len
        parts = random.randint(1,11)
        for i in xrange(parts):
            data = ''.join(random.choice(string.letters) for i in xrange(f_len/parts))
            self.checksum.update(data)
            self.db.write(data)
            time.sleep(.1)

        rest = f_len - (f_len/parts)*parts
        if rest:
            data = ''.join(random.choice(string.letters) for i in xrange(rest))
            self.checksum.update(data)
            self.db.write(data)
        self.db.finalize()
        self.db.close()

    def get_checksum(self):
        return self.checksum.hexdigest()

class DBReader(threading.Thread):
    def __init__(self, path, f_len):
        threading.Thread.__init__(self)
        self.path = path
        self.f_len = f_len
        self.checksum = hashlib.sha1()

    def run(self):
        try:
            self.db = DataBlock(self.path, self.f_len)
            while True:
                data = self.db.read(1000)
                if not data:
                    break
                self.checksum.update(data)
            self.db.close()
            os.remove(self.path)
        except Exception, err:
            print 'ERROR: %s'%err

    def get_checksum(self):
        return self.checksum.hexdigest()

            

class TestSecManager(unittest.TestCase):
    def test_enc_dec(self):
        for i in xrange(10):
            self.iter_encr(1000+random.randint(0, 500), CLIENT_KS_4096_PATH)

    def iter_encr(self, data_len, key_storage):
        data = ''.join(random.choice(string.letters) for i in xrange(data_len))
        ks = FileBasedSecurityManager(key_storage, PASSWD)

        print 'Data block len: %s'%len(data)

        encdec = ks.get_encoder(data_len)
        encrypted = encdec.encrypt(data)
        print 'Encrypted data block len: %s'%len(encrypted)

        encdec = ks.get_encoder(data_len)
        decrypted = encdec.decrypt(encrypted)
        print 'Decrypted data block len: %s'%len(decrypted)

        self.assertEqual(decrypted, data)

    def test_inc_encode_decode(self):
        ks = FileBasedSecurityManager(CLIENT_KS_1024_PATH, PASSWD)
        key = ks.get_client_cert_key()
        self.assertEqual(key, 63)
        data = ''.join(random.choice(string.letters) for i in xrange(1024))
        TEST_LEN = 10000
        encdec = ks.get_encoder(TEST_LEN)
        or_data = ''
        dc_data = ''
        for i in xrange(TEST_LEN/100):
            data = ''.join(random.choice(string.letters) for i in xrange(100))
            or_data += data
            dc_data += encdec.encrypt(data)

        self.assertEqual(len(dc_data), encdec.get_expected_data_len())

        encdec = ks.get_encoder(TEST_LEN)
        data = ''
        for i in xrange(TEST_LEN/1000):
            data += encdec.decrypt(dc_data[i*1000:(i+1)*1000])
        data += encdec.decrypt(dc_data[(i+1)*1000:])

        self.assertEqual(data, or_data)

    def test_data_block(self):
        ks = FileBasedSecurityManager(CLIENT_KS_1024_PATH, PASSWD)
        DataBlock.SECURITY_MANAGER = ks
        DB_PATH = tmp('test_data_block.kst')

        DATA_LEN = 10
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        db = DataBlock(DB_PATH, DATA_LEN, force_create=True)
        checksum = hashlib.sha1()
        for i in xrange(DATA_LEN/10):
            data = ''.join(random.choice(string.letters) for i in xrange(DATA_LEN/(DATA_LEN/10)))
            checksum.update(data)
            db.write(data)
        db.close()
        db.close() #should be OK
        or_checksum = checksum.hexdigest()
        enc_checksum = db.checksum()

        db = DataBlock(DB_PATH, DATA_LEN)
        ret_data = ''
        checksum = hashlib.sha1()
        while True:
            data = db.read(100)
            if not data:
                break
            ret_data += data
            checksum.update(data)
        self.assertEqual(or_checksum, checksum.hexdigest())
        self.assertEqual(db.checksum(), enc_checksum)

        db = DataBlock(DB_PATH, DATA_LEN)
        raw = db.read_raw()
        self.assertEqual(db.checksum(), enc_checksum)

        db = DataBlock(DB_PATH, DATA_LEN)
        raw = db.read()
        self.assertEqual(ret_data, raw)

        app_db = DataBlock(DB_PATH)
        app_db.write('The end!')
        app_db.finalize()
        app_db.close()

        db = DataBlock(DB_PATH, actsize=True)
        raw = db.read()
        self.assertEqual(ret_data+'The end!', raw)
        db.close()

    def test_parallel_read_write(self):
        ks = FileBasedSecurityManager(CLIENT_KS_1024_PATH, PASSWD)
        DataBlock.SECURITY_MANAGER = ks
        writers = []
        readers = []
        NUM = 25
        for i in xrange(NUM):
            path = tmp('parallel_read_write_db.%s'%i)
            flen = random.randint(10, 10000)
            dbw = DBWriter(path, flen)
            dbr = DBReader(path, flen)
            writers.append(dbw)
            readers.append(dbr)

        for writer in writers:
            writer.start()
        for reader in readers:
            reader.start()

        for i,writer in enumerate(writers):
            writer.join()
            readers[i].join()
            self.assertEqual(writer.get_checksum(), readers[i].get_checksum(), 'Num=%s, len=%s'%(i,writer.f_len))


if __name__ == '__main__':
    unittest.main()

