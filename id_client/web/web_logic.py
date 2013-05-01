#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.web.web_logic
@author Konstantin Andrusenko
@date April 23, 2013
"""

import os

from wsgi_app import UrlHandler
from wsgi_app import WSGIApplication
from id_client.constants import *

class StaticPage(UrlHandler):
    def on_process(self, env, *args):
        return self.file_source(args[0])

class MainPage(UrlHandler):
    def on_process(self, env, *args):
        return self.file_source('html/index.html')

class GetPageHandler(UrlHandler):
    def on_process(self, env, *args):
        return self.file_source('html/%s'%args[0])

class GetMenuHandler(UrlHandler):
    def on_process(self, env, *args):
        return self.json_source(MENU_MAP)

class GetServiceStatusHandler(UrlHandler):
    def on_process(self, env, *args):
        idepositbox_client = env['idepositbox_app']
        sync_stat = -1
        if idepositbox_client is not None:
            status = idepositbox_client.status
            has_ks = idepositbox_client.key_storage_status()
        else:
            status = 'stopped'
            has_ks = False

        if status == 'started':
            if idepositbox_client.nibbler.has_incomlete_operations():
                sync_stat = 1
            else:
                sync_stat = 0

        return self.json_source({'service_status': status,
                                    'sync_status': sync_stat,
                                    'has_keystorage': has_ks})


class GetSettingsHandler(UrlHandler):
    def on_process(self, env, *args):
        idepositbox_client = env['idepositbox_app']
        config = idepositbox_client.get_config()
        resp = {'key_storage_path': config.key_storage_path,
                'fabnet_hostname': config.fabnet_hostname,
                'parallel_get_count': config.parallel_get_count,
                'parallel_put_count': config.parallel_put_count,
                'webdav_bind_host': config.webdav_bind_host,
                'webdav_bind_port': config.webdav_bind_port,
                'security_provider_type': config.security_provider_type,
                'mount_type': config.mount_type
                }
        return self.json_source(resp)

class ApplySettingsHandler(UrlHandler):
    def on_process(self, env, *args):
        idepositbox_client = env['idepositbox_app']
        if env['REQUEST_METHOD'].upper() != 'POST':
            raise Exception('POST method exptected!')

        data = self.get_post_form(env)
        try:
            key_storage_path = data.get('key_storage_path', None)
            fabnet_hostname = data.get('fabnet_hostname', None)
            webdav_bind_host = data.get('webdav_bind_host', None)

            if not key_storage_path:
                raise Exception('Please, specify key storage path!')
            if not fabnet_hostname:
                raise Exception('Please, specify Nimbus file system service URL!')
            if not webdav_bind_host:
                raise Exception('Please, specify WebDav server bind hostname')
            
            try:
                data['webdav_bind_port'] = int(data.get('webdav_bind_port', 8080))
            except ValueError:
                raise Exception('Invalid WebDav port number!')

            try:
                data['parallel_get_count'] = int(data.get('parallel_get_count', 2))
            except ValueError:
                raise Exception('Invalid parallel downloads count number!')

            try:
                data['parallel_put_count'] = int(data.get('parallel_put_count', 2))
            except ValueError:
                raise Exception('Invalid parallel uploads count number!')

            if data.get('security_provider_type') not in (SPT_TOKEN_BASED, SPT_FILE_BASED):
                raise Exception('Invalid security provider type!')

            if data.get('mount_type') not in (MOUNT_LOCAL, MOUNT_EXPORT):
                raise Exception('Invalid mount type!')

            if data.get('security_provider_type') == SPT_FILE_BASED:
                kss = idepositbox_client.key_storage_status(SPT_FILE_BASED, key_storage_path)
                if kss == 0:
                    raise Exception('Key storage does not found at %s'%key_storage_path)
                elif kss == -1:
                    raise Exception('Invalid key storage at %s'%key_storage_path)
                data['key_storage_path'] = os.path.abspath(key_storage_path)

            idepositbox_client.update_config(data) 
            
            resp = {'ret_code':0}
        except Exception, err:
            resp = {'ret_code':1, 'ret_message': str(err)}

        return self.json_source(resp)


class StartServiceHandler(UrlHandler):
    def on_process(self, env, *args):
        try:
            idepositbox_client = env['idepositbox_app']
            data = self.get_post_form(env)
            idepositbox_client.start(data.get('password', ''))
            resp = {'ret_code':0}
        except Exception, err:
            resp = {'ret_code':1, 'ret_message': str(err)}
        return self.json_source(resp)

class StopServiceHandler(UrlHandler):
    def on_process(self, env, *args):
        try:
            idepositbox_client = env['idepositbox_app']
            idepositbox_client.stop()
            resp = {'ret_code':0}
        except Exception, err:
            resp = {'ret_code':1, 'ret_message': str(err)}
        return self.json_source(resp)
        
class IsKsExistsHandler(UrlHandler):
    def on_process(self, env, *args):
        try:
            idepositbox_client = env['idepositbox_app']
            data = self.get_post_form(env)

            ks_type = data.get('security_provider_type', SPT_TOKEN_BASED)
            if ks_type not in (SPT_TOKEN_BASED, SPT_FILE_BASED):
                raise Exception('Invalid security provider type!')
            ks_path = data.get('key_storage_path', '')

            kss = idepositbox_client.key_storage_status(ks_type, ks_path)
            resp = {'ret_code':0, 'ks_status': int(kss)}
        except Exception, err:
            resp = {'ret_code':1, 'ret_message': str(err)}
        return self.json_source(resp)
    
class GetKsInfoHandler(UrlHandler):
    def on_process(self, env, *args):
        try:
            idepositbox_client = env['idepositbox_app']
            data = self.get_post_form(env)

            ks_type = data.get('security_provider_type', SPT_TOKEN_BASED)
            if ks_type not in (SPT_TOKEN_BASED, SPT_FILE_BASED):
                raise Exception('Invalid security provider type!')
            ks_path = data.get('key_storage_path', '')
            ks_pwd = data.get('password', None)
            if ks_pwd is None:
                raise Exception('Password does not found!')

            cert = idepositbox_client.get_key_storage_info(ks_type, ks_path, ks_pwd)
            resp = {'ret_code': 0, 'cert': cert}
        except Exception, err:
            resp = {'ret_code': 1, 'ret_message': str(err)}
        return self.json_source(resp)


class GenerateKeyStorageHandler(UrlHandler):
    def on_process(self, env, *args):
        try:
            idepositbox_client = env['idepositbox_app']
            data = self.get_post_form(env)
            idepositbox_client.generate_key_storage(\
                    data['security_provider_type'],
                    data['key_storage_path'],
                    data['act_key'], data['password'])
            resp = {'ret_code': 0}
        except Exception, err:
            resp = {'ret_code': 1, 'ret_message': str(err)}
        return self.json_source(resp)


HANDLERS_MAP = [('/get_menu', GetMenuHandler()),
                ('/get_service_status', GetServiceStatusHandler()),
                ('/start_service', StartServiceHandler()),
                ('/stop_service', StopServiceHandler()),
                ('/get_settings', GetSettingsHandler()),
                ('/apply_settings', ApplySettingsHandler()),
                ('/is_ks_exists', IsKsExistsHandler()),
                ('/get_ks_info', GetKsInfoHandler()),
                ('/generate_key_storage', GenerateKeyStorageHandler()),
                ('/get_page/(.+)', GetPageHandler()),
                ('/static/(.+)', StaticPage()),
                ('/(\w*)', MainPage())]


STATIC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))


MENU_MAP = (('home', 'Home'),
            ('settings', 'Settings'),
#            ('syslog', 'System log'),
            ('key_mgmt', 'Key management'),
            ('about', 'About'),
            ('contact', 'Contact'))


