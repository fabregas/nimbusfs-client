#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.encdec_provider
@author Konstantin Andrusenko
@date February 04, 2013

This module contains the implementation of EncDecProvider class
"""


import struct
from Crypto.Cipher import AES
from Crypto import Random

BLOCK_SIZE = 32
INTERRUPT = '\x00\x01'
PAD = '\x00'

class EncDecProvider:
    def __init__(self, prikey, raw_data_len=None):
        self.__cipher = None
        self.__rest_str = ''
        self.__prikey = prikey
        self.__max_enc_data_len = len(self.__prikey.publickey().encrypt(' '*48, 32)[0])
        self.__expected_len = self.__calculate_expected_len(raw_data_len)
        self.__raw_data_len = raw_data_len
        self.__processed_len = 0
        self.__random = Random.new()

    def get_expected_data_len(self):
        return self.__expected_len

    def __calculate_expected_len(self, raw_data_len):
        if raw_data_len is None:
            return None
        int_len = len(INTERRUPT)
        remaining_len = BLOCK_SIZE - raw_data_len - int_len
        to_pad_len = remaining_len % BLOCK_SIZE
        return 4 + self.__max_enc_data_len  + raw_data_len + len(INTERRUPT) + to_pad_len

    def __add_padding(self, data, force=False):
        data = self.__rest_str + data
        self.__rest_str = ''
        if force or (self.__raw_data_len and self.__raw_data_len <= (self.__processed_len+len(data))):
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
        
        self.__processed_len += len(ret_data)
        return ret_data

    def __strip_padding(self, data):
        ret_data = data.rstrip(PAD).rstrip(INTERRUPT)
        return ret_data

    def __get_random(self, cnt):
        while True:
            data = self.__random.read(cnt)
            if data[0] != '\x00':
                return data

    def encrypt(self, data, finalize=False):
        if not self.__cipher:
            secret = self.__get_random(32)
            iv = self.__random.read(16)
            self.__cipher = AES.new(secret, AES.MODE_CBC, iv)
            enc_data = self.__prikey.publickey().encrypt(secret+iv, 32)[0]

            to_pad_len = self.__max_enc_data_len - len(enc_data)
            enc_data_pad = PAD * to_pad_len
        else:
            enc_data = None

        plaintext_padded = self.__add_padding(data, finalize)
        if plaintext_padded:
            encrypted = self.__cipher.encrypt(plaintext_padded)
        else:
            #need more data for encryprion
            encrypted = ''

        if enc_data:
            header_size = struct.pack('<HH', len(enc_data), len(enc_data_pad))
            return ''.join([header_size, enc_data, enc_data_pad, encrypted])
        else:
            return encrypted


    def decrypt(self, data):
        data = self.__rest_str + data
        data_len = len(data)
        self.__processed_len += data_len

        if not self.__cipher:
            enc_data_len, enc_data_pad_len  = struct.unpack('<HH', data[:4])
            if data_len < enc_data_len+4:
                raise Exception('Unexpected encrypted header size: %s'%len(data))

            header = data[4:4+enc_data_len]
            data = data[enc_data_len+enc_data_pad_len+4:]

            header = self.__prikey.decrypt(header)
            secret = header[:32]
            iv = header[32:]

            self.__cipher = AES.new(secret, AES.MODE_CBC, iv)

        data_len = len(data)
        if data_len < BLOCK_SIZE:
            self.__rest_str = data
            return ''
        rest_len = data_len % BLOCK_SIZE
        if rest_len:
            self.__rest_str = data[data_len-rest_len:]
            data = data[:data_len-rest_len]

        decrypted_data = self.__cipher.decrypt(data)

        if self.__processed_len >= self.__expected_len:
            return self.__strip_padding(decrypted_data)
        else:
            return decrypted_data

