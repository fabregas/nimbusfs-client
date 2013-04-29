#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_clientwebdav.application
@author Konstantin Andrusenko
@date Nobember 25, 2012

This module contains the implementation of WebDavServer class
"""
import os
import shutil
import time
import signal
import sys
import threading
import logging

from wsgidav.version import __version__
from wsgidav.wsgidav_app import DEFAULT_CONFIG, WsgiDAVApp
from wsgidav.fs_dav_provider import FilesystemProvider
from wsgidav.util import BASE_LOGGER_NAME
from cherrypy import wsgiserver, __version__ as cp_version

from fabnet_dav_provider import FabnetProvider
from id_client.base_external_api import BaseExternalAPI
from nimbus_client.core.logger import logger

WAIT_WEBDAV_SERVER_TIMEOUT = 10

wsgiserver.CherryPyWSGIServer.version = "WsgiDAV/%s %s" % (__version__, wsgiserver.CherryPyWSGIServer.version)

class WebDavAPI(BaseExternalAPI):
    def __init__(self, nibbler, host, port):
        BaseExternalAPI.__init__(self, nibbler)
        self.host = host
        self.port = int(port)
        self.server = None

    def get_name(self):
        return 'WebDav API'

    def get_start_waittime(self):
        return WAIT_WEBDAV_SERVER_TIMEOUT

    def is_ready(self):
        if self.server:
            return self.server.ready
        return False

    def __init_logger(self):
        wsgi_logger = logging.getLogger(BASE_LOGGER_NAME)

        for hdlr in wsgi_logger.handlers[:]:
            try:
                hdlr.flush()
                hdlr.close()
            except:
                pass
            logger.removeHandler(hdlr)

        for hdlr in logger.handlers[:]:
            wsgi_logger.addHandler(hdlr)

        wsgi_logger.setLevel(logging.INFO)

    def run(self):
        provider = FabnetProvider(self.nibbler)

        config = DEFAULT_CONFIG.copy()
        config.update({
            "provider_mapping": {"/": provider},
            "user_mapping": {},
            "verbose": 1,
            #"debug_methods": ['OPTIONS', 'PROPFIND'],
            "enable_loggers": [],
            "propsmanager": True,      # True: use property_manager.PropertyManager                    
            "locksmanager": True,      # True: use lock_manager.LockManager                   
            "domaincontroller": None,  # None: domain_controller.WsgiDAVDomainController(user_mapping)
            })


        self.__init_logger()

        app = WsgiDAVApp(config)

        if config["verbose"] >= 1:
            print("Running %s, listening on %s://%s:%s" % (wsgiserver.CherryPyWSGIServer.version, 'http', self.host, self.port))

        self.server = wsgiserver.CherryPyWSGIServer((self.host, self.port), app,)
        self.server.provider = provider

        self.server.start()


    def stop(self):
        if self.server:
            self.server.stop()



