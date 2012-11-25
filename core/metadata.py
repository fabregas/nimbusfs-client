#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.metadata
@author Konstantin Andrusenko
@date October 12, 2012

This module contains the implementation of user metadata classes.
"""
import json
import hashlib
from datetime import datetime
import threading

from client.constants import DEFAULT_REPLICA_COUNT

class BadMetadata(Exception):
    def __init__(self, msg):
        Exception.__init__(self, 'Bad metadata. %s'%msg)

class PathException(Exception):
    pass

class ChunkMD:
    def __init__(self, key=None, checksum=None, seek=None, size=None):
        self.checksum = checksum
        self.key = key
        self.seek = seek
        self.size = size

    def load(self, chunk_obj):
        self.checksum = chunk_obj.get('checksum', None)
        self.key = chunk_obj.get('key', None)
        self.seek = chunk_obj.get('seek', None)
        self.size = chunk_obj.get('size', None)

        if self.checksum is None:
            raise BadMetadata('Chunk checksum does not found!')
        if self.key is None:
            raise BadMetadata('Chunk key does not found!')
        if self.seek is None:
            raise BadMetadata('Chunk seek does not found!')
        if self.size is None:
            raise BadMetadata('Chunk size does not found!')

    def dump(self):
        return {'checksum': self.checksum,
                'key': self.key,
                'seek': self.seek,
                'size': self.size}


class FileMD:
    def __init__(self, name=None, size=0, replica_count=DEFAULT_REPLICA_COUNT, parent_dir=None):
        self.name = name
        self.size = size
        self.replica_count = replica_count
        self.chunks = []
        self.create_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

        self.__lock = threading.Lock()
        self.parent_dir = parent_dir

    @classmethod
    def is_dir(cls):
        return False

    @classmethod
    def is_file(cls):
        return True

    def load(self, file_obj):
        self.name = file_obj.get('name', None)
        self.size = file_obj.get('size', None)
        chunks = file_obj.get('chunks', [])
        for chunk in chunks:
            chunk_obj = ChunkMD()
            chunk_obj.load(chunk)
            self.chunks.append(chunk_obj)
        self.replica_count = file_obj.get('replica_count', DEFAULT_REPLICA_COUNT)
        create_date = file_obj.get('create_date', None)
        if create_date:
            self.create_date = create_date

        if self.name is None:
            raise BadMetadata('File name does not found!')
        if self.size is None:
            raise BadMetadata('File size does not found!')
        if self.replica_count is None:
            raise BadMetadata('File replica count does not found!')

    def dump(self):
        return {'name': self.name,
                'size': self.size,
                'chunks': [c.dump() for c in self.chunks],
                'replica_count': self.replica_count,
                'create_date': self.create_date}

    def append_chunk(self, key, checksum, seek, size):
        self.__lock.acquire()
        try:
            chunk_obj = ChunkMD(key, checksum, seek, size)
            self.chunks.append(chunk_obj)
        finally:
            self.__lock.release()

    def is_all_chunks(self):
        act_size = 0
        self.__lock.acquire()
        try:
            for chunk in self.chunks:
                act_size += chunk.size

            if act_size == self.size:
                return True
            return False
        finally:
            self.__lock.release()


class DirectoryMD:
    def __init__(self, name=''):
        self.name = name
        self.content = []
        self.create_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        self.last_modify_date = self.create_date

    @classmethod
    def is_dir(cls):
        return True

    @classmethod
    def is_file(cls):
        return False

    def load(self, dir_obj):
        self.name = dir_obj.get('name', None)
        if self.name is None:
            raise BadMetadata('Directory name does not found!')

        content = dir_obj.get('content', None)
        if content is None:
            raise BadMetadata('Directory content does not found!')

        create_date = dir_obj.get('create_date', None)
        if create_date:
            self.create_date = create_date
        last_mod_date = dir_obj.get('last_modify_date', None)
        if last_mod_date:
            self.last_modify_date = last_mod_date

        for item in content:
            if item.has_key('content'):
                item_md = DirectoryMD()
            else:
                item_md = FileMD()
            item_md.load(item)
            self.content.append(item_md)

    def dump(self):
        return {'name': self.name,
                'content': [c.dump() for c in self.content],
                'create_date': self.create_date,
                'last_modify_date': self.last_modify_date}

    def items(self):
        ret_items = []
        for item in self.content:
            ret_items.append((item.name, item.is_file()))

        return ret_items

    def get(self, item_name):
        for item in self.content:
            if item.name == item_name:
                return item

        raise PathException('"%s" does not found in %s directory'%(item_name, self.name))

    def append(self, item_md):
        if not isinstance(item_md, DirectoryMD) and not isinstance(item_md, FileMD):
            raise Exception('Item cant be appended to directory, bcs it type is equal to "%s"'%item_md)

        if item_md.is_file():
            self.remove(item_md.name)

        self.content.append(item_md)
        self.last_modify_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

    def remove(self, item_name):
        rm_i = None
        for i, item in enumerate(self.content):
            if item.name == item_name:
                rm_i = i
                break

        if rm_i is not None:
            del self.content[rm_i]
            self.last_modify_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')



class MetadataFile:
    def __init__(self):
        self.versions = []
        self.root_dir = None

    def load(self, md_str):
        md_obj = json.loads(md_str)
        self.versions = md_obj.get('versions', [])
        root_dir = md_obj.get('root_dir', DirectoryMD().dump())

        self.root_dir = DirectoryMD()
        self.root_dir.load(root_dir)

    def dump(self):
        d_obj = {'versions': self.versions,
                 'root_dir': self.root_dir.dump()}

        return json.dumps(d_obj)

    def find(self, path):
        items = path.split('/')
        cur_item = self.root_dir
        for item_name in items:
            if not item_name:
                continue

            if not cur_item.is_dir():
                raise PathException('Path "%s" does not found!'%path)

            cur_item = cur_item.get(item_name)

        return cur_item

    def exists(self, path):
        try:
            self.find(path)
        except PathException, err:
            return False

        return True

    def make_new_version(self, user_id):
        cdt = datetime.now().isoformat()
        new_version_key = hashlib.sha1(user_id+cdt).hexdigest()
        self.versions.append((cdt, new_version_key))
        return new_version_key

    def get_versions(self):
        return self.versions

    def remove_version(self, version_key):
        for_del = None
        for i, (vdt, ver_key) in enumerate(self.versions):
            if ver_key == version_key:
                for_del = i

        if for_del is not None:
            del self.versions[for_del]

