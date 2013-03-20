#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.exceptions
@author Konstantin Andrusenko
@date November 28, 2012
"""

class NimbusException(Exception):
    pass


class BadMetadata(NimbusException):
    def __init__(self, msg):
        NimbusException.__init__(self, 'Bad metadata. %s'%msg)

class MDValidationError(BadMetadata):
    pass

class MDIivalid(BadMetadata):
    pass


class PathException(NimbusException):
    pass

class NotEmptyException(NimbusException):
    pass

class NoMetadataException(NimbusException):
    pass

class NotDirectoryException(NimbusException):
    pass

class NotFileException(NimbusException):
    pass

class AlreadyExistsException(NimbusException):
    pass

class NotEmptyException(NimbusException):
    pass

class LocalPathException(NimbusException):
    pass

class TimeoutException(NimbusException):
    pass

class NoJournalFoundException(NimbusException):
    pass

class ClosedFileException(NimbusException):
    pass

class IOException(NimbusException):
    pass

class NotFoundException(NimbusException):
    pass
