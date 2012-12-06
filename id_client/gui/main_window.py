#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.gui.main_window
@author Konstantin Andrusenko
@date December 06, 2012
"""

import os
import sys

from PySide.QtCore import *
from PySide.QtGui import *
import PySide

from id_client.idepositbox_client import IdepositboxClient
from id_client.config import Config
from id_client.constants import SPT_TOKEN_BASED, SPT_FILE_BASED
from security_provider_conf_dialog import SecurityProviderConfigDialog


RESOURCES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'resources')

LOGOUT_ICON = os.path.join(RESOURCES_DIR, "logout-icon.png")
LOGIN_ICON = os.path.join(RESOURCES_DIR, "login-icon.png")
SYNC_ICON = os.path.join(RESOURCES_DIR, "sync-icon.png")

LM_LOGIN = unicode('Login')
LM_LOGOUT = unicode('Logout')
LM_EXIT = unicode('Exit')

class SystemTrayIcon(QSystemTrayIcon):
    def __init__(self, parent=None):
        super(SystemTrayIcon, self).__init__(parent)

        self.is_login = False

        self.login_act = QAction(LM_LOGIN, parent)
        self.login_act.triggered.connect(self.onLoginLogout)
        self.exit_act = QAction(LM_EXIT, parent)
        self.exit_act.triggered.connect(self.onClose)

        self.tray_menu = QMenu(parent)
        self.tray_menu.addAction(self.login_act)
        self.tray_menu.addAction(self.exit_act)

        self.setIcon(QIcon(LOGOUT_ICON))
        self.setContextMenu( self.tray_menu )

        self.configure_service()

        self.show()

        self.idepositbox_client = IdepositboxClient()
        if Config().security_provider_type == SPT_FILE_BASED:
            self.service_login()

    def configure_service(self):
        config = Config()
        if config.key_storage_path:
            return

        dialog = SecurityProviderConfigDialog()
        ret = dialog.exec_()
        if not ret:
            raise Exception('Security provider does not configured!')

        config.security_provider_type = dialog.provider_type
        config.key_storage_path = dialog.key_storage_path
        config.save()

    def on_token_event(self, event, data):
        if event == UTE_TOKEN_INSERTED:
            self.service_login()
        elif event == UTE_TOKEN_REMOVED:
            self.service_logout()

    def show_information(self, title, message):
        QMessageBox.information(None, title, message)

    def show_error(self, message):
        QMessageBox.critical(None, 'Error', message)

    def show_question(self, title, message):
        reply = QMessageBox.question(None, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            return True
        else:
            return False

    def get_password(self, message):
        msg, is_ok = QInputDialog.getText(None, 'Password', message, QLineEdit.Password)
        if is_ok:
            return msg
        return None

    def onLoginLogout(self):
        if self.is_login:
            self.service_logout()
        else:
            self.service_login()

    def service_login(self):
        try:
            passws = self.get_password('Please, enter password for key storage')

            self.idepositbox_client.start(passws)

            self.login_act.setText(LM_LOGOUT)
            self.setIcon(QIcon(LOGIN_ICON))
            self.is_login = True
        except Exception, err:
            self.show_error('Service does not started.\nDetails: %s'%err)
        else:
            config = Config()
            self.show_information('Service information', \
                    'Service is started!\nYou can mount WebDav resource by URL http://%s:%s/' \
                    %(config.webdav_bind_host, config.webdav_bind_port))

    def service_logout(self):
        try:
            self.idepositbox_client.stop()

            self.login_act.setText(LM_LOGIN)
            self.setIcon(QIcon(LOGOUT_ICON))
            self.is_login = False
        except Exception, err:
            self.show_error('Service does not stopped.\nDetails: %s'%err)

    def onClose(self):
        if not self.show_question('Exit?', 'Are you sure that you want to exit?!'):
            return

        try:
            self.service_logout()
        except Exception, err:
            self.show_error('Service does not stopped.\nDetails: %s'%err)
        finally:
            qApp.exit()



def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    try:
        tray = SystemTrayIcon()
    except Exception, err:
        print err
        sys.exit(1)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
