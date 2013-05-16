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
import sys

sys.path.insert(0, './third-party')

from tinydav import WebDAVClient, HTTPUserError, HTTPServerError

from  nimbus_client.core import fabnet_gateway
from id_client.idepositbox_client import IdepositboxClient, \
            CS_STARTED, CS_STOPPED, Config
from id_client.constants import SPT_FILE_BASED, SPT_TOKEN_BASED

from client_base_test import MockedFriClient, wait_oper_status, Transaction
fabnet_gateway.FriClient = MockedFriClient
from nimbus_client.core.logger import logger

#logger.setLevel(logging.INFO)

CLIENT_KS_PATH = './tests/cert/test_cl_1024.ks'
PASSWD = 'qwerty123'

TEST_FILE = '/tmp/test_file.out'

class TestIdepositbox(unittest.TestCase):
    CLIENT = None
    def test00_start(self):
        if os.path.exists('/tmp/static_cache/'):
            os.system('rm -rf /tmp/static_cache/')
        if os.path.exists('/tmp/test_idepositbox.conf'):
            os.remove('/tmp/test_idepositbox.conf')
        Config.get_config_file_path = lambda a: '/tmp/test_idepositbox.conf'
        config = Config()
        config.webdav_bind_port = 8080
        config.save()
        TestIdepositbox.CLIENT = IdepositboxClient()

        TestIdepositbox.CLIENT.start(SPT_FILE_BASED, CLIENT_KS_PATH, PASSWD)

        self.assertEqual(TestIdepositbox.CLIENT.get_status(), CS_STARTED)

    def test01_create_dir(self):
        client = WebDAVClient("127.0.0.1", 8080)
        response = client.mkcol("/foo")
        self.assertEqual(response.statusline, 'HTTP/1.1 201 Created')

        with self.assertRaises(HTTPUserError):
            response = client.mkcol("/foo2/test1/test2")

    def test02_propfind(self):
        client = WebDAVClient("127.0.0.1", 8080)
        response = client.propfind("/foo")
        self.assertEqual(response.statusline, 'HTTP/1.1 207 Multistatus')
        self.assertTrue('displayname>foo<' in response.content)

    def test03_put(self):
        fb = open(TEST_FILE, 'wb')
        data = ''.join(random.choice(string.letters) for i in xrange(1024))
        data *= 5*1024
        fb.write(data)
        fb.close()

        TestIdepositbox.CHECKSUM = hashlib.sha1(data).hexdigest()
        client = WebDAVClient("127.0.0.1", 8080)

        with open(TEST_FILE) as fd:
            response = client.put('/foo/test.out', fd, "text/plain")
            self.assertEqual(response.statusline, 'HTTP/1.1 201 Created')

        response = client.propfind("/foo", depth=1)
        self.assertTrue('displayname>test.out<' in response.content)

        wait_oper_status(TestIdepositbox.CLIENT.get_nibbler().inprocess_operations, '/foo/test.out', Transaction.TS_FINISHED)


    def test04_get(self):
        client = WebDAVClient("127.0.0.1", 8080)

        response = client.get('/foo')
        self.assertEqual(response.statusline, 'HTTP/1.1 200 OK')

        response = client.get('/foo/test.out')
        self.assertEqual(response.statusline, 'HTTP/1.1 200 OK')

        self.assertEqual(TestIdepositbox.CHECKSUM, hashlib.sha1(response.content).hexdigest())

    def test05_delete(self):
        client = WebDAVClient("127.0.0.1", 8080)
        response = client.delete('/foo/test.out')
        self.assertEqual(response.statusline, 'HTTP/1.1 204 No Content')

        with self.assertRaises(HTTPUserError):
            response = client.delete('/foo/test.out')

        response = client.delete('/foo/')
        self.assertEqual(response.statusline, 'HTTP/1.1 204 No Content')

        with self.assertRaises(HTTPUserError):
            client.propfind("/foo")


    def test99_stop(self):
        time.sleep(1.0)
        TestIdepositbox.CLIENT.stop()
        self.assertEqual(TestIdepositbox.CLIENT.get_status(), CS_STOPPED)



if __name__ == '__main__':
    unittest.main()

