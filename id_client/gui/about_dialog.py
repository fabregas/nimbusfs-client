#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.gui.about_dialog
@author Konstantin Andrusenko
@date December 15, 2012
"""

from PySide.QtCore import QSize, Qt
from PySide.QtGui import QDialog, QPixmap, QPalette

from forms.about_form import Ui_AboutDialog


class AboutDialog(QDialog):
    def __init__(self, icon_path, bg_img_path, version, parent=None):
        super(AboutDialog, self).__init__(parent, Qt.WindowStaysOnTopHint|Qt.Window)

        self.ui = Ui_AboutDialog()
        self.ui.setupUi(self)

        #icon = QPixmap(icon_path)
        #icon = icon.scaled(QSize(100, 100))
        #self.ui.iconLabel.setPixmap(icon)
        self.ui.versionLabel.setText('Version: %s'%version)

        palette = QPalette()
        palette.setBrush(QPalette.Window, QPixmap(bg_img_path).scaled(self.size(), Qt.KeepAspectRatio))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
