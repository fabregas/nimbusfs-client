import struct
import threading
import time
import zlib
from datetime import datetime

from nimbus_client.core.exceptions import *

MAX_B = pow(2, struct.calcsize('<B')*8)-1
MAX_L = pow(2, struct.calcsize('<L')*8)-1
MAX_Q = pow(2, struct.calcsize('<Q')*8)-1

MO_APPEND = 1
MO_REMOVE = 0


DEFAULT_REPLICA_COUNT = 2

class SafeDict:
    def __init__(self, dict_obj={}):
        self.__dict_obj = dict_obj
        self.__lock = threading.RLock()

    def __setitem__(self, key, value):
        self.__lock.acquire()
        try:
            self.__dict_obj[key] = value
        finally:
            self.__lock.release()

    def __getitem__(self, key):
        self.__lock.acquire()
        try:
            return self.__dict_obj.get(key, None)
        finally:
            self.__lock.release()

    def __repr__(self):
        self.__lock.acquire()
        try:
            ret = []
            for key, value in self.__dict_obj.items():
                ret.append('%s=%s'%(key, value))
            return '{%s}'%', '.join(ret)
        finally:
            self.__lock.release()



class AbstractMetadataObject(object):
    #metadata objects labels
    MOL_FILE = 1
    MOL_DIR = 2
    def __init__(self, dumped_md=None, **kw_args):
        self._args = kw_args
        if dumped_md:
            self.load(dumped_md)
        self.on_init()

    def on_init(self):
        pass

    def __repr__(self):
        return '[%s] %s'%(self.__class__.__name__, self._args)

    def __str__(self):
        return self.__repr__()

    def __unicode__(self):
        return self.__repr__()

    def __getattr__(self, attr):
        return self._args.get(attr, None)

    def __setattr__(self, attr, value):
        if attr.startswith('_'):
            object.__setattr__(self, attr, value)
            return
        self._args[attr] = value

    def copy(self):
        c_args = copy.copy(self._args)
        c_obj = self.__class__(**c_args)
        c_obj.set_addr(self.__md_addr)
        return c_obj

    def dump(self, is_local=False, recursive=False):
        raise Exception('Not implemented')

    def load(self, dumped):
        raise Exception('Not implemented')

    @classmethod
    def load_md(cls, dumped):
        md_obj_label = ord(dumped[0])
        if md_obj_label == cls.MOL_FILE:
            md = FileMD()
        elif md_obj_label == cls.MOL_DIR:
            md = DirectoryMD()
        else:
            raise Exception('Unknown metadata label "%s"'%md_obj_label)
        md.load(dumped)
        return md


class ChunkMD(AbstractMetadataObject):
    DUMP_STRUCT = '<20s20sQL'
    MIN_DUMP_LEN = struct.calcsize(DUMP_STRUCT)

    def validate(self):
        if self.checksum is None:
            raise MDValidationError('Checksum is empty')
        if self.seek is None:
            raise MDValidationError('Seek is empty')
        if self.size is None:
            raise MDValidationError('ChunkMD: Size is empty')
        if self.seek < 0 or self.seek > MAX_Q:
            raise MDValidationError('Seek %s is out of supported range [0..%s]'%(self.seek, MAX_Q))
        if self.size < 0 or self.size > MAX_L:
            raise MDValidationError('Chunk size %s is out of supported range [0..%s]'%(self.size, MAX_L))

    def dump(self, is_local=False, recursive=False):
        self.validate()
        try:
            if not self.key:
                key = ''
            else:
                key = self.key.decode('hex')
        except TypeError:
            raise MDValidationError('Invalid key "%s"'%self.key)
        try:
            checksum = self.checksum.decode('hex')
        except TypeError:
            raise MDValidationError('Invalid checksum "%s"'%self.checksum)

        dumped = struct.pack(self.DUMP_STRUCT, key, checksum, self.seek, self.size)
        if is_local and self.local_key:
            try:
                dumped += self.local_key.decode('hex')
            except TypeError:
                raise MDValidationError('Invalid local key "%s"'%self.local_key)

        return dumped

    def load(self, dumped):
        size = self.MIN_DUMP_LEN
        if len(dumped) < size:
            raise MDIivalid('Invalid chunks MD size %s'%len(dumped))
        key, checksum, self.seek, self.size = struct.unpack(self.DUMP_STRUCT, dumped[:size])
        self.checksum = checksum.encode('hex')
        if key == '\x00'*20:
            self.key = None
        else:
            self.key = key.encode('hex')
        if len(dumped) == size+20:
            self.local_key = dumped[size:].encode('hex')



