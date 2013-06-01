#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.utils
@author Konstantin Andrusenko
@date May 31, 2013
"""

import sys
import subprocess

DETACHED_PROCESS = 8 #flag for win32

def Subprocess(argv, **params):
    stdout = params.get('stdout', subprocess.PIPE)
    stderr = params.get('stderr', subprocess.PIPE)
    env = params.get('env', {})
    if sys.platform != 'win32':
        flags = 0
        if params.get('daemon', False):
            argv = 'nohup %s &'%argv
    else:
        flags = DETACHED_PROCESS



    return subprocess.Popen(argv.split(), stdout=stdout, stderr=stderr, env=env, creationflags=flags)
