import os
import json
import threading
from cherrypy import wsgiserver 
from datetime import datetime, timedelta
import urlparse

CERT = '''
-----BEGIN CERTIFICATE-----
MIIECTCCAvGgAwIBAgIBAjANBgkqhkiG9w0BAQUFADCBojEUMBIGA1UEAwwLaURl
cG9zaXRCb3gxCzAJBgNVBAYTAlVBMQ0wCwYDVQQIDARLaWV2MQ0wCwYDVQQHDARL
aWV2MR0wGwYDVQQKDBRpRGVwb3NpdEJveCBzb2Z0d2FyZTEdMBsGA1UECwwUcm9v
dC5pZGVwb3NpdGJveC5jb20xITAfBgkqhkiG9w0BCQEWEmNhQGlkZXBvc2l0Ym94
LmNvbTAgFw0xMjEyMjAwMjQwNTZaGA8zMDM2MDQxNjAyNDA1NlowgZUxIDAeBgNV
BAMTF0Jhc2UgY2xpZW50IGNlcnRpZmljYXRlMQ0wCwYDVQQHEwRLaWV2MR0wGwYD
VQQKExRpRGVwb3NpdEJveCBzb2Z0d2FyZTEgMB4GA1UECxMXY2xpZW50cy5pZGVw
b3NpdGJveC5jb20xITAfBgkqhkiG9w0BCQEWEmNhQGlkZXBvc2l0Ym94LmNvbTCC
ASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBANN1L892pW/13djMqbNkI4HK
b4nT8k9jBDhMUroFgofsXVt0UC4LwiZRWBqRK93+Rgdky8waNsydn7ZjcuMxIQSl
gadokOnalw8KioFdB/0R7CDeDMAzKO/s10l57eII+lJfXnjOCt1RMt2lV7dQvuBw
UaX8D05mx7XhLAlQvzG7CFwa8aUqy5EcT/3snbNL+9hwHJ67g7zR7H0I/QsVvkM6
4xVEVTGlx+5SEPMl6c6d3+/WnwaCadh0sUA7R+kaMJ/IZs9eZ5NoJ7V2h/u9Ivd5
sNJNZT32CNKddg/d9liysEdh7F+TrJDZWs5mLPWSa6t7PexphP7c94XEiZaNg0cC
AwEAAaNTMFEwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUXNc4t0FIjF5XrTjA
l2T4WS54GYkwHwYDVR0jBBgwFoAUiKKO24Q3IoFDu5XPnStyCivOmi8wDQYJKoZI
hvcNAQEFBQADggEBABEzh+sJIkleiGpGBEwLJS1xrQRxnbM5ggYZ/kTEAXv+lQ5b
IzfrpZD3LntMbtHVuF7TDeJzk/6u2ahBbHvT22ZOD0ArbNJ/Imu7cA6XwclWyDZt
ilpcy+Wic36c87HR3nmkX6VzHojeYLvIR72sBfVg56WGwmu7PlsyGS6DU9KtJYlm
EdSFLtHyYDCvO33dRRkiVzNXOPJMov3KQQ0WIy563QtaD4RX2q0o//qW+ThtSBvZ
ntl6OnUfgznymuICRkP9dokwxB/uqv3jen0L221PZDFv2TptWfN/qMcOhg9IyDK7
NcmBEDxKUBi09LThB8VKS5eevKwqRun9vhRm9xg=
-----END CERTIFICATE-----
'''

def get_payment_info(pay_key, cert_cn):
    if pay_key == 'fake':
        raise Exception('Invalid payment key!')

    return json.dumps({'service_term': 555, 
                        'service_capacity': 1000,
                        'status': 'WAIT_FOR_USER',
                        'cert_cn': cert_cn})

def generate_certificate(pay_key, cert_req_pem):
    if pay_key == 'fake':
        raise Exception('Invalid payment key!')

    return CERT.strip()


def web_app(environ, start_response):
    try:
        body= ''
        try:
            length = int(environ.get('CONTENT_LENGTH', '0'))
        except ValueError:
            length= 0

        if length != 0:
            body = environ['wsgi.input'].read(length)

        params = dict(urlparse.parse_qs(body))

        def safe_get(key):
            ret = params.get(key, None)
            if ret is None:
                raise Exception('%s expected!'%key)
            return ret[0]

        path = environ['PATH_INFO']

        if environ['REQUEST_METHOD'] != 'POST':
            raise Exception('POST method expected!')

        if path == '/get_payment_info':
            pay_key = safe_get('payment_key')
            cert_cn = params.get('cert_cn', None)
            if cert_cn:
                cert_cn = cert_cn[0]
            resp = get_payment_info(pay_key, cert_cn)
        elif path == '/generate_certificate':
            pay_key = safe_get('payment_key')
            cert_req_pem = safe_get('cert_req_pem')

            resp = generate_certificate(pay_key, cert_req_pem)
        else:
            raise Exception('Unexpected path "%s"!'%path)

        status = '200 OK'
        response_headers = [('Content-type','text/plain')]
        start_response(status, response_headers)
        return [resp]
    except Exception, err:
        response_headers = [('Content-type','text/plain')]
        start_response('505 Internal Server Error', response_headers)
        return [str(err)]


class MockedCAServer(threading.Thread):
    def __init__(self, bind_port):
        threading.Thread.__init__(self)
        self.bind_port = bind_port
        self.server = None

    def run(self):
        self.server = wsgiserver.CherryPyWSGIServer(('127.0.0.1', self.bind_port), web_app,)
        self.server.start()

    def stop(self):
        self.server.stop()


