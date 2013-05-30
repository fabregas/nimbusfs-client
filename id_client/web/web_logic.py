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
from id_client.media_storage import AbstractMediaStoragesManager
from id_client.idepositbox_client import logger, SM_TYPES_MAP
from nimbus_client.core.exceptions import NoCertFound

KB = 1024
MB = 1024.*KB
GB = 1024.*MB

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
        idepositbox_client = env['idepositbox_app']
        version = idepositbox_client.get_version() 
        return self.json_source({'menu': MENU_MAP, 'version': version})

class GetServiceStatusHandler(UrlHandler):
    def on_process(self, env, *args):
        idepositbox_client = env['idepositbox_app']
        sync_stat = SS_UNKNOWN
        if idepositbox_client is not None:
            status = idepositbox_client.get_status()
        else:
            status = 'stopped'

        events_count = idepositbox_client.get_events_count()
        up_perc = down_perc = 100
        if status == 'started':
            up_perc, down_perc = idepositbox_client.get_nibbler().transactions_progress()
            if up_perc != 100 or down_perc != 100:
                sync_stat = SS_SYNC_PROGRESS
            else:
                sync_stat = SS_ALL_SYNC

        return self.json_source({'service_status': status,
                                    'upload_progress': up_perc,
                                    'download_progress': down_perc,
                                    'sync_status': sync_stat,
                                    'events_count': events_count})


def file_size(size):
    if size < KB:
        return '%i b'%size
    if size < MB:
        return '%i Kb'%(size/KB)
    if size < GB:
        return '%.1f Mb'%(size/MB)
    return '%.2f Gb'%(size/GB)

class GetInprogressFilesHandler(UrlHandler):
    def on_process(self, env, *args):
        idepositbox_client = env['idepositbox_app']
        ret_list = []
        if idepositbox_client.get_status() == 'started':
            operations = idepositbox_client.get_nibbler().inprocess_operations()
            for oper in operations:
                ret_list.append((oper.is_upload, os.path.basename(oper.file_path), \
                        oper.status, file_size(oper.size), file_size(oper.progress_size)))

        return self.json_source({'inprogress_list': ret_list})

def parse_ks(data):
    key_storage = data.get('__key_storage', None)
    if not key_storage:
        raise Exception('Please, specify key chain path!')
    idx = key_storage.find(':')
    security_provider_type = key_storage[:idx]
    key_storage_path = key_storage[idx+1:]
    if security_provider_type not in SM_TYPES_MAP.keys():
        raise Exception('Invalid security provider type "%s"'%security_provider_type)
    return security_provider_type, key_storage_path


class GetSettingsHandler(UrlHandler):
    def on_process(self, env, *args):
        idepositbox_client = env['idepositbox_app']
        config = idepositbox_client.get_config()
        resp = {
                'fabnet_hostname': config.fabnet_hostname,
                'parallel_get_count': config.parallel_get_count,
                'parallel_put_count': config.parallel_put_count,
                'webdav_bind_host': config.webdav_bind_host,
                'webdav_bind_port': config.webdav_bind_port,
                'mount_type': config.mount_type,
                }
        return self.json_source(resp)

class GetMediaDevicesHandler(UrlHandler):
    def on_process(self, env, *args):
        idepositbox_client = env['idepositbox_app']
        ms_list = idepositbox_client.get_available_media_storages()
        available_ks_list = []
        for ms in ms_list:
            label = ms.label
            ks_status = idepositbox_client.key_storage_status(ms.ks_type, ms.path)
            item = (label, '%s:%s'%(ms.ks_type, ms.path), ks_status)

            if idepositbox_client.get_last_key_storage_type() == ms.ks_type \
                    and idepositbox_client.get_last_key_storage_path() == ms.path:
                available_ks_list.insert(0, item)
            else:
                available_ks_list.append(item)

        resp = {
                '__available_ks_list': available_ks_list
                }
        return self.json_source(resp)

