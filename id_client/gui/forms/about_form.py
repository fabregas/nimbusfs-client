# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'id_client/gui/forms/about_form.ui'
#
# Created: Sat Dec 15 02:00:11 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_AboutDialog(object):
    def setupUi(self, AboutDialog):
        AboutDialog.setObjectName("AboutDialog")
        AboutDialog.resize(400, 300)
        AboutDialog.setMinimumSize(QtCore.QSize(400, 300))
        AboutDialog.setMaximumSize(QtCore.QSize(400, 300))
        self.verticalLayout = QtGui.QVBoxLayout(AboutDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.iconLabel = QtGui.QLabel(AboutDialog)
        self.iconLabel.setMinimumSize(QtCore.QSize(0, 100))
        self.iconLabel.setText("")
        self.iconLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.iconLabel.setObjectName("iconLabel")
        self.verticalLayout.addWidget(self.iconLabel)
        self.label = QtGui.QLabel(AboutDialog)
        font = QtGui.QFont()
        font.setPointSize(20)
        font.setWeight(75)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.label_2 = QtGui.QLabel(AboutDialog)
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_2.setObjectName("label_2")
        self.verticalLayout.addWidget(self.label_2)
        self.versionLabel = QtGui.QLabel(AboutDialog)
        self.versionLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.versionLabel.setObjectName("versionLabel")
        self.verticalLayout.addWidget(self.versionLabel)
        self.label_3 = QtGui.QLabel(AboutDialog)
        self.label_3.setAlignment(QtCore.Qt.AlignCenter)
        self.label_3.setObjectName("label_3")
        self.verticalLayout.addWidget(self.label_3)
        self.label_4 = QtGui.QLabel(AboutDialog)
        self.label_4.setAlignment(QtCore.Qt.AlignCenter)
        self.label_4.setObjectName("label_4")
        self.verticalLayout.addWidget(self.label_4)

        self.retranslateUi(AboutDialog)
        QtCore.QMetaObject.connectSlotsByName(AboutDialog)

    def retranslateUi(self, AboutDialog):
        AboutDialog.setWindowTitle(QtGui.QApplication.translate("AboutDialog", "About", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("AboutDialog", "iDepositBox", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("AboutDialog", "Client software for idepositbox.com service", None, QtGui.QApplication.UnicodeUTF8))
        self.versionLabel.setText(QtGui.QApplication.translate("AboutDialog", "Version: XXX", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("AboutDialog", "Copyright (c) 2012 iDepositBox software", None, QtGui.QApplication.UnicodeUTF8))
        self.label_4.setText(QtGui.QApplication.translate("AboutDialog", "All rights reserved", None, QtGui.QApplication.UnicodeUTF8))

