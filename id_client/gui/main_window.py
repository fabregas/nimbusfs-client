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
import threading
import time

from PySide.QtCore import *
from PySide.QtGui import *
import PySide

from id_client.idepositbox_client import IdepositboxClient, logger
from id_client.config import Config
from id_client.constants import SPT_TOKEN_BASED, SPT_FILE_BASED
from security_provider_conf_dialog import SecurityProviderConfigDialog
from files_inprogress_dialog import FilesInprogressDialog


CUR_DIR = os.path.abspath(os.path.dirname(__file__))
RESOURCES_DIR = os.path.join(CUR_DIR, 'resources')

if not os.path.exists(RESOURCES_DIR):
    RESOURCES_DIR = CUR_DIR

LOGOUT_ICON = os.path.join(RESOURCES_DIR, "logout-icon.png")
LOGIN_ICON = os.path.join(RESOURCES_DIR, "login-icon.png")
SYNCDATA_ICON = os.path.join(RESOURCES_DIR, "sync-icon.png")
MENU_LOGIN_ICON = os.path.join(RESOURCES_DIR, "menu-login-icon.png")
MENU_LOGOUT_ICON = os.path.join(RESOURCES_DIR, "menu-logout-icon.png")
MENU_EXIT_ICON = os.path.join(RESOURCES_DIR, "menu-exit-icon.png")

LM_LOGIN = unicode('Login')
LM_LOGOUT = unicode('Logout')
LM_SYNC_INFO = unicode('Data transmission...')
LM_EXIT = unicode('Exit')


class SystemTrayIcon(QSystemTrayIcon):
    sync_data_inprogress = Signal()
    no_sync_data = Signal()

    def __init__(self, parent=None):
        super(SystemTrayIcon, self).__init__(parent)

        self.is_login = False
        self.sync_status = False

        self.sync_data_inprogress.connect(self.on_sync_data_inprogress)
        self.no_sync_data.connect(self.on_no_sync_data)

        self.login_icon = QIcon(LOGIN_ICON)
        self.logout_icon = QIcon(LOGOUT_ICON)
        self.syncdata_icon = QIcon(SYNCDATA_ICON)

        self.login_act = QAction(QIcon(MENU_LOGIN_ICON), LM_LOGIN, parent)
        self.login_act.triggered.connect(self.onLoginLogout)
        self.sync_info_act = QAction(QIcon(SYNCDATA_ICON), LM_SYNC_INFO, parent)
        self.sync_info_act.triggered.connect(self.onSyncInfo)
        self.exit_act = QAction(QIcon(MENU_EXIT_ICON), LM_EXIT, parent)
        self.exit_act.triggered.connect(self.onClose)

        self.tray_menu = QMenu(parent)
        self.tray_menu.addAction(self.login_act)
        self.tray_menu.addAction(self.sync_info_act)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.exit_act)

        self.setIcon(self.logout_icon)
        self.setContextMenu( self.tray_menu )

        self.configure_service()

        self.show()

        self.idepositbox_client = IdepositboxClient()
        if Config().security_provider_type == SPT_FILE_BASED:
            self.service_login()

        self.check_sync_status_thr = CheckSyncStatusThread(self)
        self.check_sync_status_thr.start()

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
            self.login_act.setIcon(QIcon(MENU_LOGOUT_ICON))
            self.setIcon(self.login_icon)
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
            self.login_act.setIcon(QIcon(MENU_LOGIN_ICON))
            self.setIcon(self.logout_icon)
            self.is_login = False
        except Exception, err:
            self.show_error('Service does not stopped.\nDetails: %s'%err)
        finally:
            self.check_sync_status_thr.stop()
            self.check_sync_status_thr.wait()

    def on_sync_data_inprogress(self):
        self.sync_status = True
        self.setIcon(self.syncdata_icon)

    def on_no_sync_data(self):
        if not self.sync_status:
            return

        self.setIcon(self.login_icon)

    def onSyncInfo(self):
        f_inprogress_dialog = FilesInprogressDialog(self.idepositbox_client.nibbler)
        f_inprogress_dialog.exec_()

    def onClose(self):
        if not self.show_question('Exit?', 'Are you sure that you want to exit?!'):
            return

        try:
            self.service_logout()
        except Exception, err:
            self.show_error('Service does not stopped.\nDetails: %s'%err)
        finally:
            qApp.exit()


class CheckSyncStatusThread(QThread):
    def __init__(self, tray):
        QThread.__init__(self, tray)
        self.tray = tray
        self.stopped = True

    def run(self):
        self.stopped = False
        while not self.stopped:
            try:
                ops = self.tray.idepositbox_client.nibbler.inprocess_operations()
                if ops:
                    self.tray.sync_data_inprogress.emit()
                else:
                    self.tray.no_sync_data.emit()

                time.sleep(1)
            except Exception, err:
                logger.error('CheckSyncStatusThread: %s'%err)

    def stop(self):
        self.stopped = True

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
