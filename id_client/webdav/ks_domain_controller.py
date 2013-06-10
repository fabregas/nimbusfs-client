#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.webdav.ks_domain_controller
@author Konstantin Andrusenko
@date May 12, 2013
"""

from wsgidav.http_authenticator import SimpleDomainController


class KSDomainController(SimpleDomainController):
    def __init__(self, key_storage):
        self.key_storage = key_storage
        self.__pwd = None

    def getDomainRealm(self, inputURL, environ):
        """Resolve a relative url to the  appropriate realm name."""
        return ''

    def requireAuthentication(self, realmname, environ):
        """Return True if this realm requires authentication or False if it is 
        available for general access."""
        if environ.get('REMOTE_ADDR', '') == '127.0.0.1':
            return False
        return True 
    
    def isRealmUser(self, realmname, username, environ):
        """Returns True if this username is valid for the realm, False otherwise."""
        return True
 
    def getRealmUserPassword(self, realmname, username, environ):
        """Return the password for the given username for the realm. 
        Used for digest authentication.
        """
        raise Exception('Unsupported digest AUTH')
      
    
    def authDomainUser(self, realmname, username, password, environ):
        """Returns True if this username/password pair is valid for the realm, 
        False otherwise. Used for basic authentication."""
        if self.__pwd and self.__pwd == password:
            return True
        is_valid = self.key_storage.validate(password)
        if is_valid:
            #caching valid key storage password
            self.__pwd = password
        return is_valid
