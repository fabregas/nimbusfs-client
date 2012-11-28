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

from M2Crypto import X509
from Crypto.Cipher import AES
from Crypto import Random
from Crypto.PublicKey import RSA

CLIENT_CERT_FILENAME = 'client_certificate.pem'
CLIENT_PRIKEY_FILENAME = 'client_prikey'

BLOCK_SIZE = 32
INTERRUPT = u'\u0001'
PAD = u'\u0000'


class AbstractSecurityManager:
    def __init__(self, ks_path, passwd):
        self._client_cert = None
        self._client_prikey = None

        self.__random = Random.new()

        self._load_key_storage(ks_path, passwd)

    def _load_key_storage(self, ks_path, passwd):
        pass

    def get_client_cert(self):
        return self._client_cert

    def get_client_cert_key(self):
        cert = X509.load_cert_string(self._client_cert)
        return cert.get_fingerprint()
        #return cert.get_ext('authorityKeyIdentifier').get_value()[5:].strip().replace(':','')

    def __add_padding(self, data):
        new_data = ''.join([data, INTERRUPT])
        new_data_len = len(new_data)
        remaining_len = BLOCK_SIZE - new_data_len
        to_pad_len = remaining_len % BLOCK_SIZE
        pad_string = PAD * to_pad_len
        return ''.join([new_data, pad_string])

    def __strip_padding(self, data):
        ret_data = data.rstrip(PAD).rstrip(INTERRUPT)
        return ret_data

    def __get_random(self, cnt):
        while True:
            data = self.__random.read(cnt)
            if data[0] != '\x00':
                return data

    def encrypt(self, data):
        secret = self.__get_random(32)
        iv = self.__random.read(16)
        encrypt_cipher = AES.new(secret, AES.MODE_CBC, iv)
        plaintext_padded = self.__add_padding(data)

        encrypted = encrypt_cipher.encrypt(plaintext_padded)

        public_key = self._client_prikey.publickey()

        enc_data = public_key.encrypt(secret+iv, 32)[0]
        header_size = struct.pack('<H', len(enc_data)+2)

        return ''.join([header_size, enc_data, encrypted])

    def __dump(self, ss):
        ret_s = ''
        for c in ss:
            ret_s += '%x'%ord(c)
        return ret_s


    def decrypt(self, data):
        hsize = struct.unpack('<H', data[:2])[0]
        header = data[2:hsize]
        data = data[hsize:]

        header = self._client_prikey.decrypt(header)
        secret = header[:32]
        iv = header[32:]

        decrypt_cipher = AES.new(secret, AES.MODE_CBC, iv)
        decrypted_data = decrypt_cipher.decrypt(data)
        return self.__strip_padding(decrypted_data)


class FileBasedSecurityManager(AbstractSecurityManager):
    def _load_key_storage(self, ks_path, passwd):
        if not os.path.exists(ks_path):
            raise Exception('Key storage file %s does not found!'%ks_path)

        storage = zipfile.ZipFile(ks_path)
        storage.setpassword(passwd)

        def read_file(f_name):
            f_obj = storage.open(f_name)
            data = f_obj.read()
            f_obj.close()
            return data

        self._client_cert = read_file(CLIENT_CERT_FILENAME)
        self._client_prikey = read_file(CLIENT_PRIKEY_FILENAME)
        self._client_prikey = RSA.importKey(self._client_prikey)

        storage.close()


