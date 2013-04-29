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
import copy
import tempfile
import ConfigParser
from ConfigParser import RawConfigParser

from constants import SPT_TOKEN_BASED, MOUNT_LOCAL

class Config(dict):
    def __init__(self):
        dict.__init__(self)
        self.refresh()

    def __get_conf_val(self, section, param, var_name, p_type=str):
        try:
            val = self.__config.get(section, param)
            self[var_name] = p_type(val)
        except ConfigParser.Error:
            pass

    def refresh(self):
        try:
            self.update(self.get_defaults())
            config_file = self.get_config_file_path()

            if not os.path.exists(config_file):
                self.save()

            self.__config = RawConfigParser()
            self.__config.read(config_file)

            self.__get_conf_val('LOG','log_level', 'log_level')
            self.__get_conf_val('SECURITY_PROVIDER', 'provider_type', 'security_provider_type')
            self.__get_conf_val('SECURITY_PROVIDER', 'key_storage_path', 'key_storage_path')
            self.__get_conf_val('FABNET', 'fabnet_url', 'fabnet_hostname')
            self.__get_conf_val('FABNET', 'parallel_put_count', 'parallel_put_count', int)
            self.__get_conf_val('FABNET', 'parallel_get_count', 'parallel_get_count', int)
            self.__get_conf_val('CACHE', 'cache_dir', 'cache_dir')
            self.__get_conf_val('CACHE', 'cache_size', 'cache_size', int)
            self.__get_conf_val('WEBDAV', 'bind_hostname', 'webdav_bind_host')
            self.__get_conf_val('WEBDAV', 'bind_port', 'webdav_bind_port')
            self.__get_conf_val('WEBDAV', 'mount_type', 'mount_type')
        except ConfigParser.Error, msg:
            raise Exception('ConfigParser: %s' % msg)

    def get_config_file_path(self):
        return os.path.join(os.getenv('HOME'), '.idepositbox_client.conf')

    def get_defaults(self):
        return {'log_level': 'INFO',
                'fabnet_hostname': 'lb.idepositbox.com',
                'parallel_put_count': '3',
                'parallel_get_count': '3',
                'security_provider_type': SPT_TOKEN_BASED,
                'key_storage_path': '',
                'webdav_bind_host': '127.0.0.1',
                'webdav_bind_port': '8080',
                'mount_type': MOUNT_LOCAL,
                'cache_dir': tempfile.gettempdir(),
                'cache_size': 0}

    def __getattr__(self, attr):
        try:
            return  self.__getitem__(attr)
        except KeyError:
            raise  AttributeError(attr)

    def __setattr__(self, attr, value):
        if attr.startswith('_') or attr in self:
            dict.__setattr__(self, attr, value)
        else:
            self.__setitem__(attr, value)

    def save(self):
        config = RawConfigParser()
        config.add_section('LOG')
        config.add_section('FABNET')
        config.add_section('CACHE')
        config.add_section('SECURITY_PROVIDER')
        config.add_section('WEBDAV')

        config.set('LOG', 'log_level', self['log_level'])

        config.set('FABNET', 'fabnet_url', self['fabnet_hostname'])
        config.set('FABNET', 'parallel_put_count', self['parallel_put_count'])
        config.set('FABNET', 'parallel_get_count', self['parallel_get_count'])
        config.set('CACHE', 'cache_dir', self['cache_dir'])
        config.set('CACHE', 'cache_size', self['cache_size'])
        config.set('SECURITY_PROVIDER', 'provider_type', self['security_provider_type'])
        config.set('SECURITY_PROVIDER', 'key_storage_path', self['key_storage_path'])
        config.set('WEBDAV', 'bind_hostname', self['webdav_bind_host'])
        config.set('WEBDAV', 'bind_port', self['webdav_bind_port'])
        config.set('WEBDAV', 'mount_type', self['mount_type'])

        config_file = self.get_config_file_path()
        f = open(config_file, 'w')
        config.write(f)
        f.close()

    def get_config_dict(self):
        return copy.copy(self)

    def update_config(self, config_dict):
        self.update(config_dict)