class FileMD(AbstractMetadataObject):
    HDR_STRUCT = '<BBLQBLQ'
    HDR_LEN = struct.calcsize(HDR_STRUCT)

    @classmethod
    def is_dir(cls):
        return False

    @classmethod
    def is_file(cls):
        return True

    def validate(self):
        if not self.size:
            raise MDValidationError('FileMD: Size is empty')
        if self.parent_dir_id is None:
            raise MDValidationError('ParentDirID is empty')
        if not self.name:
            raise MDValidationError('FileName is empty')
        if not self.chunks:
            raise MDValidationError('Chunks is empty')

        if self.item_id < 0 or self.item_id > MAX_L:
            raise MDValidationError('File id %s is out of supported range [0..%s]'%(self.item_id, MAX_L))
        if self.replica_count < 0 or self.replica_count > MAX_B:
            raise MDValidationError('Replica count %s is out of supported range [0..%s]'%(self.seek, MAX_B))
        if self.size < 0 or self.size > MAX_Q:
            raise MDValidationError('File size %s is out of supported range [0..%s]'%(self.size, MAX_Q))
        if self.parent_dir_id < 0 or self.parent_dir_id > MAX_L:
            raise MDValidationError('File parent dir id %s is out of supported range [0..%s]'%(self.parent_dir_id, MAX_L))

    def on_init(self):
        if not self.replica_count:
            self.replica_count = DEFAULT_REPLICA_COUNT
        if not self.create_date:
            self.create_date = int(time.mktime(datetime.now().timetuple()))
        if self.chunks is None:
            self.chunks = []

    def dump(self, is_local=False, recursive=False):
        self.validate()
        fname = self.name.encode('utf8')
        fname_len = len(fname)
        if fname_len < 1 or fname_len > MAX_B:
            raise MDValidationError('File name length should be in range [1..%s], but "%s" occured'%(MAX_B, fname))

        dump = struct.pack(self.HDR_STRUCT, AbstractMetadataObject.MOL_FILE, fname_len, self.item_id, \
                self.size, self.replica_count, self.parent_dir_id, self.create_date)
        dump += fname
        for chunk in self.chunks:
            ch_dump = chunk.dump(is_local)
            dump += '%s%s'%(chr(len(ch_dump)), ch_dump)
        return dump

    def load(self, dumped):
        if len(dumped) < self.HDR_LEN:
            raise MDIivalid('Invalid file MD dump size %s'%len(dumped))

        file_label, f_name_len, self.item_id, self.size, self.replica_count, \
            self.parent_dir_id, self.create_date = \
            struct.unpack(self.HDR_STRUCT, dumped[:self.HDR_LEN])

        f_name = dumped[self.HDR_LEN: self.HDR_LEN+f_name_len]
        self.name = f_name.decode('utf8')
        seek = self.HDR_LEN+f_name_len
        while seek < len(dumped):
            chunk_len = ord(dumped[seek])
            seek += 1
            chunk_dump = dumped[seek:seek+chunk_len]
            chunk = ChunkMD(dumped_md=chunk_dump)
            self.append_chunk(chunk)
            seek += chunk_len

    def append_chunk(self, chunk):
        if self.chunks is None:
            self.chunks = []
        self.chunks.append(chunk)

    def chunks_stat(self):
        foreign_chunks = local_chunks = 0
        for chunk in self.chunks:
            if chunk.key:
                foreign_chunks += 1
            if chunk.local_key:
                local_chunks += 1
        return local_chunks, foreign_chunks



class DirItem:
    def __init__(self, item):
        self.__items = [item]

    def __iter__(self):
        for item in self.__items:
            yield item

    def to_str(self, val):
        if type(val) == unicode:
            return val.encode('utf8')
        return val

    def get_by_name(self, item_name):
        for item in self.__items:
            if self.to_str(item.name) == self.to_str(item_name):
                return item
        return None

    def append(self, item):
        ex_item = self.get_by_name(item.name)
        if ex_item:
            return False
        self.__items.append(item)
        return True

    def remove(self, item_name):
        ret_i = None
        for i, item in enumerate(self.__items):
            if self.to_str(item.name) == self.to_str(item_name):
                ret_i = i
                break
        del self.__items[ret_i]

    def empty(self):
        return len(self.__items) == 0


