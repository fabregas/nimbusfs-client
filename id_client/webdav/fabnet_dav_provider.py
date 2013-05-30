#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package webdav_server.fabnet_dav_provider
@author Konstantin Andrusenko
@date November 25, 2012

This module contains the implementation of fabner DAV provider
"""
from datetime import datetime
import time
import wsgidav.util as util
import os
import threading

from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection


from nimbus_client.core.nibbler import FSItem, PathException
from cache_fs import CacheFS

__docformat__ = "reStructuredText"

logger = util.getModuleLogger(__name__)

BUFFER_SIZE = 8192

class EmptyFileObject:
    def write(self, data):
        raise RuntimeError('EmptyFileObject can not provide write() method')

    def read(self, dummy):
        return ''

    def seek(self, dummy):
        pass

    def close(self):
        pass


    

#===============================================================================
# FileResource
#===============================================================================
class FileResource(DAVNonCollection):
    """Represents a single existing DAV resource instance.

    See also _DAVResource, DAVNonCollection, and FilesystemProvider.
    """
    def __init__(self, nibbler, path, environ, file_obj, virtual=False):
        super(FileResource, self).__init__(path, environ)
        self.nibbler = nibbler
        self.file_obj = file_obj

        # Setting the name from the file path should fix the case on Windows
        self.virtual_res = virtual
        self.name = os.path.basename(file_obj.name)
        self.name = self.name

        self._file_obj = None

    # Getter methods for standard live properties     
    def getContentLength(self):
        return self.file_obj.size

    def getContentType(self):
        return 'application/octet-stream'

    def _to_unix_time(self, date):
        return time.mktime(date.timetuple())

    def getCreationDate(self):
        return self._to_unix_time(self.file_obj.create_dt)

    def getDisplayName(self):
        return self.name

    def getEtag(self):
        return util.getETag(self.file_obj.name)

    def getLastModified(self):
        return self._to_unix_time(self.file_obj.create_dt)

    def supportEtag(self):
        return True

    def supportRanges(self):
        return True

    def getContent(self):
        """Open content as a stream for reading.

        See DAVResource.getContent()
        """
        if self.virtual_res:
            return EmptyFileObject()
        return self.nibbler.open_file(self.path)

    def beginWrite(self, contentType=None):
        """Open content as a stream for writing.

        See DAVResource.beginWrite()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        self._file_obj = self.nibbler.open_file(self.path, for_write=True)
        return self._file_obj

    def endWrite(self, withErrors):
        """Called when PUT has finished writing.

        This is only a notification. that MAY be handled.
        """
        #if withErrors or self._file_obj.get_seek()>0:
        self.provider.cache_fs.remove(self.path)

    def delete(self):
        """Remove this resource or collection (recursive).

        See DAVResource.delete()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        self.provider.cache_fs.remove(self.path)
        if self.nibbler.find(self.path):
            self.nibbler.remove_file(self.path)

        self.removeAllProperties(True)
        self.removeAllLocks(True)


    def copyMoveSingle(self, destPath, isMove):
        """See DAVResource.copyMoveSingle() """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        assert not util.isEqualOrChildUri(self.path, destPath)
        if isMove:
            self.nibbler.move(self.path.rstrip('/'), destPath.rstrip('/'))
        else:
            self.nibbler.copy(self.path.rstrip('/'), destPath.rstrip('/'))


    def supportRecursiveMove(self, destPath):
        """Return True, if moveRecursive() is available (see comments there)."""
        return True


    def moveRecursive(self, destPath):
        """See DAVResource.moveRecursive() """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        assert not util.isEqualOrChildUri(self.path, destPath)

        self.nibbler.move(self.path.rstrip('/'), destPath.rstrip('/'))


#===============================================================================
# FolderResource
#===============================================================================
class FolderResource(DAVCollection):
    """Represents a single existing file system folder DAV resource.

    See also _DAVResource, DAVCollection, and FilesystemProvider.
    """
    def __init__(self, nibbler, path, environ, dir_obj):
        super(FolderResource, self).__init__(path, environ)

        self.nibbler = nibbler
        self.dir_obj = dir_obj

        # Setting the name from the file path should fix the case on Windows
        self.path = path
        self.name = os.path.basename(self.path)
        #self.name = self.name.encode("utf8")


    # Getter methods for standard live properties     
    def _to_unix_time(self, date):
        return time.mktime(date.timetuple())

    def getCreationDate(self):
        return self._to_unix_time(self.dir_obj.create_dt)

    def getDisplayName(self):
        return self.name

    def getDirectoryInfo(self):
        return None

    def getEtag(self):
        return None

    def getLastModified(self):
        return self._to_unix_time(self.dir_obj.modify_dt)

    def getMemberNames(self):
        """Return list of direct collection member names (utf-8 encoded).

        See DAVCollection.getMemberNames()
        """
        # On Windows NT/2k/XP and Unix, if path is a Unicode object, the result 
        # will be a list of Unicode objects. 
        # Undecodable filenames will still be returned as string objects    
        # If we don't request unicode, for example Vista may return a '?' 
        # instead of a special character. The name would then be unusable to
        # build a distinct URL that references this resource.

        nameList = []

        for item in self.nibbler.listdir(self.path):
            name = item.name
            nameList.append(name)

        for item in self.provider.cache_fs.get_dir_content(self.path):
            if item not in nameList:
                nameList.append(item)

        #this magic does not allow load the whole content for crazy Finder on MacOS
        magic_files = ['.ql_disablecache', '.ql_disablethumbnails']
        if nameList:
            for magic_file in magic_files:
                if magic_file not in nameList:
                    f_obj = FSItem(magic_file, is_dir=False) 
                    self.provider.cache_fs.put(os.path.join(self.path, magic_file), f_obj)
                    nameList.append(magic_file)

        return nameList

    def getMember(self, name):
        """Return direct collection member (DAVResource or derived).

        See DAVCollection.getMember()
        """
        path = util.joinUri(self.path, name)

        return self.provider.getResourceInst(path, self.environ)


    # --- Read / write ---------------------------------------------------------
    def createEmptyResource(self, name):
        """Create an empty (length-0) resource.

        See DAVResource.createEmptyResource()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        #if name.startswith('.'):
        #    raise DAVError(HTTP_FORBIDDEN)

        path = util.joinUri(self.path, name)
        f_obj = FSItem(name, is_dir=False) 
        self.provider.cache_fs.put(path, f_obj)
        return self.provider.getResourceInst(path, self.environ)


    def createCollection(self, name):
        """Create a new collection as member of self.

        See DAVResource.createCollection()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        path = util.joinUri(self.path, name)
        self.nibbler.mkdir(path)


    def delete(self):
        """Remove this resource or collection (recursive).

        See DAVResource.delete()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        self.nibbler.rmdir(self.path.rstrip('/'), recursive=True)

        self.removeAllProperties(True)
        self.removeAllLocks(True)


    def copyMoveSingle(self, destPath, isMove):
        """See DAVResource.copyMoveSingle() """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        assert not util.isEqualOrChildUri(self.path, destPath)
        if isMove:
            self.nibbler.move(self.path.rstrip('/'), destPath.rstrip('/'))
        else:
            self.nibbler.copy(self.path.rstrip('/'), destPath.rstrip('/'))


    def supportRecursiveMove(self, destPath):
        """Return True, if moveRecursive() is available (see comments there)."""
        return True


    def moveRecursive(self, destPath):
        """See DAVResource.moveRecursive() """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        assert not util.isEqualOrChildUri(self.path, destPath)

        try:
            self.nibbler.move(self.path.rstrip('/'), destPath.rstrip('/'))
        except Exception, err:
            logger.error('copyMoveSingle %s %s : %s'%(self.path, destPath, err))



#===============================================================================
# FabnetProvider
#===============================================================================
class FabnetProvider(DAVProvider):
    def __init__(self, nibbler):
        super(FabnetProvider, self).__init__()
        self.nibbler = nibbler
        self.cache_fs = CacheFS()
        self.readonly = False
        self.__lock = threading.Lock()
        self.__virtual_resources = {}

    def getResourceInst(self, path, environ):
        """Return info dictionary for path.

        See DAVProvider.getResourceInst()
        """
        self._count_getResourceInst += 1

        is_virt = True
        r_obj = self.cache_fs.get(path)
        if not r_obj:
            r_obj = self.nibbler.find(path)
            if r_obj is None:
                return None
            is_virt = False

        if r_obj.is_dir:
            return FolderResource(self.nibbler, path, environ, r_obj)

        return FileResource(self.nibbler, path, environ, r_obj, is_virt)

