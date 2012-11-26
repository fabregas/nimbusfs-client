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
from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection

from datetime import datetime
import wsgidav.util as util
import os
import mimetypes
import shutil
import stat
import tempfile

from id_client.core.metadata import DirectoryMD, FileMD

__docformat__ = "reStructuredText"

#_logger = util.getModuleLogger(__name__)

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
        self.name = self.name.encode("utf8")

        self._filePath = None

    # Getter methods for standard live properties     
    def getContentLength(self):
        return self.file_obj.size

    def getContentType(self):
        return 'application/octet-stream'

    def _to_unix_time(self, date):
        return float(datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ').strftime("%s"))

    def getCreationDate(self):
        return self._to_unix_time(self.file_obj.create_date)

    def getDisplayName(self):
        return self.name

    def getEtag(self):
        return util.getETag(self.file_obj.name)

    def getLastModified(self):
        return self._to_unix_time(self.file_obj.create_date)

    def supportEtag(self):
        return True

    def supportRanges(self):
        return True

    def getContent(self):
        """Open content as a stream for reading.

        See DAVResource.getContent()
        """
        return self.nibbler.load_file(self.file_obj)

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
        if not withErrors:
            self.nibbler.save_file(self._filePath, self.file_obj, \
                        os.path.dirname(self.path).decode('utf8'))

        if self._filePath:
            os.unlink(self._filePath)
            self._filePath = None


    def delete(self):
        """Remove this resource or collection (recursive).

        See DAVResource.delete()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        self.nibbler.remove_file(self.path.decode('utf8'))

        self.removeAllProperties(True)
        self.removeAllLocks(True)


    def copyMoveSingle(self, destPath, isMove):
        """See DAVResource.copyMoveSingle() """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        assert not util.isEqualOrChildUri(self.path, destPath)
        if isMove:
            self.nibbler.move(self.path.rstrip('/').decode('utf8'), destPath.rstrip('/').decode('utf8'))
        else:
            self.nibbler.copy(self.path.rstrip('/').decode('utf8'), destPath.rstrip('/').decode('utf8'))


    def supportRecursiveMove(self, destPath):
        """Return True, if moveRecursive() is available (see comments there)."""
        return True


    def moveRecursive(self, destPath):
        """See DAVResource.moveRecursive() """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        assert not util.isEqualOrChildUri(self.path, destPath)

        self.nibbler.move(self.path.rstrip('/').decode('utf8'), destPath.rstrip('/').decode('utf8'))


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
        self.name = os.path.basename(self.dir_obj.name)
        self.name = self.name.encode("utf8")


    # Getter methods for standard live properties     

    def _to_unix_time(self, date):
        return float(datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ').strftime("%s"))

    def getCreationDate(self):
        return self._to_unix_time(self.dir_obj.create_date)

    def getDisplayName(self):
        return self.name

    def getDirectoryInfo(self):
        return None

    def getEtag(self):
        return None

    def getLastModified(self):
        return self._to_unix_time(self.dir_obj.last_modify_date)

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

        for name, is_file in self.dir_obj.items():
            name = name.encode("utf8")
            nameList.append(name)

        return nameList

    def getMember(self, name):
        """Return direct collection member (DAVResource or derived).

        See DAVCollection.getMember()
        """
        r_obj = self.dir_obj.get(name.decode("utf8"))

        path = util.joinUri(self.path, name)
        if r_obj.is_dir():
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
        file_md = FileMD(name.decode('utf8'))
        self.dir_obj.append(file_md)

        return self.provider.getResourceInst(path, self.environ)


    def createCollection(self, name):
        """Create a new collection as member of self.

        See DAVResource.createCollection()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        dir_md = DirectoryMD(name.decode('utf8'))
        self.dir_obj.append(dir_md)


    def delete(self):
        """Remove this resource or collection (recursive).

        See DAVResource.delete()
        """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        self.nibbler.rmdir(self.path.rstrip('/').decode('utf8'), recursive=True)

        self.removeAllProperties(True)
        self.removeAllLocks(True)


    def copyMoveSingle(self, destPath, isMove):
        """See DAVResource.copyMoveSingle() """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        assert not util.isEqualOrChildUri(self.path, destPath)
        if isMove:
            self.nibbler.move(self.path.rstrip('/').decode('utf8'), destPath.rstrip('/').decode('utf8'))
        else:
            self.nibbler.copy(self.path.rstrip('/').decode('utf8'), destPath.rstrip('/').decode('utf8'))


    def supportRecursiveMove(self, destPath):
        """Return True, if moveRecursive() is available (see comments there)."""
        return True


    def moveRecursive(self, destPath):
        """See DAVResource.moveRecursive() """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)

        assert not util.isEqualOrChildUri(self.path, destPath)

        self.nibbler.move(self.path.rstrip('/').decode('utf8'), destPath.rstrip('/').decode('utf8'))



#===============================================================================
# FabnetProvider
#===============================================================================
class FabnetProvider(DAVProvider):
    def __init__(self, nibbler):
        super(FabnetProvider, self).__init__()
        self.nibbler = nibbler
        self.readonly = False

    def getResourceInst(self, path, environ):
        """Return info dictionary for path.

        See DAVProvider.getResourceInst()
        """
        self._count_getResourceInst += 1
        fp = util.toUnicode(path.rstrip("/"))
        r_obj = self.nibbler.get_resource(fp)

        if r_obj is None:
            return None

        if r_obj.is_dir():
            return FolderResource(self.nibbler, path, environ, r_obj)

        return FileResource(self.nibbler, path, environ, r_obj)