class DirectoryMD(AbstractMetadataObject):
    HDR_STRUCT = '<BBLLQQ'
    HDR_LEN = struct.calcsize(HDR_STRUCT)
    ITEM_HDR_STRUCT = '<IB'
    ITEM_HDR_LEN = struct.calcsize(ITEM_HDR_STRUCT)

    @classmethod
    def is_dir(cls):
        return True

    @classmethod
    def is_file(cls):
        return False

    def __update_modify_date(self):
        self.last_modify_date = int(time.mktime(datetime.now().timetuple()))

    def __hash(self, str_data):
        return zlib.adler32(str_data)

    def on_init(self):
        if not self.create_date:
            self.create_date = int(time.mktime(datetime.now().timetuple()))
        if not self.last_modify_date:
            self.__update_modify_date()
        if not self.content:
            self.content = {}

    def validate(self):
        if not self.name:
            raise MDValidationError('DirectoryName is empty')
        if not self.item_id:
            raise MDValidationError('DirID is empty')
        if self.parent_dir_id is None:
            raise MDValidationError('ParentDirID is empty')

        if self.item_id < 0 or self.item_id > MAX_L:
            raise MDValidationError('Directory id %s is out of supported range [0..%s]'%(self.item_id, MAX_L))
        if self.parent_dir_id < 0 or self.parent_dir_id > MAX_L:
            raise MDValidationError('Directory parent id %s is out of supported range [0..%s]'%(self.parent_dir_id, MAX_L))

    def dump(self, is_local=False, recursive=False):
        self.validate()
        dname = self.name.encode('utf8')
        dname_len = len(dname)
        if dname_len < 1 or dname_len > MAX_B:
            raise MDValidationError('Directory name length should be in range [1..%s], but "%s" occured'%(MAX_B, dname))
        dump = struct.pack(self.HDR_STRUCT, AbstractMetadataObject.MOL_DIR, dname_len, self.item_id, \
                self.parent_dir_id, self.create_date, self.last_modify_date)
        dump += dname

        if recursive:
            for dir_item in self.content.values():
                for item in dir_item:
                    im_dump = item.dump(is_local, recursive)
                    dump += '%s%s'%(struct.pack(self.ITEM_HDR_STRUCT, len(im_dump), int(item.is_file())), im_dump)

        return dump

    def load(self, dumped):
        if len(dumped) < self.HDR_LEN:
            raise MDIivalid('Invalid directory MD dump size %s'%len(dumped))

        dir_label, d_name_len, self.item_id, self.parent_dir_id, \
            self.create_date, self.last_modify_date = \
            struct.unpack(self.HDR_STRUCT, dumped[:self.HDR_LEN])
        d_name = dumped[self.HDR_LEN: self.HDR_LEN+d_name_len]
        self.name = d_name.decode('utf8')

        seek = self.HDR_LEN+d_name_len
        ss = self.ITEM_HDR_LEN
        self.content = {}
        while seek < len(dumped):
            item_len, is_file = struct.unpack(self.ITEM_HDR_STRUCT, dumped[seek:seek+ss])
            seek += ss
            item_dump = dumped[seek:seek+item_len]
            if is_file:
                i_class = FileMD
            else:
                i_class = DirectoryMD

            item = i_class(dumped_md=item_dump)
            self.append(item)
            seek += item_len

    def iteritems(self):
        for item in self.content.values():
            for subitem in item:
                yield subitem

    def get(self, item_name):
        item = None
        if self.content:
            f_hash = self.__hash(item_name)
            item_o = self.content.get(f_hash, None)
            if item_o:
                item = item_o.get_by_name(item_name)

        if not item:
            raise PathException('"%s" does not found in %s directory'%(item_name, self.name))

        return item

    def append(self, item_md):
        if not isinstance(item_md, AbstractMetadataObject):
            raise TypeError('Item cant be appended to directory, bcs it type is equal to "%s"'%item_md.__class__.__name__)

        f_hash = self.__hash(item_md.name)
        item_o = self.content.get(f_hash, None)
        if item_o:
            if not item_o.append(item_md):
                raise AlreadyExistsException('Item %s is already exists in directory %s'%\
                                            (item_md.name, self.name))
        else:
            item_o = DirItem(item_md)
            self.content[f_hash] = item_o

        item_md.parent_dir_id = self.item_id
        self.__update_modify_date()

    def empty(self):
        if not self.content:
            return True
        return False

    def remove(self, item_name):
        try:
            ex_item = self.get(item_name)
        except PathException:
            #item not found
            return

        f_hash = self.__hash(item_name)
        item_o = self.content.get(f_hash, None)
        if not item_o:
            raise PathException('No item %s in directory %s'%(item_name, self.name))

        item_o.remove(item_name)
        if item_o.empty():
            del self.content[f_hash]
        self.__update_modify_date()



