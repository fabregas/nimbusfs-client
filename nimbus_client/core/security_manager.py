#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.security_manager
@author Konstantin Andrusenko
@date October 28, 2012

This module contains the implementation of security manager
"""
import os
import re
import tempfile
import zipfile
import struct
import shutil
from datetime import datetime
from base64 import b64encode, b64decode
from subprocess import Popen, PIPE, STDOUT

from nimbus_client.core.constants import SPT_FILE_BASED, SPT_TOKEN_BASED
from nimbus_client.core.encdec_provider import EncDecProvider
from nimbus_client.core import pycrypto_enc_engine
from nimbus_client.core.exceptions import InvalidPasswordException
from nimbus_client.core.logger import logger

CLIENT_CERT_FILENAME = 'client_certificate.pem'
CLIENT_PRIKEY_FILENAME = 'client_prikey'

Cipher = pycrypto_enc_engine.PythonCryptoEngine

class AbstractSecurityManager:
    KSS_NOT_FOUND = 0
    KSS_INVALID = -1
    KSS_EXISTS = 1

    @classmethod
    def get_ks_status(cls, ks_path):
        pass

    @classmethod
    def initiate_key_storage(cls, ks_path, ks_pwd):
        pass

    def __init__(self, ks_path, passwd):
        self._ks_path = ks_path
        self._client_cert = None
        self._client_prikey = None

        self._load_key_storage(ks_path, passwd)
        Cipher.init_key_cipher(self._client_prikey)

    def _load_key_storage(self, ks_path, passwd):
        pass

    def get_client_cert(self):
        return self._client_cert

    def get_client_cert_key(self):
        return Cipher.load_serial_number(self._client_cert)

    def get_prikey(self):
        return self._client_prikey

    def get_encoder(self, raw_len):
        return EncDecProvider(Cipher, raw_len)

    def generate_cert_request(self):
        pass

    def append_certificate(self, ks_path, ks_pwd, cert):
        pass

    def validate(self, password):
        pass


class FileBasedSecurityManager(AbstractSecurityManager):
    @classmethod
    def get_ks_status(cls, ks_path):
        if not os.path.exists(ks_path):
            return cls.KSS_NOT_FOUND
        ##if not zipfile.is_zipfile(ks_path):
        ##    return cls.KSS_INVALID
        return cls.KSS_EXISTS

    def exec_openssl(self, command, stdin=None, cwd=None):
        '''Run openssl command. PKI_OPENSSL_BIN doesn't need to be specified'''
        c = ['openssl']
        c.extend(command)

        proc = Popen(c, shell=False, stdin=PIPE, stdout=PIPE, stderr=STDOUT, cwd=cwd)
        stdout_value, stderr_value = proc.communicate(stdin)

        out = stdout_value
        if stderr_value:
            out += '\n%s'%stderr_value
        if proc.returncode != 0:
            logger.debug('OpenSSL error: %s'%out)
        return proc.returncode, out

    @classmethod
    def initiate_key_storage(cls, ks_path, ks_pwd):
        ks_path = os.path.abspath(ks_path)
        if os.path.exists(ks_path):
            raise Exception('File "%s" is already exists'%ks_path)

        dirname = os.path.dirname(ks_path)
        if not os.path.exists(dirname):
            try:
                os.mkdir(dirname)
            except IOError:
                raise Exception('Can not make directory "%s"'%dirname)

        try:
            open(ks_path, 'w').close()
        except IOError:
            raise Exception('Can not write to "%s"'%ks_path)

        pkey_file = tempfile.NamedTemporaryFile()
        retcode, out = self.exec_openssl(['genrsa', '-out', pkey_file.name, '1024'])
        if retcode:
            raise Exception('Can not generate private key using openssl command')

        try:
            retcode, out = self.exec_openssl(['pkcs12', '-export', '-inkey', pkey_file.name, \
                '-nocerts', '-out', ks_path, '-password', 'stdin'], ks_pwd)
            if retcode:
                raise Exception('Can not create key chain at %s'%ks_path)
        finally:
            pkey_file.close()

    def _load_key_storage(self, ks_path, passwd):
        if not os.path.exists(ks_path):
            raise Exception('Key chain file %s does not found!'%ks_path)

        tmp_file = tempfile.NamedTemporaryFile()
        try:
            retcode, out = self .exec_openssl(['pkcs12', '-in', ks_path, '-out', tmp_file.name, '-password', 'stdin', '-nodes'], passwd)
            if retcode:
                raise InvalidPasswordException('Can not open key chain! Maybe pin-code is invalid!')
            data = open(tmp_file.name).read()
        finally:
            tmp_file.close()

        pkey_s = re.search('(-----BEGIN PRIVATE KEY-----(\w|\W)+-----END PRIVATE KEY-----)', data)
        if not pkey_s:
            raise Exception('Private key does not found in key chain!')
        self._client_prikey = pkey_s.groups()[0]

        cert_s = re.search('(-----BEGIN CERTIFICATE-----(\w|\W)+-----END CERTIFICATE-----)', data)
        if cert_s:
            self._client_cert = cert_s.groups()[0]

    def generate_cert_request(self, cert_cn):
        pkey_file = tempfile.NamedTemporaryFile()
        cert_req_file = tempfile.NamedTemporaryFile()
        pkey_file.write(self._client_prikey)
        pkey_file.flush()
        try:
            retcode, out = self.exec_openssl(['req', '-key', pkey_file.name, '-out', cert_req_file.name, \
                '-new', '-subj', '/CN=%s/O=iDepositBox\ software/OU=clients.idepositbox.com'%cert_cn])
            if retcode:
                raise Exception('No certificate request generated!\n%s'%out)
            cert_req = open(cert_req_file.name).read()
        finally:
            pkey_file.close()
            cert_req_file.close()
        return cert_req

    def append_certificate(self, ks_path, ks_pwd, cert):
        pkey_file = tempfile.NamedTemporaryFile()
        cert_file = tempfile.NamedTemporaryFile()
        pkey_file.write(self._client_prikey)
        pkey_file.flush()
        cert_file.write(cert)
        cert_file.flush()

        try:
            retcode, out =  self.exec_openssl(['pkcs12', '-export', \
                    '-inkey', pkey_file.name, '-in', cert_file.name, '-out', ks_path, \
                    '-password', 'stdin'], ks_pwd)
            if retcode:
                raise Exception('Can not update key chain at %s'%ks_path)
        finally:
            pkey_file.close()
            cert_file.close()

    def validate(self, password):
        retcode, out = self.exec_openssl(['pkcs12', '-in', self._ks_path, \
                '-password', 'stdin', '-info', '-noout', '-nodes'], password)
        if retcode:
            return False
        return True

