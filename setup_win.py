import os
import sys
from cx_Freeze import setup, Executable
sys.path.append(os.path.dirname(__file__))
from id_client.version import VERSION

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"packages": ["dbhash", "dumbdbm", "cherrypy", "wsgidav",\
        'PySide.QtGui', 'PySide.QtCore', 'PySide.QtWebKit', 'PySide.QtNetwork'], \
        "excludes": ["tkinter", "tk", "tcl"],
        'include_files': [('./id_client/gui/resources/loading.gif', ''),
                        ('./id_client/gui/resources/login-icon.png', ''),
                        ('./id_client/gui/resources/logout-icon.png', ''),
                        ('./id_client/gui/resources/sync-icon.png', ''),
                        ('./id_client/gui/resources/menu-exit-icon.png', ''),
                        ('./id_client/gui/resources/menu-manage-icon.png', ''),
                        ('./id_client/gui/resources/app-icon.png', ''),
                        ('./id_client/gui/resources/app-icon.ico', ''),
                        ('./id_client/web/static', ''),
                        ('./third-party/OpenSSL', ''),
                        ('./third-party/imageformats', ''),
                        ('./id_client/security/fat_img.zip', '')]}

# GUI applications require a different base on Windows (the default is for a
# console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(  name = "iDepositBox",
        version = VERSION,
        license = 'iDepositBox software',
        author = 'iDepositBox software',
        url = 'http://idepositbox.com',
        description = "iDepositBox service client",
        options = {"build_exe": build_exe_options,\
                    'bdist_msi': {'upgrade_code': '{87654321-ACDC-EF12-1234-123456789012}'}},
        executables = [Executable("./id_client/gui/main_window.py", base=base, \
                        targetName='iDepositBox.exe', icon='./id_client/gui/resources/app-icon.ico', \
                        shortcutName='iDepositBox', shortcutDir='DesktopFolder'),
                       Executable("./bin/idepositbox_cli"),
                       Executable("./id_client/client_daemon.py")])

