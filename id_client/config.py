#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.core.config
@author Konstantin Andrusenko
@date November 25, 2012

This module contains the implementation of Config class
"""
import os
import ConfigParser
from ConfigParser import RawConfigParser

from constants import SPT_TOKEN_BASED

class Config:
    def __init__(self):
        try:
            config_file = self.get_config_file_path()
            if not os.path.exists(config_file):
                self.create_defaults()
                self.save()

            config = RawConfigParser()
            config.read(config_file)

            self.log_level = config.get('LOG','log_level')
            self.security_provider_type = config.get('SECURITY_PROVIDER', 'provider_type')
            self.key_storage_path = config.get('SECURITY_PROVIDER', 'key_storage_path')
            self.fabnet_hostname = config.get('FABNET', 'fabnet_url')
            self.parallel_put_count = int(config.get('FABNET', 'parallel_put_count'))
            self.parallel_get_count = int(config.get('FABNET', 'parallel_get_count'))
            self.webdav_bind_host = config.get('WEBDAV', 'bind_hostname')
            self.webdav_bind_port = config.get('WEBDAV', 'bind_port')
        except ConfigParser.NoOptionError, msg:
            raise Exception('ConfigParser. No option error: %s' % msg)
        except ConfigParser.Error, msg:
            raise Exception('ConfigParser: %s' % msg)

    def get_config_file_path(self):
        return os.path.join(os.getenv('HOME'), '.idepositbox_client.conf')

    def create_defaults(self):
        self.log_level = 'INFO'
        self.fabnet_hostname = 'lb.idepositbox.com'
        self.parallel_put_count = '3'
        self.parallel_get_count = '3'
        self.security_provider_type = SPT_TOKEN_BASED
        self.key_storage_path = ''
        self.webdav_bind_host = '127.0.0.1'
        self.webdav_bind_port = '8080'

    def save(self):
        config = RawConfigParser()
        config.add_section('LOG')
        config.add_section('FABNET')
        config.add_section('SECURITY_PROVIDER')
        config.add_section('WEBDAV')

        config.set('LOG', 'log_level', self.log_level)

        config.set('FABNET', 'fabnet_url', self.fabnet_hostname)
        config.set('FABNET', 'parallel_put_count', self.parallel_put_count)
        config.set('FABNET', 'parallel_get_count', self.parallel_get_count)
        config.set('SECURITY_PROVIDER', 'provider_type', self.security_provider_type)
        config.set('SECURITY_PROVIDER', 'key_storage_path', self.key_storage_path)
        config.set('WEBDAV', 'bind_hostname', self.webdav_bind_host)
        config.set('WEBDAV', 'bind_port', self.webdav_bind_port)

        config_file = self.get_config_file_path()
        f = open(config_file, 'w')
        config.write(f)
        f.close()

