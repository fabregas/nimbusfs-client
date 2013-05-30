#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.m2crypto_engine
@author Konstantin Andrusenko
@date March 1, 2013

This module contains the implementation of encode/decode class
based in Crypto module
"""
import re
from Crypto.Cipher import AES
from Crypto import Random
from Crypto.PublicKey import RSA as CRSA
from Crypto.Cipher import PKCS1_OAEP

BLOCK_SIZE = 16
INTERRUPT = '\x0F\x01'
PAD = '\x00'
INTERRUPT_LEN = len(INTERRUPT)
EOF_PATTERN = re.compile('%s%s*$'%(INTERRUPT, PAD))


class PythonCryptoEngine:
    RAND = Random.new()
    K_CIPHER = None
    __KEY = None

    @classmethod
    def init_key_cipher(cls, prikey):
        key = CRSA.importKey(prikey)
        cls.K_CIPHER = PKCS1_OAEP.new(key)
        cls.__KEY = key

    @classmethod
    def key_size(cls):
        if not cls.__KEY:
            raise RuntimeError('PythonCryptoEngine is not initialized!')
        size = cls.__KEY.size()
        to_pad_len = (8 - size) % 8
        return (size+to_pad_len)/8

    @classmethod
    def calculate_expected_len(cls, raw_data_len):
        remaining_len = BLOCK_SIZE - raw_data_len - INTERRUPT_LEN
        to_pad_len = remaining_len % BLOCK_SIZE
        return cls.key_size() + raw_data_len + INTERRUPT_LEN + to_pad_len

    def __init__(self, encrypted_header=None):
        if encrypted_header:
            self.__enc_data = encrypted_header

            header = self.K_CIPHER.decrypt(encrypted_header)
            secret = header[:32]
            iv = header[32:]
        else:
            secret = self._get_random(32)
            iv = self._get_random(16)
            self.__enc_data = self.K_CIPHER.encrypt(secret+iv)

        self.__cipher = AES.new(secret, AES.MODE_CBC, iv)
        self.__rest_str = ''
        self.__prev_dec_str = ''

    def __add_padding(self, data, finalize=False):
        data = self.__rest_str + data
        self.__rest_str = ''
        if finalize:
            new_data = ''.join([data, INTERRUPT])

            new_data_len = len(new_data)
            remaining_len = BLOCK_SIZE - new_data_len
            to_pad_len = remaining_len % BLOCK_SIZE
            pad_string = PAD * to_pad_len

            ret_data = ''.join([new_data, pad_string])
        else:
            data_len = len(data)
            if data_len < BLOCK_SIZE:
                self.__rest_str += data
                return None
            rest_len = data_len % BLOCK_SIZE
            if rest_len:
                self.__rest_str = data[data_len-rest_len:]
                ret_data = data[:data_len-rest_len]
            else:
                self.__rest_str = ''
                ret_data = data
        return ret_data

    def __strip_padding(self, data):
        found = re.search(EOF_PATTERN, data)
        if found:
            return data[:found.start()]
        return data

    def _get_random(self, cnt):
        while True:
            data = self.RAND.read(cnt)
            if data[0] != '\x00':
                return data

    def encrypt(self, data, finalize=False):
        plaintext_padded = self.__add_padding(data, finalize)
        if plaintext_padded:
            encrypted = self.__cipher.encrypt(plaintext_padded)
        else:
            #need more data for encryprion
            encrypted = ''
        return encrypted
    
    def decrypt(self, data, finalize=False):
        data = self.__rest_str + data
        self.__rest_str = ''
        data_len = len(data)
        if data_len < BLOCK_SIZE:
            self.__rest_str = data
            return ''
        rest_len = data_len % BLOCK_SIZE
        if rest_len:
            self.__rest_str = data[data_len-rest_len:]
            data = data[:data_len-rest_len]

        d_data = self.__cipher.decrypt(data)
        if finalize:
            ret_data = self.__strip_padding(self.__prev_dec_str + d_data)
        else:
            ret_data = self.__prev_dec_str + d_data[:-BLOCK_SIZE]
            self.__prev_dec_str = d_data[-BLOCK_SIZE:]

        return ret_data

    def get_encrypted_header(self):
        return self.__enc_data 


