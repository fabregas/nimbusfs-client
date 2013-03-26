#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.m2crypto_engine
@author Konstantin Andrusenko
@date March 1, 2013

This module contains the implementation of encode/decode class
based in M2Crypto module
"""
try:
    import M2Crypto
    from M2Crypto import Rand, RSA
    from M2Crypto.EVP import Cipher
    has_m2crypto = True
except ImportError:
    has_m2crypto = False


ENC=1
DEC=0

class M2CryptoEngine:
    K_CIPHER = None

    @classmethod
    def init_key_cipher(cls, prikey):
        cls.K_CIPHER = RSA.load_key_string(prikey)

    def __init__(self, encrypted_header=None):
        if encrypted_header:
            self.__enc_data = encrypted_header

            header = self.K_CIPHER.private_decrypt(encrypted_header, RSA.pkcs1_padding)
            secret = header[:32]
            iv = header[32:]
            op = DEC
        else:
            secret = self._get_random(32)
            iv = self._get_random(16)
            self.__enc_data = self.K_CIPHER.public_encrypt(secret+iv, RSA.pkcs1_padding)
            op = ENC

        self.__cipher = Cipher(alg='aes_128_cbc', key=secret, iv=iv, op=op)
        self.__cipher.set_padding(1)

    def _get_random(self, cnt):
        while True:
            data = Rand.rand_bytes(cnt)
            if data[0] != '\x00':
                return data

    def encrypt(self, data, finalize=False):
        end_data = self.__cipher.update(data)
        if finalize:
            end_data += self.__cipher.final()
        return end_data

    def decrypt(self, data, finalize=False):
        end_data = self.__cipher.update(data)
        if finalize:
            end_data += self.__cipher.final()
        return end_data

    def get_encrypted_header(self):
       return self.__enc_data 

