from setuptools import setup
import sys
sys.path.append('third-party')

APP = ['./id_client/gui/main_window.py']
OPTIONS = {'argv_emulation': False,
           'includes' : ('PySide.QtGui', 'wsgidav', 'cherrypy'),
           'semi_standalone': 'False',
           'compressed' : 'True',
           'frameworks' : ('libpyside-python2.7.dylib',),
           'resources': ['./id_client/gui/resources/login-icon.png',
                            './id_client/gui/resources/logout-icon.png',
                            './id_client/gui/resources/qt.conf']
          }

setup(
    name= 'IdepositboxClient',
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