class Metadata:
    MD_DUMP_HDR_STRUCT = '<Q'
    MD_DUMP_HDR_LEN = struct.calcsize(MD_DUMP_HDR_STRUCT)

    MD_DUMP_NAME = 'metadata.dump'

    def __init__(self, cache_dir, journal):
        self.__journal = journal
        self.__cache_dir = cache_dir

        self.__lock = threading.RLock()
        self.__last_dir_id = 0
        self.__last_saved_transaction = None
        self.__root_dir = DirectoryMD(dir_id=0)

        self.__init_meta()

    def dump(self):
        md_dump_file = os.path.join(self.__cache_dir, MD_DUMP_NAME)
        md_dump_db = DataBlock(md_dump_file)
        md_dump_db.write(self.__root_dir.dump(recursive=True))

    def __init_meta(self):
        md_dump_file = os.path.join(self.__cache_dir, MD_DUMP_NAME)
        if os.path.exists(md_dump_file):
            md_dump_db = DataBlock(md_dump_file)
            md_dump = md_dump_db.read()
            self.__last_saved_transaction = struct.unpack(self.MD_DUMP_HDR_STRUCT,
                                                    md_dump[:self.MD_DUMP_HDR_LEN])
            self.__root_dir.load(md_dump[self.MD_DUMP_HDR_LEN:])

        self.__restore_journal()

    def __restore_journal(self):
        for j_oper, j_item in self.__journal.iteritems(self.__last_saved_transaction):
            self.__apply_j_item(j_oper, j_item)

        for j_oper, j_item in self.__journal.iter_unsaved():
            self.__apply_j_item(j_oper, j_item)

    def __apply_j_item(self, j_oper, j_item):
        if j_oper == MO_APPEND:
            if j_item.is_dir():
                self.__last_dir_id = j_item.item_id

            self.append(j_item)
        elif j_oper == MO_UPDATE:
            self.update(j_item)
        elif j_oper == MO_REMOVE:
            self.remove(j_item)
        else:
            raise MDIivalid('Unknown journal operation type: %s'%j_oper)

    def __find_by_id(self, dir_id, start_dir=None):
        if not dir_id:
            return self.root_dir

        if not start_dir:
            start_dir = self.root_dir

        if start_dir.dir_id == dir_id:
            return start_dir

        for item_md in start_dir.items():
            if item_md.is_dir():
                found_id = self.__find_by_id(dir_id, item_md)
                if found_id:
                    return found_id

    def find(self, path):
        self.__lock.acquire()
        try:
            items = path.split('/')
            cur_item = self.__root_dir
            for item_name in items:
                if not item_name:
                    continue

                if not cur_item.is_dir():
                    raise PathException('Path "%s" does not found!'%path)

                cur_item = cur_item.get(item_name)
            return cur_item.copy()
        finally:
            self.__lock.release()

    def mkdir(self, dir_name):
        self.__lock.acquire()
        try:
            self.__last_dir_id += 1
            dir_id = self.__last_dir_id
        finally:
            self.__lock.release()

        return DirectoryMD(dir_id=dir_id, name=dir_name)

    def exists(self, path):
        try:
            self.find(path)
        except PathException, err:
            return False
        return True

    def append(self, dest_dir, item_md):
        self.__lock.acquire()
        try:
            dest_dir_md = self.find(dest_dir)
            n_item_md = item_md.copy()
            dest_dir_md.append(n_item_md)

            self.journal.add_to_transaction(MO_APPEND, n_item_md)
        finally:
            self.__lock.release()

        '''
        self.__lock.acquire()
        try:
            self.__unsaved_items.append((MO_APPEND, item_md))
        finally:
            self.__lock.release()
        '''

    def update(self, item_md):
        self.__lock.acquire()
        try:
            parent_dir_id = item_md.parent_dir_id
            if parent_dir_id is None:
                raise NimbusException('metadata object does not initialized!')

            base_dir = self.__find_by_id(parent_dir_id)
            c_item_md = base_dir.get(item_md.name)
            c_item_md.update(item_md)

            self.journal.add_to_transaction(MO_UPDATE, c_item_md)
        finally:
            self.__lock.release()

    def remove(self, rm_path):
        self.__lock.acquire()
        try:
            rm_item_md = self.find(rm_path)
            if rm_item_md.is_dir() and not rm_item_md.empty():
                raise NotEmptyException('Directory %s is not empty!'%rm_path)

            base_dir = self.__find_by_id(rm_item_md.parent_dir_id)
            base_dir.remove(rm_item_md.name)

            self.journal.add_to_transaction(MO_REMOVE, item_md)
        finally:
            self.__lock.release()

        '''
        self.__lock.acquire()
        try:
            self.__unsaved_items.append((MO_REMOVE, rm_item_md))
        finally:
            self.__lock.release()
        '''
    '''
    def save(self):
        self.__lock.acquire()
        try:
            self.__journal.transaction(self.__unsaved_items)
            self.__unsaved_items = []
        finally:
            self.__lock.release()
    '''
