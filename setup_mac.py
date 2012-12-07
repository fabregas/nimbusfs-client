from setuptools import setup
import sys
sys.path.append('third-party')

#'git describe --always --tag'

APP = ['./id_client/gui/main_window.py']
OPTIONS = {'argv_emulation': False,
           'iconfile': './id_client/gui/resources/app-icon.icns',
           'plist': {'CFBundleShortVersionString':'0.1.1',},
           'includes' : ('PySide.QtGui', 'PySide.QtCore', 'wsgidav', 'cherrypy'),
           'semi_standalone': 'False',
           'compressed' : 'True',
           'frameworks' : ('libpyside-python2.7.1.1.dylib', 'libshiboken-python2.7.1.1.dylib'),
           'resources': ['./id_client/gui/resources/login-icon.png',
                            './id_client/gui/resources/logout-icon.png',
                            './id_client/gui/resources/qt.conf',
                            '/usr/lib/libpyside-python2.7.1.1.dylib',
                            '/usr/lib/libshiboken-python2.7.1.1.dylib']
          }

setup(
    name= 'IdepositboxClient',
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app']
)
