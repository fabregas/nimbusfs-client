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
import tempfile

from wsgidav.version import __version__
from wsgidav.wsgidav_app import DEFAULT_CONFIG, WsgiDAVApp
from wsgidav.util import BASE_LOGGER_NAME
from cherrypy import wsgiserver, __version__ as cp_version

from nimbus_client.core.logger import init_logger
from fabnet_dav_provider import FabnetProvider
from ks_domain_controller import KSDomainController
from id_client.base_external_api import BaseExternalAPI
from id_client.version import VERSION
from id_client.config import Config

WAIT_WEBDAV_SERVER_TIMEOUT = 10

wsgiserver.CherryPyWSGIServer.version = "WsgiDAV/%s %s" % (__version__, wsgiserver.CherryPyWSGIServer.version)

class WebDavAPI(BaseExternalAPI):
    def __init__(self, nibbler, host, port, log_level=logging.INFO):
        BaseExternalAPI.__init__(self, nibbler)
        self.host = host
        self.port = int(port)
        self.log_level = log_level
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
        config = Config()
        wsgi_logger = init_logger(os.path.join(config.data_dir, 'logs', 'webdav.log'),\
                                    BASE_LOGGER_NAME)
        wsgi_logger.setLevel(self.log_level)

    def main_loop(self):
        provider = FabnetProvider(self.nibbler)

        config = DEFAULT_CONFIG.copy()
        config.update({
            "provider_mapping": {"/": provider},
            "user_mapping": {},
            "verbose": 1,
            #"debug_methods": ['OPTIONS', 'PROPFIND', 'GET'],
            "enable_loggers": [],
            "propsmanager": True,      # True: use property_manager.PropertyManager                    
            "locksmanager": True,      # True: use lock_manager.LockManager                   
            "acceptdigest": False,     # Allow digest authentication, True or False
            "defaultdigest": False,    # True (default digest) or False (default basic)
            "domaincontroller": KSDomainController(self.nibbler.get_security_provider()),  
            "dir_browser": {'response_trailer': "<a href='http://idepositbox.com'>"\
                                    "iDepositBox/%s</a> ${time}"%VERSION}
            })

        app = WsgiDAVApp(config)
        self.__init_logger()

        if config["verbose"] >= 1:
            print("Running %s, listening on %s://%s:%s" % (wsgiserver.CherryPyWSGIServer.version, 'http', self.host, self.port))

        self.server = wsgiserver.CherryPyWSGIServer((self.host, self.port), app,)
        self.server.provider = provider

        self.server.start()


    def stop(self):
        if self.server:
            self.server.stop()



