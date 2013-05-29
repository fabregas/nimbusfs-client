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
import json
import httplib
import socket
import copy
from subprocess import Popen, PIPE

from PySide.QtCore import *
from PySide.QtGui import *
import PySide

import id_client
from id_client.idepositbox_client import logger
from id_client.constants import *
from id_client.gui.webview_dialog import WebViewDialog

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(id_client.__file__), '../'))
MGMT_CLI_PATH = os.path.abspath(os.path.join(CUR_DIR, '../../bin/idepositbox_cli'))
RESOURCES_DIR = os.path.join(CUR_DIR, 'resources')

if not os.path.exists(RESOURCES_DIR):
    RESOURCES_DIR = CUR_DIR

if not os.path.exists(MGMT_CLI_PATH):
    MGMT_CLI_PATH = os.path.abspath(os.path.join(CUR_DIR, 'idepositbox_cli'))

LOGOUT_ICON = os.path.join(RESOURCES_DIR, "logout-icon.png")
LOGIN_ICON = os.path.join(RESOURCES_DIR, "login-icon.png")
SYNCDATA_ICON = os.path.join(RESOURCES_DIR, "sync-icon.png")
APP_ICON = os.path.join(RESOURCES_DIR, "app-icon.png")

MENU_MANAGE_ICON = os.path.join(RESOURCES_DIR, "menu-manage-icon.png")
MENU_EXIT_ICON = os.path.join(RESOURCES_DIR, "menu-exit-icon.png")

LM_MANAGE = unicode('Manage...')
LM_EXIT = unicode('Exit')

STATUS_STOPPED = 'stopped'
STATUS_STARTED = 'started'
STATUS_SYNCING = 'syncing'

DAEMON_PORT = 8880

MGMT_CLI_RUNCMD = [sys.executable, MGMT_CLI_PATH]
ENV = copy.copy(os.environ)
ENV['IDB_LIB_PATH'] = LIB_DIR


class SystemTrayIcon(QSystemTrayIcon):
    def __init__(self, parent=None):
        super(SystemTrayIcon, self).__init__(parent)

        self.login_icon = QIcon(self.__get_icon_src(LOGIN_ICON))
        self.logout_icon = QIcon(self.__get_icon_src(LOGOUT_ICON))
        self.syncdata_icon = QIcon(self.__get_icon_src(SYNCDATA_ICON))

        self.manage_act = QAction(QIcon(MENU_MANAGE_ICON), LM_MANAGE, parent)
        self.exit_act = QAction(QIcon(MENU_EXIT_ICON), LM_EXIT, parent)

        self.tray_menu = QMenu(parent)
        self.tray_menu.addAction(self.manage_act)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.exit_act)

        self.setIcon(self.logout_icon)
        self.setContextMenu(self.tray_menu)
        self.setToolTip('iDepositBox service client')
        
    def __get_icon_src(self, icon_path):
        if sys.platform.startswith('linux'):
            ic = QImage(icon_path)
            #ic = ic.scaled(16, 16)
            ic.invertPixels()
            return QPixmap.fromImage(ic)
        return icon_path

    def on_changed_service_status(self, status):
        if status == STATUS_STOPPED:
            self.setIcon(self.logout_icon)
        elif status == STATUS_STARTED:
            self.setIcon(self.login_icon)
        elif status == STATUS_SYNCING:
            self.setIcon(self.syncdata_icon)
        else:
            raise Exception('Unexpected service status "%s"'%status)

    def show_information(self, title, message):
        if self.supportsMessages():
            self.showMessage(title, message)


