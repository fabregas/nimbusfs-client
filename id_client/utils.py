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
    with_input = params.get('with_input', False)
    stdin = None
    if with_input:
        stdin = subprocess.PIPE
    stdout = params.get('stdout', subprocess.PIPE)
    stderr = params.get('stderr', subprocess.PIPE)
    shell = params.get('shell', False)
    env = params.get('env', None)
    if sys.platform != 'win32':
        flags = 0
        if params.get('daemon', False):
            argv = 'nohup %s &'%argv
    else:
        flags = DETACHED_PROCESS

    return subprocess.Popen(argv.split(), stdout=stdout, stderr=stderr, \
            stdin=stdin, env=env, creationflags=flags, shell=shell)