class ApplySettingsHandler(UrlHandler):
    def on_process(self, env, *args):
        idepositbox_client = env['idepositbox_app']
        if env['REQUEST_METHOD'].upper() != 'POST':
            raise Exception('POST method exptected!')

        data = self.get_post_form(env)
        try:
            fabnet_hostname = data.get('fabnet_hostname', None)
            webdav_bind_host = data.get('webdav_bind_host', None)

            if not webdav_bind_host:
                raise Exception('Please, specify WebDav server bind hostname')
            
            try:
                data['webdav_bind_port'] = int(data.get('webdav_bind_port', 8080))
            except ValueError:
                raise Exception('Invalid WebDav port number!')

            try:
                data['parallel_get_count'] = int(data.get('parallel_get_count', 2))
                if data['parallel_get_count'] not in range(1, 21): 
                    raise ValueError()
            except ValueError:
                raise Exception('Invalid simultaneous downloads count number! Expecting numeric value in range [1-20]')

            try:
                data['parallel_put_count'] = int(data.get('parallel_put_count', 2))
                if data['parallel_put_count'] not in range(1, 21): 
                    raise ValueError()
            except ValueError:
                raise Exception('Invalid simultaneous uploads count number! Expecting numeric value in range [1-20]')

            if data.get('mount_type') not in (MOUNT_LOCAL, MOUNT_EXPORT):
                raise Exception('Invalid mount type!')

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

            security_provider_type, key_storage_path = parse_ks(data)
            kss = idepositbox_client.key_storage_status(security_provider_type, key_storage_path)
            if kss == 0:
                raise Exception('Key chain does not found at %s'%key_storage_path)
            elif kss == -1:
                raise Exception('Invalid key chain at %s'%key_storage_path)

            idepositbox_client.start(security_provider_type, key_storage_path, data.get('password', ''))
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

            ks_type, ks_path = parse_ks(data)
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

            ks_type, ks_path = parse_ks(data)
            ks_pwd = data.get('password', None)
            if ks_pwd is None:
                raise Exception('Password does not found!')

            cert = idepositbox_client.get_key_storage_info(ks_type, ks_path, ks_pwd)
            resp = {'ret_code': 0, 'cert': cert}
        except NoCertFound, err:
            resp = {'ret_code': 123, 'ret_message':str(err)}
        except Exception, err:
            resp = {'ret_code': 1, 'ret_message': str(err)}
        return self.json_source(resp)


class GenerateKeyStorageHandler(UrlHandler):
    def on_process(self, env, *args):
        try:
            idepositbox_client = env['idepositbox_app']
            data = self.get_post_form(env)
            ks_type, ks_path = parse_ks(data)
            idepositbox_client.generate_key_storage(\
                    ks_type, ks_path,
                    data['act_key'], data['password'])
            resp = {'ret_code': 0}
        except NoCertFound, err:
            resp = {'ret_code': 123, 'ret_message':str(err)}
        except Exception, err:
            logger.error('GenerateKeyStorageHandler: %s'%err)
            logger.traceback_info()            
            resp = {'ret_code': 1, 'ret_message': str(err)}
        return self.json_source(resp)

class GetEventsHandler(UrlHandler):
    def on_process(self, env, *args):
        try:
            idepositbox_client = env['idepositbox_app']
            events_obj = idepositbox_client.get_events()
            events = []
            for event_obj in events_obj:
                events.append((event_obj.get_datetime().strftime("%d-%m-%y %H:%M:%S"),\
                        event_obj.get_message()))
            events.reverse()
            resp = {'ret_code': 0, 'events': events}
        except Exception, err:
            resp = {'ret_code': 1, 'ret_message': str(err)}
        return self.json_source(resp)




HANDLERS_MAP = [('/get_menu', GetMenuHandler()),
                ('/get_service_status', GetServiceStatusHandler()),
                ('/get_inprogress_files', GetInprogressFilesHandler()),
                ('/start_service', StartServiceHandler()),
                ('/stop_service', StopServiceHandler()),
                ('/get_settings', GetSettingsHandler()),
                ('/apply_settings', ApplySettingsHandler()),
                ('/is_ks_exists', IsKsExistsHandler()),
                ('/get_ks_info', GetKsInfoHandler()),
                ('/generate_key_storage', GenerateKeyStorageHandler()),
                ('/get_media_devices', GetMediaDevicesHandler()),
                ('/get_events', GetEventsHandler()),
                ('/get_page/(.+)', GetPageHandler()),
                ('/static/(.+)', StaticPage()),
                ('/(\w*)', MainPage())]


STATIC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))


MENU_MAP = (('home', 'Home'),
            ('settings', 'Settings'),
#            ('syslog', 'System log'),
            ('key_mgmt', 'Key management'),
            ('about', 'About'))


