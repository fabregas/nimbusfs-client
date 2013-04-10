#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.base_external_api
@author Konstantin Andrusenko
@date April 23, 2013

This module contains the implementation of IdepositboxClient class
"""
import threading

class BaseExternalAPI(threading.Thread):
    def __init__(self, nibbler):
        threading.Thread.__init__(self)
        self.nibbler = nibbler

    def run(self):
        pass

    def stop(self):
        pass

    def get_name(self):
        pass

    def get_start_waittime(self):
        pass

    def is_ready(self):
        pass
