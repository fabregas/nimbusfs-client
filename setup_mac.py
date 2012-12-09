from setuptools import setup
import sys
import subprocess
sys.path.append('third-party')

p = subprocess.Popen('git describe --always --tag'.split(), stdout=subprocess.PIPE)
out, _ = p.communicate()

APP = ['./id_client/gui/main_window.py']
OPTIONS = {'argv_emulation': False,
           'iconfile': './id_client/gui/resources/app-icon.icns',
           'plist': {'CFBundleShortVersionString': out.strip(),},
           'includes' : ('PySide.QtGui', 'PySide.QtCore', 'wsgidav', 'cherrypy'),
           'semi_standalone': 'False',
           'compressed' : 'True',
           'frameworks' : ('libpyside-python2.7.1.1.dylib', 'libshiboken-python2.7.1.1.dylib'),
           'resources': ['./id_client/gui/resources/login-icon.png',
                            './id_client/gui/resources/logout-icon.png',
                            './id_client/gui/resources/sync-icon.png',
                            './id_client/gui/resources/qt.conf',
                            './id_client/gui/resources/menu-exit-icon.png',
                            './id_client/gui/resources/menu-login-icon.png',
                            './id_client/gui/resources/menu-logout-icon.png',
                            '/usr/lib/libpyside-python2.7.1.1.dylib',
                            '/usr/lib/libshiboken-python2.7.1.1.dylib']
          }

setup(
    name= 'Idepositbox',
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app']
)
