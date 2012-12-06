#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.gui.security_provider_conf_dialog
@author Konstantin Andrusenko
@date December 06, 2012
"""

import os
from PySide.QtGui import QDialog, QFileDialog

from forms.security_provider_conf_form import Ui_SecutiryProviderConfigDialog
from id_client.constants import SPT_TOKEN_BASED, SPT_FILE_BASED

class SecurityProviderConfigDialog(QDialog):
    def __init__(self, parent=None):
        super(SecurityProviderConfigDialog, self).__init__(parent)

        self.ui = Ui_SecutiryProviderConfigDialog()
        self.ui.setupUi(self)
        self.ui.applyButton.clicked.connect(self.on_apply)
        self.ui.selectFileButton.clicked.connect(self.on_select_file_button)
        self.ui.applyButton.setEnabled(False)
        self.ui.selectFileButton.setEnabled(False)
        self.ui.rbTokenKS.toggled.connect(self.on_token_ks_toggled)
        self.ui.rbLocalKS.toggled.connect(self.on_file_ks_toggled)

        self.provider_type = None
        self.key_storage_path = ''

    def on_apply(self):
        if self.ui.rbTokenKS.isChecked():
            self.provider_type = SPT_TOKEN_BASED
            self.key_storage_path = 'usb'
        elif self.ui.rbLocalKS.isChecked():
            self.provider_type = SPT_FILE_BASED
            self.key_storage_path = self.ui.lineEdit.text()
        else:
            self.reject()
            return

        self.accept()


    def on_select_file_button(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open file', os.getenv('HOME', '/home'))
        self.ui.lineEdit.setText(fname)
        self.ui.applyButton.setEnabled(True)

    def on_token_ks_toggled(self, checked):
        self.ui.applyButton.setEnabled(True)
        if checked:
            self.ui.selectFileButton.setEnabled(False)

    def on_file_ks_toggled(self, checked):
        if self.ui.lineEdit.text():
            self.ui.applyButton.setEnabled(True)
        else:
            self.ui.applyButton.setEnabled(False)

        if checked:
            self.ui.selectFileButton.setEnabled(True)

