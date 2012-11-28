#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package webdav_server.server
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

from wsgidav.version import __version__
from wsgidav.wsgidav_app import DEFAULT_CONFIG, WsgiDAVApp
from wsgidav.fs_dav_provider import FilesystemProvider
from cherrypy import wsgiserver, __version__ as cp_version

from fabnet_dav_provider import FabnetProvider
from nimbus_client.core.logger import logger


class WebDavServer(threading.Thread):
    def __init__(self, host, port, nibbler):
        threading.Thread.__init__(self)
        self.host = host
        self.port = int(port)
        self.nibbler = nibbler

        self.server = None

    def is_ready(self):
        if not self.server:
            return False
        return self.server.ready

    def run(self):
        provider = FabnetProvider(self.nibbler)

        config = DEFAULT_CONFIG.copy()
        config.update({
            "provider_mapping": {"/": provider},
            "user_mapping": {},
            "verbose": 1,
            "enable_loggers": [],
            "propsmanager": True,      # True: use property_manager.PropertyManager                    
            "locksmanager": True,      # True: use lock_manager.LockManager                   
            "domaincontroller": None,  # None: domain_controller.WsgiDAVDomainController(user_mapping)
            })

        app = WsgiDAVApp(config)

        version = "WsgiDAV/%s %s" % (__version__, wsgiserver.CherryPyWSGIServer.version)
        wsgiserver.CherryPyWSGIServer.version = version
        if config["verbose"] >= 1:
            print("Runing %s, listening on %s://%s:%s" % (version, 'http', self.host, self.port))

        server = wsgiserver.CherryPyWSGIServer((self.host, self.port), app,)
        server.provider = provider

        self.server = server
        logger.info('WebDav server is initialized!')
        self.server.start()

    def stop(self):
        try:
            logger.info('Stopping webdav server...')
            if self.server:
                self.server.stop()
        except Exception, err:
            logger.error('Stopping webdav server error: %s'%err)


