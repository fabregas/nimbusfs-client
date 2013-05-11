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

from idepositbox_client import logger

class BaseExternalAPI(threading.Thread):
    def __init__(self, nibbler):
        threading.Thread.__init__(self)
        name = self.get_name()
        if not name:
            name = self.__class__.__name__
        self.setName(name)
        self.nibbler = nibbler

    def run(self):
        try:
            self.main_loop()
        except Exception, err:
            logger.error('external API error: %s'%err)

    def main_loop(self):
        pass

    def stop(self):
        pass

    def get_name(self):
        pass

    def get_start_waittime(self):
        pass

    def is_ready(self):
        pass
