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


from nimbus_client.core.metadata import *
from nimbus_client.core.metadata_file import *
from nimbus_client.core.security_manager import FileBasedSecurityManager
from nimbus_client.core.data_block import DataBlock

CLIENT_KS_PATH = './tests/cert/test_cl_1024.zip'
PASSWD = 'qwerty123'


class TestMetadata(unittest.TestCase):
    def test_chunk_md(self):
        with self.assertRaises(MDValidationError):
            chunk = ChunkMD()
            chunk.dump()

        with self.assertRaises(MDValidationError):
            chunk = ChunkMD(checksum='a12324', seek=pow(2, 65), size=444)
            chunk.dump()

        with self.assertRaises(MDValidationError):
            chunk = ChunkMD(checksum='a12324', seek=42353, size=pow(2,35))
            chunk.dump()

        with self.assertRaises(MDValidationError):
            chunk = ChunkMD(checksum='a12324', seek=42353, size=pow(2,35))
            chunk.dump()

        with self.assertRaises(MDValidationError):
            chunk = ChunkMD(checksum='4235idsfsdfs23', seek=42353, size=35)
            chunk.dump()

        chunk = ChunkMD(checksum='a12324', seek=42353, size=324)
        dump = chunk.dump()
        restored_chunk = ChunkMD()
        restored_chunk.load(dump)
        self.assertEqual(restored_chunk.key, None)
        self.assertEqual(restored_chunk.local_key, None)


        checksum = hashlib.sha1('ewrfdsgsdgdfgsw').hexdigest()
        key = hashlib.sha1('ewrqwerfdasdfsw').hexdigest()
        local_key=hashlib.sha1('sadaaa').hexdigest()
        size = 23425522
        seek = 23235634532423

        chunk = ChunkMD(checksum=checksum, size=size, seek=seek, key=key)

        dump = chunk.dump()
        restored_chunk = ChunkMD()
        restored_chunk.load(dump)

        self.assertEqual(restored_chunk.checksum, checksum)
        self.assertEqual(restored_chunk.key, key)
        self.assertEqual(restored_chunk.size, size)
        self.assertEqual(restored_chunk.seek, seek)

        dump = chunk.dump()
        restored_chunk = ChunkMD()
        restored_chunk.load(dump)

        self.assertEqual(restored_chunk.checksum, checksum)
        self.assertEqual(restored_chunk.key, key)
        self.assertEqual(restored_chunk.local_key, None)
        self.assertEqual(restored_chunk.size, size)
        self.assertEqual(restored_chunk.seek, seek)

    def test_file_md(self):
        chunk = ChunkMD(checksum='a12324', size=23444, seek=2314, key='a12325')
        with self.assertRaises(MDValidationError):
            file_md = FileMD()
            file_md.append_chunk(chunk)
            file_md.dump()

        with self.assertRaises(MDValidationError):
            file_md = FileMD(name='test', size=pow(2,65), replica_count=2, parent_dir_id=222)
            file_md.append_chunk(chunk)
            file_md.dump()

        with self.assertRaises(MDValidationError):
            file_md = FileMD(name='test', size=235234534, replica_count=6666, parent_dir_id=222)
            file_md.append_chunk(chunk)
            file_md.dump()

        with self.assertRaises(MDValidationError):
            file_md = FileMD(name='test', size=235234534, replica_count=66, parent_dir_id=pow(2,35))
            file_md.append_chunk(chunk)
            file_md.dump()

        with self.assertRaises(MDValidationError):
            file_md = FileMD(name='test'*200, size=235234534, replica_count=66, parent_dir_id=324)
            file_md.append_chunk(chunk)
            file_md.dump()

        fname = 'This is test file name'
        size = 23213432532523
        parent_dir_id= 23423452
        replica_count=4
        file_md = FileMD(item_id=234,name=fname, size=size, replica_count=replica_count, parent_dir_id=parent_dir_id)
        file_md.append_chunk(chunk)
        dump = file_md.dump()

        restored_file_md = FileMD()
        restored_file_md.load(dump)
        self.assertEqual(restored_file_md.name, fname)
        self.assertEqual(restored_file_md.size, size)
        self.assertEqual(restored_file_md.replica_count, replica_count)
        self.assertEqual(restored_file_md.parent_dir_id, parent_dir_id)
        self.assertTrue(restored_file_md.create_date > 0)

        local_chunks, foreign_chunks = restored_file_md.chunks_stat()
        self.assertEqual(local_chunks, 0)
        self.assertEqual(foreign_chunks, 1)

    def test_dir_md(self):
        with self.assertRaises(MDValidationError):
            dir_md = DirectoryMD()
            dir_md.dump()

        with self.assertRaises(MDValidationError):
            dir_md = DirectoryMD(name='test', item_id=pow(2,35), parent_dir_id=0)
            dir_md.dump()

        with self.assertRaises(MDValidationError):
            dir_md = DirectoryMD(name='test', item_id=54353, parent_dir_id=pow(2,36))
            dir_md.dump()

        with self.assertRaises(MDValidationError):
            dir_md = DirectoryMD(name='test'*200, item_id=54353, parent_dir_id=325)
            dir_md.dump()


        dir_name = 'Test directory'
        dir_id = 235532
        parent_dir_id = 345
        dir_md = DirectoryMD(name=dir_name, item_id=dir_id, parent_dir_id=parent_dir_id)
        dump = dir_md.dump()
        r_dir_md = DirectoryMD()
        r_dir_md.load(dump)
        self.assertEqual(r_dir_md.name, dir_name)
        self.assertEqual(r_dir_md.item_id, dir_id)
        self.assertEqual(r_dir_md.parent_dir_id, parent_dir_id)
        self.assertTrue(r_dir_md.create_date > 0)
        self.assertTrue(r_dir_md.last_modify_date > 0)


        with self.assertRaises(TypeError):
            dir_md.append('some fake')

        self.assertEqual(dir_md.empty(), True)
        fname = 'This is test file name'
        size = 23213432532523
        parent_dir_id= 23423452
        replica_count=4
        file_md = FileMD(name=fname, size=size, replica_count=replica_count, parent_dir_id=parent_dir_id)
        chunk = ChunkMD(checksum='a12324', size=23444, seek=2314, key='a12325')
        file_md.append_chunk(chunk)
        dir_md.append(file_md)
        dumped = dir_md.dump(recursive=True)
        dir_md = DirectoryMD(dumped_md=dumped)
        self.assertEqual(dir_md.empty(), False)
        with self.assertRaises(AlreadyExistsException):
            dir_md.append(file_md)

        for item in dir_md.iteritems():
            self.assertEqual(item.is_file(), True)
            self.assertEqual(item.name, fname)
            self.assertEqual(item.size, size)

        with self.assertRaises(PathException):
            dir_md.get('unknown_file_name')

        item = dir_md.get(fname)
        self.assertEqual(item.name, fname)
        self.assertEqual(item.size, size)

        dir_md.remove('unknown_file_name')
        dir_md.remove(fname)
        self.assertEqual(dir_md.empty(), True)
        with self.assertRaises(PathException):
            dir_md.get(fname)


    def test_dir_md(self):
        md_file_path = '/tmp/md.cache'
        if os.path.exists(md_file_path):
            os.remove(md_file_path)
        FS_STR = [('/test_dir', 1), ('/test_dir/subdir', 1), ('/test_dir/my_file.txt', 0), ('/test_dir/subdir/test_file.txt', 0)]
        md_file = MetadataFile(md_file_path)

        for path, is_dir in FS_STR:
            b_dir, i_name = os.path.split(path)
            if is_dir:
                item = DirectoryMD(name=i_name)
            else:
                chunk = ChunkMD(checksum='a12324', size=23444, seek=2314, key='a12325')
                item = FileMD(name=i_name, size=3453, replica_count=2)
                item.append_chunk(chunk)
            md_file.append(b_dir, item)
        
        f_md = md_file.find('/test_dir/subdir/test_file.txt')
        self.assertEqual(f_md.is_file(), True)
        self.assertEqual(f_md.name, 'test_file.txt')
        self.assertEqual(f_md.replica_count, 2)
        self.assertEqual(f_md.size, 3453)
        self.assertEqual(f_md.create_date > 0, True)

        #md_file._print()
        with self.assertRaises(PathException):
            md_file.find('/test_dir/unknown')

        dir_md = md_file.find('/test_dir/subdir')
        f_md = md_file.find('/test_dir/my_file.txt')
        f_md.name = 'my_updated_file.txt'
        f_md.parent_dir_id = dir_md.item_id
        md_file.update(f_md)

        with self.assertRaises(PathException):
            md_file.find('/test_dir/my_file.txt')

        f_md = md_file.find('/test_dir/subdir/my_updated_file.txt')
        self.assertEqual(f_md.is_file(), True)
        self.assertEqual(f_md.name, 'my_updated_file.txt')

        with self.assertRaises(NotEmptyException):
            md_file.remove(dir_md)

        objects = md_file.listdir('/test_dir/subdir')
        self.assertEqual(len(objects), 2)
        for item in objects:
            md_file.remove(item)
            with self.assertRaises(PathException):
                md_file.find('/test_dir/subdir/%s'%item.name)

        md_file.remove(dir_md)
        with self.assertRaises(PathException):
            md_file.find('/test_dir/subdir')
        objects = md_file.listdir('/test_dir/')
        self.assertEqual(len(objects), 0)
        md_file.append('/test_dir/', DirectoryMD(name='subdir'))
        md_file.find('/test_dir/subdir')
        

    def test_journal(self):
        ks = FileBasedSecurityManager(CLIENT_KS_PATH, PASSWD)
        DataBlock.SECURITY_MANAGER = ks
        os.system('rm /tmp/test_nimbusfs_journal')
        journal = Journal('%040x'%23453, '/tmp/test_nimbusfs_journal', MockedFabnetGateway())
        try:
            dir_name = 'Test directory'
            dir_id = 235532
            parent_dir_id = 345
            dir_md = DirectoryMD(name=dir_name, item_id=dir_id, parent_dir_id=parent_dir_id)
            journal.append(Journal.OT_APPEND, dir_md)

            for record_id, operation_type, item_md in journal.iter():
                self.assertEqual(record_id, 1)
                self.assertEqual(operation_type, Journal.OT_APPEND)
                self.assertEqual(item_md.item_id, dir_id)
                self.assertEqual(item_md.parent_dir_id, parent_dir_id)
                self.assertEqual(item_md.name, dir_name)

            dir_name = 'new directory name'
            dir_md.dir_name = dir_name
            journal.append(Journal.OT_UPDATE, dir_md)
            for record_id, operation_type, item_md in journal.iter(2):
                self.assertEqual(record_id, 2)
                self.assertEqual(operation_type, Journal.OT_UPDATE)
                self.assertEqual(item_md.item_id, dir_id)
                self.assertEqual(item_md.parent_dir_id, parent_dir_id)
                self.assertEqual(item_md.name, dir_name)

            journal.append(Journal.OT_REMOVE, dir_md)
        finally:
            journal.close()
        
        journal = Journal('%040x'%23453, '/tmp/test_nimbusfs_journal', MockedFabnetGateway())
        cnt = 0
        for record_id, operation_type, item_md in journal.iter():
            cnt += 1
        journal.close()
        self.assertEqual(cnt, 3)


class MockedFabnetGateway:
    def get(self, primary_key, replica_count, data_block):
        if primary_key != '%040x'%23453:
            raise Exception('unknown metadata journal key')
        return 'OK'

    def put(self, data_block, key):
        if key != '%040x'%23453:
            raise Exception('unknown metadata journal key')


if __name__ == '__main__':
    unittest.main()

