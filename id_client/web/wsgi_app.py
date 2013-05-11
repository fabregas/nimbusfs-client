#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.web.wsgi_app
@author Konstantin Andrusenko
@date April 23, 2013
"""
import os
import re
import json
import urllib
import mimetypes
import cgi

class NotFound(Exception):
    pass

class UrlHandler:
    __static_dir = None

    @classmethod
    def setup_static_dir(cls, dir_path):
        cls.__static_dir = dir_path

    def __call__(self, environ, start_response, *args):
        try:
            cont_type, resp = self.on_process(environ, *args)
            status = '200 OK'
        except NotFound, err:
            status = '404 Not Found'
            cont_type = 'text/plain'
            resp = 'Requested page does not found! {%s}'%err
        except Exception, err:
            status = '500 Internal Server Error'
            cont_type = 'text/plain'
            resp = str(err.replace('\n', '<br/>'))

        headers = [('Content-type', cont_type), ('Content-length', str(len(resp)))]
        start_response(status, headers)
        return [resp]

    def on_process(self, env, *args):
        pass

    def file_source(self, file_name):
        path = os.path.join(self.__static_dir, file_name)
        if not os.path.exists(path):
            raise NotFound('File %s does not found!'%path)

        c_type, enc = mimetypes.guess_type(file_name)
        if not c_type:
            c_type = 'text/plain'
        data = open(path).read()
        return c_type, data

    def json_source(self, data):
        json_data = json.dumps(data)
        return 'application/json', json_data

    def get_post_form(self, environ):
        input = environ['wsgi.input']
        fs = cgi.FieldStorage(fp=input, environ=environ, keep_blank_values=1)
        params = {}
        for key in fs.keys():
            params[ key ] = fs[ key ].value
        return params


class WSGIApplication:
    def __init__(self, idepositbox_app, handlers_map, static_dir):
        self.__idepositbox_app = idepositbox_app
        self.__handlers_map = []
        UrlHandler.setup_static_dir(static_dir)
        for r_val, handler in handlers_map:
            if not r_val.endswith('$'):
                r_val += '$'
            self.__handlers_map.append((re.compile(r_val), handler))

    def __find_handler(self, path):
        for re_path, handler in self.__handlers_map:
            found = re.match(re_path, path)
            if found:
                return handler, found.groups()

        raise NotFound('Page %s does not found!'%path)

    def __call__(self, environ, start_response):
        path = urllib.unquote(environ["PATH_INFO"])
        if isinstance(path, unicode):
            path = path.encode("utf8")

        if not path:
            path = '/'

        handler, args = self.__find_handler(path)
        environ['idepositbox_app'] = self.__idepositbox_app
        environ['path'] = path
        for v in handler(environ, start_response, *args):
            yield v
        return