class CheckSyncStatusThread(QThread):
    def __init__(self, wind):
        QThread.__init__(self, wind)
        self.wind = wind
        self.stopped = True

    def run(self):
        self.stopped = False
        old_status = None
        mgmt_addr = '127.0.0.1:%s'%DAEMON_PORT
        time.sleep(2)

        while not self.stopped:
            try:
                conn = httplib.HTTPConnection(mgmt_addr)
                try:
                    conn.request('GET', '/get_service_status')
                    response = conn.getresponse()
                    if response.status != 200:
                        raise Exception('mgmt service error! [%s %s] %s'%(response.status, response.reason, response.read()))
                    data = response.read()
                except socket.error, err:
                    raise Exception('Mgmt server does not respond! Details: %s'%err)
                finally:
                    conn.close()

                data = json.loads(data)
                if data.get('service_status', CS_FAILED) != CS_STARTED:
                    status = STATUS_STOPPED
                else:
                    if data.get('sync_status', SS_SYNC_PROGRESS):
                        status = STATUS_SYNCING
                    else:
                        status = STATUS_STARTED

                if status != old_status:
                    self.wind.changed_service_status.emit(status)
                old_status = status
            except Exception, err:
                logger.error('CheckSyncStatusThread: %s'%err)
            finally:
                time.sleep(2)

    def stop(self):
        self.stopped = True

class MainWind(WebViewDialog):
    changed_service_status = Signal(str)

    def __init__(self, parent=None):
        super(MainWind, self).__init__(parent)

        self.__first_event = True
        self.systray = SystemTrayIcon(self)
        self.changed_service_status.connect(self.on_changed_service_status)
        self.systray.manage_act.triggered.connect(self.onManage)
        self.systray.exit_act.triggered.connect(self.onClose)
        self.setWindowIcon(QIcon(APP_ICON))
        self.setWindowState(Qt.WindowMaximized)
        self.setVisible(False)

        proc = Popen(MGMT_CLI_RUNCMD+['restart'], stdout=PIPE, stderr=PIPE, env=ENV)
        cout, cerr = proc.communicate()
        print(cout)
        if proc.returncode:
            self.show_error('Management console does not started!\nDetails: %s'%cerr)
            raise Exception('mgmt server does not started by %s'%MGMT_CLI_RUNCMD)

        self.check_sync_status_thr = CheckSyncStatusThread(self)
        self.check_sync_status_thr.start()

        self.systray.activated.connect(self.on_icon_activated)
        if self.systray.isSystemTrayAvailable():
            self.systray.show()

    def on_changed_service_status(self, status):
        if self.__first_event:
            if self.systray.isVisible():
                self.systray.show_information('Information', 'iDepostiBox client was started successfully')
            else:
                self.onManage()
            self.__first_event = False

        if self.systray.isVisible():
            self.systray.on_changed_service_status(status)

    def on_icon_activated(self, reason):
        if reason in (self.systray.ActivationReason.Trigger, self.systray.ActivationReason.DoubleClick):
            self.systray.contextMenu().popup(QCursor.pos())

    def onManage(self):
        self.load('http://127.0.0.1:%s/'%DAEMON_PORT)
        self.setVisible(True)

    def show_error(self, message):
        QMessageBox.critical(self, 'Error', message)

    def closeEvent(self, event):
        if not self.systray.isVisible():
            self.onClose()
            event.ignore()
        else:
            event.accept()

    def onClose(self):
        if not self.show_question('Exit?', 'Are you sure that you want to exit?!', self):
            return

        try:
            proc = Popen(MGMT_CLI_RUNCMD+['stop'], stdout=PIPE, stderr=PIPE, env=ENV)
            cout, cerr = proc.communicate()
            print (cout)
            if proc.returncode:
                self.show_error('Management console does not stopped!\nDetails: %s'%cerr)

            self.check_sync_status_thr.stop()
            self.check_sync_status_thr.wait()
        finally:
            qApp.exit()

    @classmethod
    def show_question(cls, title, message, parent=None):
        reply = QMessageBox.question(parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            return True
        else:
            return False

    @classmethod
    def isMgmtServerStarted(cls):
        proc = Popen(MGMT_CLI_RUNCMD+['status'], stdout=PIPE, stderr=PIPE, env=ENV)
        cout, cerr = proc.communicate()
        print (cout)
        if proc.returncode:
            return False
        return True

def main():
    app = QApplication(sys.argv)
    if MainWind.isMgmtServerStarted():
        if not MainWind.show_question('WARNING', 'Management console is already started! Do you really want start application?'):
            sys.exit(1)
    app.setQuitOnLastWindowClosed(False)
    try:
        mw = MainWind()
    except Exception, err:
        print err
        sys.exit(1)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
