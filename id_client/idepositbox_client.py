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
import os
import time
import logging
import traceback
import tempfile
import httplib
import urllib
import socket
import json
import subprocess
import threading
import string

from nimbus_client.core.security_manager import FileBasedSecurityManager, AbstractSecurityManager
from nimbus_client.core.base_safe_object import LockObject
from nimbus_client.core.nibbler import Nibbler
from nimbus_client.core.logger import logger
from nimbus_client.core.events import Event, events_provider

from id_client.webdav.application import WebDavAPI
from id_client.config import Config
from id_client.constants import *
from id_client.media_storage import get_media_storage_manager
from id_client.security.block_device_based_ks import BlockDeviceBasedSecurityManager
from id_client.webdav_mounter import WebdavMounter
from id_client.version import VERSION

SM_TYPES_MAP = {SPT_TOKEN_BASED: None,
                SPT_BLOCKDEV_BASED: BlockDeviceBasedSecurityManager,
                SPT_FILE_BASED: FileBasedSecurityManager}

ALLOWED_PWD_CHARS = set(string.letters + string.digits + '@#$%^&+=')

IDLock = LockObject()
IDEventLock = LockObject()

class IdepositboxClient(object):
    def __init__(self):
        self.__nibbler = None
        self.__api_list = []
        self.__config = Config()
        self.__status = CS_STOPPED
        self.__ms_mgr = get_media_storage_manager()
        self.__check_kss_thrd = None
        self.__last_ks_type = None
        self.__last_ks_path = None
        self.__events = []
        events_provider.append_listener(Event.ET_CRITICAL, self.on_critical_event)

    def __set_log_level(self):
        log_level = self.__config.log_level.lower()
        if log_level == 'info':
            logger.setLevel(logging.INFO)
        elif log_level == 'debug':
            logger.setLevel(logging.DEBUG)
        elif log_level == 'error':
            logger.setLevel(logging.ERROR)

    @IDEventLock
    def on_critical_event(self, event):
        self.__events.append(event)

    @IDEventLock
    def get_events(self):
        events = self.__events
        self.__events = []
        return events

    @IDEventLock
    def get_events_count(self):
        return len(self.__events)

    def get_version(self):
        return VERSION

    @IDLock
    def get_nibbler(self):
        return self.__nibbler

    @IDLock
    def get_status(self):
        return self.__status

    @IDLock
    def get_last_key_storage_type(self):
        return self.__last_ks_type

    @IDLock
    def get_last_key_storage_path(self):
        return self.__last_ks_path

    @IDLock
    def start(self, ks_type, ks_path, ks_passwd):
        if self.__status == CS_STARTED:
            raise Exception('IdepositboxClient is already started')

        self.__config.refresh()
        config = self.__config
        try:
            self.__set_log_level()
            sm_class = SM_TYPES_MAP.get(ks_type, None)
            if not sm_class:
                raise Exception('Unsupported key chain type: "%s"'%ks_type)
            security_provider = sm_class(ks_path, ks_passwd)
            self.__last_ks_path = ks_path
            self.__last_ks_type = ks_type
            
            self.__nibbler = Nibbler(config.fabnet_hostname, security_provider, \
                                config.parallel_put_count, config.parallel_get_count, \
                                config.cache_dir, config.cache_size)


            try:
                registered = self.__nibbler.is_registered()
            except Exception, err:
                logger.error(err)
                raise Exception('Service %s does not respond! Please, '\
                                'ensure that network is configured correctly'%config.fabnet_hostname)

            if not registered:
                try:
                    self.__nibbler.register_user() #FIXME: this is dangerous call! user should accept this case...
                except Exception, err:
                    logger.error('Register user error: %s'%err)
                    raise Exception('User does not registered in service')

            self.__nibbler.start()

            #init API instances
            self.__api_list = []
            if config.mount_type == MOUNT_LOCAL:
                ext_host = '127.0.0.1'
            else:
                ext_host = config.webdav_bind_host
            webdav_server = WebDavAPI(self.__nibbler, ext_host, config.webdav_bind_port)
            self.__api_list.append(webdav_server)

            for api_instance in self.__api_list:
                logger.debug('starting %s...'%api_instance.get_name())
                api_instance.start()
                
                logger.debug('waiting while %s is started...'%api_instance.get_name())
                for i in xrange(api_instance.get_start_waittime()):
                    time.sleep(1)
                    if api_instance.is_ready():
                        break
                else:
                    raise Exception('%s does not started!'%api_instance.get_name())
                logger.info('%s is started!'%api_instance.get_name())

            if config.mount_type == MOUNT_LOCAL:
                webdav_mount = WebdavMounter()
                ret_code = webdav_mount.mount(ext_host, config.webdav_bind_port)
                mount_point = webdav_mount.get_mount_point()
                if ret_code:
                    logger.error('WebDav resource does not mounted at %s!'%mount_point)
                else:
                    logger.info('WebDav resource is mounted at %s'%mount_point)

            self.__check_kss_thrd = CheckKSStatusThread(self)
            self.__check_kss_thrd.start()
            logger.info('IdepositboxClient is started')
        except Exception, err:
            logger.error('init fabnet provider error: %s'%err)
            self.__status = CS_FAILED
            self.stop()
            logger.write = logger.debug
            traceback.print_exc(file=logger)
            raise err
        self.__status = CS_STARTED

    @IDLock
    def get_config(self):
        self.__config.refresh()
        return self.__config.get_config_dict()

    @IDLock
    def update_config(self, new_config):
        self.__config.update(new_config)
        self.__config.save()

    @IDLock
    def get_available_media_storages(self):
        return self.__ms_mgr.get_available_storages()

    @IDLock
    def key_storage_status(self, ks_type=None, ks_path=''):
        if ks_type is None:
            if not self.__last_ks_type:
                return AbstractSecurityManager.KSS_NOT_FOUND
            ks_type = self.__last_ks_type
            ks_path = self.__last_ks_path
        sm = SM_TYPES_MAP.get(ks_type, None)
        if not sm:
            raise Exception('Unsupported key chain type: "%s"'%ks_type)
        return sm.get_ks_status(ks_path)

    @IDLock
    def get_key_storage_info(self, ks_type, ks_path, ks_pwd):
        sm_class = SM_TYPES_MAP.get(ks_type, None)
        if not sm_class:
            raise Exception('Unsupported key chain type: "%s"'%ks_type)

        cert = sm_class(ks_path, ks_pwd).get_client_cert()
        tmp_file = tempfile.NamedTemporaryFile()
        tmp_file.write(cert)
        tmp_file.flush()
        cmd = 'openssl x509 -in %s -noout -text'%tmp_file.name
        p = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cout, cerr = p.communicate()
        tmp_file.close()
        if p.returncode != 0:
            raise Exception(cerr)
        return cout

    def __validate_password(self, password):
        if (len(password) < 4):
            raise Exception("Password is too short")
        if any(ch not in ALLOWED_PWD_CHARS for ch in password):
            raise Exception("Password contains illegal characters")

    def generate_key_storage(self, ks_type, ks_path, act_key, password):
        sm_class = SM_TYPES_MAP.get(ks_type, None)
        if not sm_class:
            raise Exception('Unsupported key chain type: "%s"'%ks_type)

        self.__validate_password(password)
        
        conn = self.__ca_call('/get_payment_info', {'payment_key': act_key})
        try:
            resp = conn.getresponse()
            if resp.status == 505: #not found err_code
                raise Exception('Activation key "%s" does not found!'%act_key)
            if resp.status != 200:
                raise Exception('CA service error! [%s %s] %s'%(resp.status, resp.reason, resp.read()))
            data = resp.read()
        finally:
            conn.close()

        try:
            p_info = json.loads(data)
        except Exception, err:
            raise Exception('Invalid CA response: "%s"'%data)

        logger.info('Activation code is verified...')

        #if p_info['status'] == 'WAIT_FOR_USER':
        #    raise Exception('Activation key %s is already processed!'%act_key)
        sm_class.initiate_key_storage(ks_path, password)
        logger.info('key chain is initiated...')
        sm = sm_class(ks_path, password)
        cert_req = sm.generate_cert_request(p_info['cert_cn'])
        logger.info('certificate request is generated...')

        conn = self.__ca_call('/generate_certificate', \
                {'cert_req_pem': cert_req, 'payment_key': act_key})

        try:
            resp = conn.getresponse()
            if resp.status != 200:
                raise Exception('CA service error! Generate certificate: [%s %s] %s'%\
                        (resp.status, resp.reason, resp.read()))
            cert = resp.read()
        finally:
            conn.close()
        logger.info('certificate is received from CA')
        sm.append_certificate(ks_path, password, cert)
        logger.info('certificate is saved to key chain')

    def __ca_call(self, path, params={}, method='POST'):
        ca_addr = self.__config.ca_address
        if ':' not in ca_addr:
            ca_addr += ':8888' #Defult CA port
        try:
            conn = httplib.HTTPConnection(ca_addr)
            params = urllib.urlencode(params)
            conn.request(method, path, params)
        except socket.error, err:
            raise Exception('CA service does not respond at http://%s%s\n%s'%(ca_addr, path, err))

        return conn

    @IDLock
    def stop(self):
        if self.__status == CS_STOPPED:
            return

        try:
            if self.__check_kss_thrd:
                self.__check_kss_thrd.stop()
                self.__check_kss_thrd = None

            if self.__config.mount_type == MOUNT_LOCAL:
                webdav_mount = WebdavMounter()
                ret_code = webdav_mount.unmount()

            for api_instance in self.__api_list:
                try:
                    logger.debug('stopping %s ...'%api_instance.get_name())
                    api_instance.stop()
                    logger.info('%s is stopped!'%api_instance.get_name())
                except Exception, err:
                    logger.error('stopping %s error: %s'%(api_instance.get_name(), err))

            if self.__nibbler:
                self.__nibbler.stop()

            logger.info('IdepositboxClient is stopped')
        except Exception, err:
            logger.error('stopping fabnet provider error: %s'%err)
            self.__status = CS_FAILED
            raise err

        self.__status = CS_STOPPED


class CheckKSStatusThread(threading.Thread):
    def __init__(self, id_client):
        threading.Thread.__init__(self)
        self.id_client = id_client
        self.stopped = threading.Event()
        self.setName('CheckKSStatusThread')

    def run(self):
        logger.debug('thread is started')
        while not self.stopped.is_set():
            try:
                ks_status = self.id_client.key_storage_status()
                if ks_status != AbstractSecurityManager.KSS_EXISTS \
                        and self.id_client.get_status() == CS_STARTED:
                    self.id_client.stop()
            except Exception, err:
                logger.error('CheckKSStatusThread: %s'%err)
            finally:
                time.sleep(2)
        logger.debug('thread is stopped')

    def stop(self):
        self.stopped.set()
