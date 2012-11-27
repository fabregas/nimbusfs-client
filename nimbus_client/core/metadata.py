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
import uuid
import hashlib
from datetime import datetime
import threading

from nimbus_client.core.constants import DEFAULT_REPLICA_COUNT
from nimbus_client.core.exceptions import *

class ChunkMD:
    def __init__(self, **chunk_params):
        self.checksum = None
        self.key = None
        self.seek = None
        self.size = None
        self.load(chunk_params)

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
    def __init__(self, name=None, size=0, replica_count=DEFAULT_REPLICA_COUNT):
        self.id = uuid.uuid4().hex
        self.name = name
        self.size = size
        self.replica_count = replica_count
        self.chunks = []
        self.create_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        self.parent_dir_id = None

        self.__lock = threading.Lock()

    @classmethod
    def is_dir(cls):
        return False

    @classmethod
    def is_file(cls):
        return True

    def __safe_load(self, obj, attr):
        val = obj.get(attr, None)
        if val is None:
            raise BadMetadata('File %s does not found!'%val)
        return val

    def load(self, file_obj):
        self.parent_dir_id = self.__safe_load(file_obj, 'parent_id')
        self.name = self.__safe_load(file_obj, 'name')
        self.size = self.__safe_load(file_obj, 'size')
        chunks = file_obj.get('chunks', [])
        for chunk in chunks:
            chunk_obj = ChunkMD(**chunk)
            self.chunks.append(chunk_obj)
        self.replica_count = file_obj.get('replica_count', DEFAULT_REPLICA_COUNT)
        create_date = file_obj.get('create_date', None)
        if create_date:
            self.create_date = create_date

        return self

    def dump(self):
        return {'name': self.name,
                'size': self.size,
                'chunks': [c.dump() for c in self.chunks],
                'replica_count': self.replica_count,
                'create_date': self.create_date,
                'parent_id': self.parent_dir_id}

    def append_chunk(self, key, checksum, seek, size):
        self.__lock.acquire()
        try:
            chunk_obj = ChunkMD(**{'key':key, 'checksum': checksum, 'seek': seek, 'size':size})
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
    def __init__(self, name='', dir_id=None):
        self.name = name
        self.content = []
        self.create_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        self.last_modify_date = self.create_date
        self.parent_dir_id = None
        if dir_id is None:
            dir_id = uuid.uuid4().hex
        self.dir_id = dir_id

    @classmethod
    def is_dir(cls):
        return True

    @classmethod
    def is_file(cls):
        return False

    def __safe_load(self, obj, attr):
        val = obj.get(attr, None)
        if val is None:
            raise BadMetadata('Directory %s does not found'%attr)
        return val

    def load(self, dir_obj):
        self.dir_id = self.__safe_load(dir_obj, 'id')
        self.parent_dir_id = self.__safe_load(dir_obj, 'parent_id')
        self.name = self.__safe_load(dir_obj, 'name')
        create_date = dir_obj.get('create_date', None)
        if create_date:
            self.create_date = create_date
        last_mod_date = dir_obj.get('last_modify_date', None)
        if last_mod_date:
            self.last_modify_date = last_mod_date

        return self

    def dump(self):
        #TODO: attr validation should be implemented
        return {'id': self.dir_id,
                'name': self.name,
                'parent_id': self.parent_dir_id,
                'is_dir': True,
                'create_date': self.create_date,
                'last_modify_date': self.last_modify_date}

    def items(self):
        return self.content

    def get(self, item_name):
        for item in self.content:
            if item.name == item_name:
                return item

        raise PathException('"%s" does not found in %s directory'%(item_name, self.name))

    def append(self, item_md):
        if not isinstance(item_md, DirectoryMD) and not isinstance(item_md, FileMD):
            raise Exception('Item cant be appended to directory, bcs it type is equal to "%s"'%item_md)

        try:
            ex_item = self.get(item_md.name)
            if ex_item.is_dir() == item_md.is_dir():
                raise AlreadyExistsException('Item %s is already exists in directory %s'%\
                                                (item_md.name, self.name))
        except PathException:
            pass

        item_md.parent_dir_id = self.dir_id
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



class MDVersion:
    def __init__(self):
        self.__ver_datetime = None
        self.__app_items = []
        self.__rm_items = []

    def empty(self):
        return (not self.__app_items) and (not self.__rm_items)

    def append(self, item):
        self.__app_items.append(item)

    def remove(self, item):
        self.__rm_items.append(item)

    def dump(self):
        ret_lst = []
        for item in self.__app_items:
            ret_lst.append((item.dump(), False))
        for item in self.__rm_items:
            ret_lst.append((item.dump(), True))

        ver_datetime = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        return (ver_datetime, ret_lst)


class MetadataFile:
    def __init__(self):
        self.versions = []
        self.root_dir = DirectoryMD('/', dir_id='')
        self.unsaved_ver = MDVersion()

    def load(self, md_str):
        md_obj = json.loads(md_str)
        self.versions = md_obj.get('versions', [])
        for ver_dt, md_ver in self.versions:
            print 'VERSION: %s'%ver_dt
            for item, is_removed in md_ver:
                if item.get('is_dir', False):
                    item_md = DirectoryMD()
                else:
                    item_md = FileMD()

                item_md.load(item)
                parent = self.find_by_id(item_md.parent_dir_id)
                if is_removed:
                    parent.remove(item_md.name)
                else:
                    parent.append(item_md)

    def save(self):
        if not self.unsaved_ver.empty():
            self.versions.append(self.unsaved_ver.dump())
            self.unsaved_ver = MDVersion()

        d_obj = {'versions': self.versions}

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

    def find_by_id(self, dir_id, start_dir=None):
        if not dir_id:
            return self.root_dir

        if not start_dir:
            start_dir = self.root_dir

        if start_dir.dir_id == dir_id:
            return start_dir

        for item_md in start_dir.items():
            if item_md.is_dir():
                found_id = self.find_by_id(dir_id, item_md)
                if found_id:
                    return found_id

    def exists(self, path):
        try:
            self.find(path)
        except PathException, err:
            return False

        return True


    def append(self, dest_dir, item_md):
        dest_dir_md = self.find(dest_dir)
        dest_dir_md.append(item_md)

        self.unsaved_ver.append(item_md)

    def remove(self, rm_path):
        rm_item_md = self.find(rm_path)
        if rm_item_md.is_dir() and rm_item_md.items():
            raise NotEmptyException('Directory %s is not empty!'%rm_path)

        base_dir = self.find_by_id(rm_item_md.parent_dir_id)
        base_dir.remove(rm_item_md.name)
        self.unsaved_ver.remove(rm_item_md)


    '''
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
    '''

if __name__ == '__main__':
    md = MetadataFile()
    dirmd = DirectoryMD('test_dir')
    md.append('/', dirmd)

    filemd = FileMD('new_file')
    filemd.append_chunk('tttttttt', 'ewwerwerewrwrwr', 0, 123131)
    md.append('/test_dir', filemd)
    md_dump = md.save()

    assert md.exists('/test_dir') == True
    assert md.exists('/test_dir/new_file') == True
    assert md.exists('/test_dir/fake_file') == False
    dirmd = md.find('/test_dir')

    del md
    md = MetadataFile()
    md.load(md_dump)
    md.remove('/test_dir/new_file')
    md.remove('/test_dir')
    print 'metadata size: %s'%len(md.save())
    print md.save()

