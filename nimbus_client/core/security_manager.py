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
import tempfile
import zipfile
import struct
from datetime import datetime
from base64 import b64encode, b64decode

from nimbus_client.core.constants import SPT_FILE_BASED, SPT_TOKEN_BASED
from nimbus_client.core.encdec_provider import EncDecProvider
from nimbus_client.core import pycrypto_enc_engine
from nimbus_client.core.exceptions import InvalidPasswordException

CLIENT_CERT_FILENAME = 'client_certificate.pem'
CLIENT_PRIKEY_FILENAME = 'client_prikey'

Cipher = pycrypto_enc_engine.PythonCryptoEngine

class AbstractSecurityManager:
    def __init__(self, ks_path, passwd):
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



class FileBasedSecurityManager(AbstractSecurityManager):
    def _load_key_storage(self, ks_path, passwd):
        if not os.path.exists(ks_path):
            raise Exception('Key storage file %s does not found!'%ks_path)

        storage = zipfile.ZipFile(ks_path)
        storage.setpassword(passwd)

        def read_file(f_name):
            try:
                f_obj = storage.open(f_name)
            except RuntimeError, err:
                raise InvalidPasswordException('Bad password for key storage!')
                
            data = f_obj.read()
            f_obj.close()
            return data

        self._client_cert = read_file(CLIENT_CERT_FILENAME)
        self._client_prikey = read_file(CLIENT_PRIKEY_FILENAME)

        storage.close()


