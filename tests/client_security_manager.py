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


from nimbus_client.core.security_manager import FileBasedSecurityManager
from nimbus_client.core import constants
constants.READ_TRY_COUNT = 100
constants.READ_SLEEP_TIME = 0.1
from nimbus_client.core.data_block import DataBlock



CLIENT_KS_PATH = './tests/cert/test_client_ks.zip'
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
        self.db = DataBlock(self.path, self.f_len)
        self.checksum = hashlib.sha1()

    def run(self):
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
        self.db.close()

    def get_checksum(self):
        return self.checksum.hexdigest()

class DBReader(threading.Thread):
    def __init__(self, path, f_len):
        threading.Thread.__init__(self)
        self.path = path
        self.f_len = f_len
        self.db = DataBlock(self.path, self.f_len)
        self.checksum = hashlib.sha1()

    def run(self):
        while True:
            data = self.db.read(1000)
            if not data:
                break
            self.checksum.update(data)
        self.db.close()
        os.remove(self.path)

    def get_checksum(self):
        return self.checksum.hexdigest()

            

class TestSecManager(unittest.TestCase):
    def test_enc_dec(self):
        for i in xrange(10):
            self.iter_encr(1000+random.randint(0, 500))

    def iter_encr(self, data_len):
        data = ''.join(random.choice(string.letters) for i in xrange(data_len))
        ks = FileBasedSecurityManager(CLIENT_KS_PATH, PASSWD)

        print 'Data block len: %s'%len(data)

        encdec = ks.get_encoder(data_len)
        encrypted = encdec.encrypt(data)
        print 'Encrypted data block len: %s'%len(encrypted)

        encdec = ks.get_encoder(data_len)
        decrypted = encdec.decrypt(encrypted)
        print 'Decrypted data block len: %s'%len(decrypted)

        self.assertEqual(decrypted, data)

    def __test_inc_encode_decode(self):
        ks = FileBasedSecurityManager(CLIENT_KS_PATH, PASSWD)
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
        ks = FileBasedSecurityManager(CLIENT_KS_PATH, PASSWD)
        DataBlock.SECURITY_MANAGER = ks
        DB_PATH = '/tmp/test_data_block.kst'

        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        db = DataBlock(DB_PATH, 10000)
        checksum = hashlib.sha1()
        for i in xrange(100):
            data = ''.join(random.choice(string.letters) for i in xrange(100))
            checksum.update(data)
            db.write(data)
        db.close()
        db.close() #should be OK
        or_checksum = checksum.hexdigest()
        enc_checksum = db.checksum()

        db = DataBlock(DB_PATH, 10000)
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

        db = DataBlock(DB_PATH, 10000)
        raw = db.read_raw()
        self.assertEqual(db.checksum(), enc_checksum)

        db = DataBlock(DB_PATH, 10000)
        raw = db.read()
        self.assertEqual(ret_data, raw)

    def test_parallel_read_write(self):
        writers = []
        readers = []
        for i in xrange(50):
            path = '/tmp/parallel_read_write_db.%s'%i
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
            self.assertEqual(writer.get_checksum(), readers[i].get_checksum(), writer.f_len)



if __name__ == '__main__':
    unittest.main()

