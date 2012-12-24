#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.idepositbox_client
@author Konstantin Andrusenko
@date November 25, 2012

This module contains the implementation of IdepositboxClient class
"""
import time
import logging

from nimbus_client.core.security_manager import FileBasedSecurityManager, AbstractSecurityManager
from nimbus_client.core.nibbler import Nibbler
from nimbus_client.core.logger import logger

from id_client.webdav_server import WebDavServer
from id_client.token_agent import TokenAgent
from id_client.config import Config
from id_client.constants import *



class IdepositboxClient:
    def __init__(self):
        self.nibbler = None
        self.webdav_server = None
        self.config = Config()
        self.token_agent = TokenAgent(self.on_usb_token_event)
        self.status = CS_STOPPED

    def __set_log_level(self):
        log_level = self.config.log_level.lower()
        if log_level == 'info':
            logger.setLevel(logging.INFO)
        elif log_level == 'debug':
            logger.setLevel(logging.DEBUG)
        elif log_level == 'error':
            logger.setLevel(logging.ERROR)


    def start(self, ks_passwd):
        self.config.refresh()
        config = self.config
        try:
            self.__set_log_level()
            if config.security_provider_type == SPT_TOKEN_BASED:
                raise Exception('not implemented') #FIXME: token based security manager should be returned
            elif SPT_FILE_BASED:
                security_provider = FileBasedSecurityManager(config.key_storage_path, ks_passwd)
            else:
                raise Exception('Unexpected security provider type: "%s"'%config.security_provider_type)

            self.nibbler = Nibbler(config.fabnet_hostname, security_provider, \
                                config.parallel_put_count, config.parallel_get_count)

            try:
                registered = self.nibbler.is_registered()
            except Exception, err:
                logger.error(err)
                raise Exception('Service %s does not respond! Please, '\
                                'ensure that network is configured correctly'%config.fabnet_hostname)

            if not registered:
                try:
                    self.nibbler.register_user() #FIXME: this is dangerous call! user should accept this case...
                except Exception, err:
                    logger.error('Register user error: %s'%err)
                    raise Exception('User does not registered in service')

            self.webdav_server = WebDavServer(config.webdav_bind_host, config.webdav_bind_port, self.nibbler)
            self.webdav_server.start()

            logger.debug('waiting while WebDav server is started...')
            for i in xrange(WAIT_WEBDAV_SERVER_TIMEOUT):
                time.sleep(1)
                if self.webdav_server.is_ready():
                    break
            else:
                raise Exception('Webdav server does not started!')

            logger.debug('WebDav server is started!')
            logger.info('IdepositboxClient is started')
        except Exception, err:
            logger.error('init fabnet provider error: %s'%err)
            self.status = CS_FAILED
            if self.nibbler:
                self.nibbler.stop()
            raise err
        self.status = CS_STARTED

    def stop(self):
        try:
            self.token_agent.stop()
            if self.webdav_server:
                self.webdav_server.stop()
            if self.nibbler:
                self.nibbler.stop()
            logger.info('IdepositboxClient is stopped')
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
