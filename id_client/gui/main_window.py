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
from datetime import datetime, timedelta

from PySide.QtCore import *
from PySide.QtGui import *
import PySide

import id_client
from id_client.utils import logger
from id_client.constants import *
from id_client.gui.webview_dialog import WebViewDialog
from id_client.utils import Subprocess


if hasattr(sys, "frozen") and sys.platform == 'win32':
    CUR_DIR = os.path.dirname(os.path.abspath(sys.executable))
    MGMT_CLI_RUNCMD = os.path.join(CUR_DIR, 'idepositbox_cli.exe')
else:
    CUR_DIR = os.path.abspath(os.path.dirname(__file__))

    MGMT_CLI_PATH = os.path.abspath(os.path.join(CUR_DIR, '../../bin/idepositbox_cli'))
    if not os.path.exists(MGMT_CLI_PATH):
        MGMT_CLI_PATH = os.path.abspath(os.path.join(CUR_DIR, 'idepositbox_cli'))
    MGMT_CLI_RUNCMD = '%s %s'%(sys.executable, MGMT_CLI_PATH)

RESOURCES_DIR = os.path.join(CUR_DIR, 'resources')
if not os.path.exists(RESOURCES_DIR):
    RESOURCES_DIR = CUR_DIR

LOGOUT_ICON = os.path.join(RESOURCES_DIR, "logout-icon.png")
LOGIN_ICON = os.path.join(RESOURCES_DIR, "login-icon.png")
SYNCDATA_ICON = os.path.join(RESOURCES_DIR, "sync-icon.png")
APP_ICON = os.path.join(RESOURCES_DIR, "app-icon.png")

MENU_MANAGE_ICON = os.path.join(RESOURCES_DIR, "menu-manage-icon.png")
MENU_STATUS_ICON = os.path.join(RESOURCES_DIR, "menu-status-icon.png")
MENU_EXIT_ICON = os.path.join(RESOURCES_DIR, "menu-exit-icon.png")

LOADING_IMG = os.path.join(RESOURCES_DIR, "loading.gif")

LM_MANAGE = unicode('Manage...')
LM_EXIT = unicode('Exit')

STATUS_STOPPED = 'stopped'
STATUS_STARTED = 'started'
STATUS_SYNCING = 'syncing'

DAEMON_PORT = 8880

MAX_CONSOLE_WAIT_TIME = 120 #in seconds

ENV = copy.copy(os.environ)
ENV['IDB_LIB_PATH'] = os.path.abspath(os.path.join(os.path.dirname(id_client.__file__), '../'))



class SystemTrayIcon(QSystemTrayIcon):
    def __init__(self, parent=None):
        super(SystemTrayIcon, self).__init__(parent)

        self.login_icon = QIcon(self.__get_icon_src(LOGIN_ICON))
        self.logout_icon = QIcon(self.__get_icon_src(LOGOUT_ICON))
        self.syncdata_icon = QIcon(self.__get_icon_src(SYNCDATA_ICON))

        self.status_act = QAction(QIcon(MENU_STATUS_ICON), '', parent)
        self.status_act.setEnabled(False)
        self.manage_act = QAction(QIcon(MENU_MANAGE_ICON), LM_MANAGE, parent)
        self.exit_act = QAction(QIcon(MENU_EXIT_ICON), LM_EXIT, parent)

        self.tray_menu = QMenu(parent)
        self.tray_menu.addAction(self.status_act)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.manage_act)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.exit_act)

        self.on_changed_service_status(STATUS_STOPPED)
        self.setContextMenu(self.tray_menu)
        self.setToolTip('iDepositBox service client')

    def __get_icon_src(self, icon_path):
        #if sys.platform != 'darwin':
        #    ic = QImage(icon_path)
        #    #ic = ic.scaled(16, 16)
        #    ic.invertPixels()
        #    return QPixmap.fromImage(ic)
        return icon_path

    def on_changed_service_status(self, status, data=None):
        if status == STATUS_STOPPED:
            self.setIcon(self.logout_icon)
            self.status_act.setText('Logged out')
        elif status == STATUS_STARTED:
            self.setIcon(self.login_icon)
            self.status_act.setText('Logged in')
        elif status == STATUS_SYNCING:
            self.setIcon(self.syncdata_icon)
            self.status_act.setText('In progress %s'%data)
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
                conn = httplib.HTTPConnection(mgmt_addr, timeout=10)
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
                progress = None
                if data.get('service_status', CS_FAILED) != CS_STARTED:
                    status = STATUS_STOPPED
                else:
                    if data.get('sync_status', SS_SYNC_PROGRESS):
                        status = STATUS_SYNCING
                        progress = '%i%s'%(int(data.get('sum_progress', 0)), '%')
                    else:
                        status = STATUS_STARTED
                if status == STATUS_SYNCING or status != old_status:
                    self.wind.changed_service_status.emit(status, progress)
                old_status = status
            except Exception, err:
                logger.error('CheckSyncStatusThread: %s'%err)
            finally:
                time.sleep(2)
            logger.debug('finished CheckSyncStatusThread')

    def stop(self):
        self.stopped = True

