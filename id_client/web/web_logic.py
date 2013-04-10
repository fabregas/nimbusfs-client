import os

from wsgi_app import UrlHandler
from wsgi_app import WSGIApplication

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
        status = idepositbox_client.status if idepositbox_client is not None else 'stopped'
        if status == 'started':
            if idepositbox_client.nibbler.has_incomlete_operations():
                sync_stat = 1
            else:
                sync_stat = 0

        return self.json_source({'service_status': status,
                                    'sync_status': sync_stat})



HANDLERS_MAP = [('/get_menu', GetMenuHandler()),
                ('/get_service_status', GetServiceStatusHandler()),
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


