#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.gui.settings_dialog
@author Konstantin Andrusenko
@date December 10, 2012
"""

import os
from PySide.QtCore import Qt
from PySide.QtGui import QDialog, QMessageBox, QFileDialog

from forms.settings_base_form import Ui_SettingsDialog

from id_client.constants import SPT_TOKEN_BASED, SPT_FILE_BASED
from id_client.config import Config

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)

        self.ui = Ui_SettingsDialog()
        self.ui.setupUi(self)

        self.ui.applyButton.clicked.connect(self.on_apply)
        self.ui.cancelButton.clicked.connect(self.on_cancel)

        self.ui.selectFileButton.clicked.connect(self.on_select_file_button)
        self.ui.selectFileButton.setEnabled(False)
        self.ui.rbTokenKS.toggled.connect(self.on_token_ks_toggled)
        self.ui.rbLocalKS.toggled.connect(self.on_file_ks_toggled)

        self.ui.lineEdit.textChanged.connect(self.on_config_change)
        self.ui.webdavBindAddr.textChanged.connect(self.on_config_change)
        self.ui.serviceURL.textChanged.connect(self.on_config_change)
        self.ui.uploadCount.valueChanged.connect(self.on_config_change)
        self.ui.downloadCount.valueChanged.connect(self.on_config_change)
        self.ui.webdavBindPort.valueChanged.connect(self.on_config_change)

        self.config = Config()
        self.set_form_data()

        self.no_changed = True
        self.ui.applyButton.setText('Ok')
        self.ui.cancelButton.setFocus()

    def on_config_change(self, dummy=None):
        self.no_changed = False
        self.ui.applyButton.setText('Apply')

    def set_form_data(self):
        if self.config.security_provider_type == SPT_FILE_BASED:
            self.ui.lineEdit.setText(self.config.key_storage_path)
            self.ui.rbLocalKS.setChecked(True)
        else:
            self.ui.rbTokenKS.setChecked(True)


        self.ui.serviceURL.setText(self.config.fabnet_hostname)
        self.ui.downloadCount.setValue(int(self.config.parallel_get_count))
        self.ui.uploadCount.setValue(int(self.config.parallel_put_count))
        self.ui.webdavBindAddr.setText(self.config.webdav_bind_host)
        self.ui.webdavBindPort.setValue(int(self.config.webdav_bind_port))


    def apply(self):
        if self.ui.rbTokenKS.isChecked():
            self.config.security_provider_type = SPT_TOKEN_BASED
            self.config.key_storage_path = 'usb'
        elif self.ui.rbLocalKS.isChecked():
            self.config.security_provider_type = SPT_FILE_BASED
            self.config.key_storage_path = self.ui.lineEdit.text()

        self.config.fabnet_hostname = self.ui.serviceURL.text()
        self.config.parallel_get_count = self.ui.downloadCount.value()
        self.config.parallel_put_count = self.ui.uploadCount.value()
        self.config.webdav_bind_host = self.ui.webdavBindAddr.text()
        self.config.webdav_bind_port = self.ui.webdavBindPort.value()

        if not self.config.key_storage_path:
            raise Exception('Please, specify key storage path!')
        if not self.config.fabnet_hostname:
            raise Exception('Please, specify Nimbus file system service URL!')
        if not self.config.webdav_bind_host:
            raise Exception('Please, specify WebDav server bind hostname')

    def on_select_file_button(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open file', os.getenv('HOME', '/home'))
        self.ui.lineEdit.setText(fname)

    def on_token_ks_toggled(self, checked):
        self.on_config_change()
        if checked:
            self.ui.selectFileButton.setEnabled(False)

    def on_file_ks_toggled(self, checked):
        self.on_config_change()
        if checked:
            self.ui.selectFileButton.setEnabled(True)


    def on_cancel(self):
        self.reject()

    def on_apply(self):
        if self.no_changed:
            return self.accept()

        try:
            self.apply()
        except Exception, err:
            QMessageBox.critical(None, 'Error', unicode(err))
            return

        self.config.save()
        self.no_changed = True
        self.ui.applyButton.setText('Ok')
