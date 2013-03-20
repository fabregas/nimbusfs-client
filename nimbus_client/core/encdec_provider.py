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

BLOCK_SIZE = 16
INTERRUPT_LEN = 1
PAD = '\x00'

class EncDecProvider:
    def __init__(self, cipher_class, raw_data_len=None):
        self.__cipher_class = cipher_class
        self.__header_len = cipher_class.key_size()
        self.__expected_len = self.__calculate_expected_len(raw_data_len)
        self.__raw_data_len = raw_data_len
        self.__processed_len = 0
        self.__cipher = None

    def get_expected_data_len(self):
        return self.__expected_len

    def set_expected_data_len(self, expected_len):
        return self.__expected_len

    def __calculate_expected_len(self, raw_data_len):
        if raw_data_len is None:
            return None
        remaining_len = BLOCK_SIZE - raw_data_len - INTERRUPT_LEN
        to_pad_len = remaining_len % BLOCK_SIZE
        return 2 + self.__header_len + raw_data_len + INTERRUPT_LEN + to_pad_len

    def encrypt(self, data, finalize=False):
        self.__processed_len += len(data) 
        if not self.__cipher:
            self.__cipher = self.__cipher_class()
            enc_data = self.__cipher.get_encrypted_header()
        else:
            enc_data = None

        if self.__raw_data_len and self.__raw_data_len <= self.__processed_len:
            finalize = True

        encrypted = self.__cipher.encrypt(data, finalize)

        if enc_data:
            header_size = struct.pack('<H', len(enc_data))
            return ''.join([header_size, enc_data, encrypted])
        else:
            return encrypted


    def decrypt(self, data):
        data_len = len(data)
        self.__processed_len += data_len

        if not self.__cipher:
            enc_data_len = struct.unpack('<H', data[:2])[0]
            if data_len < enc_data_len+2:
                raise Exception('Unexpected encrypted header size: %s < %s'%(data_len, enc_data_len+2))

            header = data[2:2+enc_data_len]
            data = data[enc_data_len+2:]

            self.__cipher = self.__cipher_class(header)
            data_len = len(data)

        if self.__processed_len >= self.__expected_len:
            finalize = True
        else:
            finalize = False

        return self.__cipher.decrypt(data, finalize)

