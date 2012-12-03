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
import wsgidav.util as util
import os
import tempfile
import threading

from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection


from nimbus_client.core.nibbler import FSItem, PathException

__docformat__ = "reStructuredText"

#logger = util.getModuleLogger(__name__)

BUFFER_SIZE = 8192


#===============================================================================
# FileResource
#===============================================================================
class FileResource(DAVNonCollection):
    """Represents a single existing DAV resource instance.

    See also _DAVResource, DAVNonCollection, and FilesystemProvider.
    """
    def __init__(self, nibbler, path, environ, file_obj):
        super(FileResource, self).__init__(path, environ)
        self.nibbler = nibbler
        self.file_obj = file_obj

        # Setting the name from the file path should fix the case on Windows
        self.name = os.path.basename(file_obj.name)
        self.name = self.name

        self._filePath = None

    # Getter methods for standard live properties     
    def getContentLength(self):
        return self.file_obj.size

    def getContentType(self):
        return 'application/octet-stream'

    def _to_unix_time(self, date):
        return float(datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ').strftime("%s"))

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
        out_file = tempfile.NamedTemporaryFile(prefix='nibbler-download-%s-'%self.file_obj.name)
        op_id = self.nibbler.load_file(self.path, out_file.name)
        self.nibbler.wait_async_operation(op_id)
        return out_file

    def beginWrite(self, contentType=None):
        """Open content as a stream for writing.

        See DAVResource.beginWrite()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        f_idx, tmpfl = tempfile.mkstemp(prefix='nibbler-upload')
        f_obj = os.fdopen(f_idx, "wb")
        self._filePath = tmpfl
        return f_obj

    def endWrite(self, withErrors):
        """Called when PUT has finished writing.

        This is only a notification. that MAY be handled.
        """
        def callback(error):
            if self._filePath:
                os.unlink(self._filePath)
                self.provider.clearVirtualResource(self.path)
                self._filePath = None

        if not withErrors:
            if os.path.getsize(self._filePath) == 0:
                os.unlink(self._filePath)
                return

            id = self.nibbler.save_file(self._filePath, self.file_obj.name, \
                        os.path.dirname(self.path), callback)
            #self.nibbler.wait_async_operation(id)
        else:
            callback(None)


    def delete(self):
        """Remove this resource or collection (recursive).

        See DAVResource.delete()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        if self.provider.getVirtualResource(self.path):
            self.provider.clearVirtualResource(self.path)
        else:
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
        self.path = os.path.normpath(path)
        self.name = os.path.basename(self.path)
        #self.name = self.name.encode("utf8")


    # Getter methods for standard live properties     

    def _to_unix_time(self, date):
        return float(datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ').strftime("%s"))

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
            name = item.name.encode('utf8')
            nameList.append(name)

        return nameList

    def getMember(self, name):
        """Return direct collection member (DAVResource or derived).

        See DAVCollection.getMember()
        """
        path = util.joinUri(self.path, name)
        r_obj = self.nibbler.find(path)
        if r_obj is None:
            raise Exception('Member "%s" does not found in %s'%(name, self.path))

        if r_obj.is_dir:
            res = FolderResource(self.nibbler, path, self.environ, r_obj)
        else:
            res = FileResource(self.nibbler, path, self.environ, r_obj)

        return res



    # --- Read / write ---------------------------------------------------------
    def createEmptyResource(self, name):
        """Create an empty (length-0) resource.

        See DAVResource.createEmptyResource()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        if name.startswith('.'):
            raise DAVError(HTTP_FORBIDDEN)

        path = util.joinUri(self.path, name)
        file_info = self.provider.createVirtualResource(path)
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

        self.nibbler.move(self.path.rstrip('/'), destPath.rstrip('/'))



#===============================================================================
# FabnetProvider
#===============================================================================
class FabnetProvider(DAVProvider):
    def __init__(self, nibbler):
        super(FabnetProvider, self).__init__()
        self.nibbler = nibbler
        self.readonly = False
        self.__lock = threading.Lock()
        self.__virtual_resources = {}

    def getResourceInst(self, path, environ):
        """Return info dictionary for path.

        See DAVProvider.getResourceInst()
        """
        self._count_getResourceInst += 1
        #fp = util.toUnicode(path.rstrip("/"))

        r_obj = self.nibbler.find(path)

        if r_obj is None:
            r_obj = self.getVirtualResource(path)

        if r_obj is None:
            return None

        if r_obj.is_dir:
            return FolderResource(self.nibbler, path, environ, r_obj)

        return FileResource(self.nibbler, path, environ, r_obj)

    def createVirtualResource(self, path):
        item = FSItem(os.path.basename(path), False)
        self.__lock.acquire()
        try:
            self.__virtual_resources[path] = item
        finally:
            self.__lock.release()

        return item

    def getVirtualResource(self, path):
        self.__lock.acquire()
        try:
            return self.__virtual_resources.get(path, None)
        finally:
            self.__lock.release()

    def clearVirtualResource(self, path):
        self.__lock.acquire()
        try:
            if self.__virtual_resources.has_key(path):
                del self.__virtual_resources[path]
        finally:
            self.__lock.release()