class MainWind(WebViewDialog):
    changed_service_status = Signal(str, str)

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

        Subprocess(MGMT_CLI_RUNCMD + ' restart', env=ENV)

        self.check_sync_status_thr = CheckSyncStatusThread(self)
        self.check_sync_status_thr.start()

        if sys.platform != 'darwin':
            self.systray.activated.connect(self.on_icon_activated)

        self.__show_splash_screen()

    def __show_splash_screen(self):
        movie = QMovie(LOADING_IMG)
        ss = QSplashScreen()
        ss.showMessage('Starting iDepositBox service...', Qt.AlignCenter)
        ss.show()
        frames_count = movie.frameCount()
        if frames_count < 1:
            #no loaded animation
            ss.finish(self)
            return

        t0 = datetime.now()
        max_dt = timedelta(0, MAX_CONSOLE_WAIT_TIME)
        while True:
            if not self.__first_event:
                ss.finish(self)
                break
            for i in xrange(frames_count):
                pix = movie.currentPixmap()
                ss.setPixmap(pix)
                ss.repaint()
                qApp.processEvents()
                delay = movie.nextFrameDelay()
                time.sleep(delay/1000.)
                movie.jumpToNextFrame()
            dt = datetime.now() - t0
            if dt > max_dt:
                #mgmt console does not started!
                self.show_error('Management console does not started! See log file for details...')
                qApp.exit()

    def on_changed_service_status(self, status, data=None):
        if self.__first_event:
            self.__first_event = False
            if self.systray.isSystemTrayAvailable():
                self.systray.show()
                time.sleep(1)
                self.systray.show_information('Information', 'iDepostiBox client was started successfully')
            else:
                self.onManage()

        if self.systray.isVisible():
            self.systray.on_changed_service_status(status, data)

    def on_icon_activated(self, reason):
        if reason in (self.systray.ActivationReason.Trigger, self.systray.ActivationReason.DoubleClick):
            self.systray.contextMenu().popup(QCursor.pos())

    def onManage(self):
        self.load('http://127.0.0.1:%s/'%DAEMON_PORT)
        self.setVisible(True)
        self.show()
        self.activateWindow()

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
            proc = Subprocess(MGMT_CLI_RUNCMD+' stop', env=ENV)
            cout, cerr = proc.communicate()
            print (cout)
            if proc.returncode:
                self.show_error('Management console does not stopped!\nDetails: %s'%cerr)

            self.check_sync_status_thr.stop()
            self.check_sync_status_thr.wait()
        except Exception, err:
            self.show_error('Unexpected error: %s'%err)
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
        proc = Subprocess(MGMT_CLI_RUNCMD+' status', env=ENV)
        cout, cerr = proc.communicate()
        print (cout)
        if proc.returncode:
            return False
        return True

def main():
    try:
        app = QApplication(sys.argv)
        if MainWind.isMgmtServerStarted():
            if not MainWind.show_question('WARNING', 'Management console is already started! Do you really want start application?'):
                sys.exit(1)
        app.setQuitOnLastWindowClosed(False)

        mw = MainWind()
    except Exception, err:
        logger.error('UI error: %s'%err)
        sys.exit(1)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
