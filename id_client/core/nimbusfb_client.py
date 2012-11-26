#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.core.nimbusfs_client
@author Konstantin Andrusenko
@date November 25, 2012

This module contains the implementation of IdepositboxClient class
"""
from id_client.core.constants import CS_FAILED, CS_STARTED, CS_STOPPED
from id_client.core.token_agent import TokenAgent
from id_client.core.security_manager import init_security_manager

from id_client.core.nibbler import Nibbler
from id_client.core.config import Config
from id_client.core.logger import logger
from id_client.webdav_server import WebDavServer

class NimbusFSClient:
    def __init__(self):
        self.nibbler = None
        self.webdav_server = None
        self.config = Config()
        self.token_agent = TokenAgent(self.on_usb_token_event)
        self.status = CS_STOPPED

    def init_fabnet_provider(self, ks_passwd):
        config = self.config
        try:
            security_provider = init_security_manager(config.security_provider_type, \
                                        config.key_storage_path, ks_passwd)

            self.nibbler = Nibbler(config.fabnet_hostname, security_provider, \
                                config.parallel_put_count, config.parallel_get_count)

            self.webdav_server = WebDavServer(config.webdav_bind_host, config.webdav_bind_port, self.nibbler)
            self.webdav_server.start()
        except Exception, err:
            logger.error('init fabnet provider error: %s'%err)
            self.status = CS_FAILED
            raise err
        self.status = CS_STARTED

    def stop_fabnet_provider(self):
        try:
            self.token_agent.stop()
            self.webdav_server.stop()
            self.nibbler.stop()
        except Exception, err:
            logger.error('stopping fabnet provider error: %s'%err)
            self.status = CS_FAILED
            raise err

        self.status = CS_STOPPED

    def on_usb_token_event(self, event, data):
        '''This method should be implemented for performing actions
        when USB token is inserted or removed from PC

        Algorithm pattern:

        if event == UTE_TOKEN_INSERTED:
            #ask key storage password...
            self.init_fabnet_provider(ks_passwd)
        elif event == UTE_TOKEN_REMOVED:
            self.stop_fabnet_provider()
        '''
        pass
