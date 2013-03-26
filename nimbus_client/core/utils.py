#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.utils
@author Konstantin Andrusenko
@date March 20, 2013
"""

def to_str(val):
    if type(val) == unicode:
        return val.encode('utf8')
    return val
