#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.core.security_manager
@author Konstantin Andrusenko
@date November 25, 2012

This module contains the implementation of IdepositboxClient class
"""
from constants import SPT_FILE_BASED, SPT_TOKEN_BASED
from token_agent import TokenAgent
from webdav_server import WebDavServer
from nibbler import Nibbler

class IdepositboxClient:
    def __init__(self, config):
        self.nibbler = None
        self.webdav_server = None
        self.config = config
        self.token_agent = TokenAgent(self.on_usb_token_event)

    def init_fabnet_provider(self, ks_passwd):
        config = self.config
        if config.security_provider_type == SPT_FILE_BASED:
            security_provider = FileBasedSecurityProvider(config.key_storage_path, ks_passwd)
        elif config.security_provider_type == SPT_TOKEN_BASED:
            security_provider = TokenBasedSecurityProvider('', ks_passwd)

        self.nibbler = Nibbler(config.fabnet_hostname, security_provider, \
                            config.parallel_put_count, config.parallel_get_count)

        self.webdav_server = WebDavServer(config.webdav_bind_host, config.webdav_bind_port, self.nibbler)

    def stop_fabnet_provider():
        self.token_agent.stop()
        self.webdav_server.stop()
        self.nibbler.stop()

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
