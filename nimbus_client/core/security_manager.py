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
from subprocess import Popen, PIPE, STDOUT

from nimbus_client.core.encdec_provider import EncDecProvider
from nimbus_client.core import pycrypto_enc_engine
from nimbus_client.core.exceptions import InvalidPasswordException, NoCertFound
from nimbus_client.core.logger import logger

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
        if not self._client_cert:
            raise NoCertFound('No client certificate found in key chain!')
        return self._client_cert

    def get_client_cert_key(self):
        pass

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



class SimpleFile:
    def __init__(self, path):
        self.__path = path

    def exists(self):
        return os.path.exists(self.__path)

    def create_empty(self):
        dirname = os.path.dirname(self.__path)
        if not os.path.exists(dirname):
            try:
                os.mkdir(dirname)
            except IOError:
                raise Exception('Can not make directory "%s"'%dirname)

        self.write('')

    def copy_from(self, dest_file):
        data = self.__int_read(dest_file)
        self.write(data)

    def write(self, data):
        try:
            open(self.__path, 'w').write(data)
        except IOError:
            raise Exception('Can not write to "%s"'%ks_path)

    def read(self):
        return self.__int_read(self.__path)

    def __int_read(self, path):
        try:
            data = open(path, 'rb').read()
        except IOError:
            raise Exception('Can not read from "%s"'%path)
        return data
        

class FileBasedSecurityManager(AbstractSecurityManager):
    ks_file_class = SimpleFile

    @classmethod
    def get_ks_status(cls, ks_path):
        ks_file = cls.ks_file_class(ks_path)
        if not ks_file.exists():
            return cls.KSS_NOT_FOUND
        return cls.KSS_EXISTS
        ##?? cls.KSS_INVALID

    @classmethod
    def exec_openssl(cls, command, stdin=None, cwd=None):
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


    def get_client_cert_key(self):
        cert_file = tempfile.NamedTemporaryFile()
        cert_file.write(self._client_cert)
        cert_file.flush()
        try:
            retcode, out = self.exec_openssl(['x509', '-in', cert_file.name, '-subject', '-noout'])
            if retcode:
                raise Exception('Can not retrieve subject from client certificate')

            for item in out.split('/'):
                parts = item.split('=')
                if parts[0] == 'CN':
                    try:
                        return int(parts[1])
                    except ValueError:
                        raise Exception('Invalid subject CN in client certificate!')
        finally:
            cert_file.close()


    @classmethod
    def initiate_key_storage(cls, ks_path, ks_pwd):
        ks_file = cls.ks_file_class(ks_path)
        if ks_file.exists():
            try:
                cls(ks_path, ks_pwd)
            except Exception, err:
                raise Exception('Key chain at "%s" is already exists'\
                                ' and can not be opened with this pin-code'%ks_path)
            return

        ks_file.create_empty()

        pkey_file = tempfile.NamedTemporaryFile()
        ks_tmp_file = tempfile.NamedTemporaryFile()
        retcode, out = cls.exec_openssl(['genrsa', '-out', pkey_file.name, '1024'])
        if retcode:
            raise Exception('Can not generate private key using openssl command')

        try:
            retcode, out = cls.exec_openssl(['pkcs12', '-export', '-inkey', pkey_file.name, \
                '-nocerts', '-out', ks_tmp_file.name, '-password', 'stdin'], ks_pwd)
            if retcode:
                raise Exception('Can not create key chain! Details: %s'%out)
            ks_file.copy_from(ks_tmp_file.name)
        finally:
            pkey_file.close()
            ks_tmp_file.close()

    def _load_key_storage(self, ks_path, passwd):
        ks_file = self.ks_file_class(ks_path)
        if not ks_file.exists():
            raise Exception('Key chain does not found at %s!'%ks_path)

        tmp_file = tempfile.NamedTemporaryFile()
        ks_tmp_file = tempfile.NamedTemporaryFile()
        try:
            ks_tmp_file.write(ks_file.read())
            ks_tmp_file.flush()
            retcode, out = self.exec_openssl(['pkcs12', '-in', ks_tmp_file.name, '-out', \
                    tmp_file.name, '-password', 'stdin', '-nodes'], passwd)
            if retcode:
                raise InvalidPasswordException('Can not open key chain! Maybe pin-code is invalid!')
            data = open(tmp_file.name).read()
        finally:
            tmp_file.close()
            ks_tmp_file.close()

        pkey_s = re.search('(-----BEGIN \w*\s*PRIVATE KEY-----(\w|\W)+-----END \w*\s*PRIVATE KEY-----)', data)
        if not pkey_s:
            raise Exception('Private key does not found in key chain!')
        self._client_prikey = pkey_s.groups()[0]

        cert_s = re.search('(-----BEGIN \w*\s*CERTIFICATE-----(\w|\W)+-----END \w*\s*CERTIFICATE-----)', data)
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
        new_ks_file = tempfile.NamedTemporaryFile()
        pkey_file.write(self._client_prikey)
        pkey_file.flush()
        cert_file.write(cert)
        cert_file.flush()

        try:
            retcode, out =  self.exec_openssl(['pkcs12', '-export', \
                    '-inkey', pkey_file.name, '-in', cert_file.name, '-out', new_ks_file.name, \
                    '-password', 'stdin'], ks_pwd)
            if retcode:
                raise Exception('Can not update key chain! %s'%out)

            ks_file = self.ks_file_class(ks_path)
            ks_file.copy_from(new_ks_file.name)
        finally:
            pkey_file.close()
            cert_file.close()
            new_ks_file.close()

    def validate(self, password):
        ks_file = self.ks_file_class(self._ks_path)
        ks_tmp_file = tempfile.NamedTemporaryFile()
        try:
            ks_tmp_file.write(ks_file.read())
            ks_tmp_file.flush()
            retcode, out = self.exec_openssl(['pkcs12', '-in', ks_tmp_file.name, \
                    '-password', 'stdin', '-info', '-noout', '-nodes'], password)
            if retcode:
                return False
            return True
        finally:
            ks_tmp_file.close()

