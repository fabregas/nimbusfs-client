# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'id_client/gui/forms/security_provider_conf_form.ui'
#
# Created: Sun Dec  9 14:48:12 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_SecutiryProviderConfigDialog(object):
    def setupUi(self, SecutiryProviderConfigDialog):
        SecutiryProviderConfigDialog.setObjectName("SecutiryProviderConfigDialog")
        SecutiryProviderConfigDialog.setWindowModality(QtCore.Qt.WindowModal)
        SecutiryProviderConfigDialog.resize(410, 270)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(SecutiryProviderConfigDialog.sizePolicy().hasHeightForWidth())
        SecutiryProviderConfigDialog.setSizePolicy(sizePolicy)
        SecutiryProviderConfigDialog.setMinimumSize(QtCore.QSize(410, 270))
        SecutiryProviderConfigDialog.setMaximumSize(QtCore.QSize(410, 270))
        self.groupBox = QtGui.QGroupBox(SecutiryProviderConfigDialog)
        self.groupBox.setGeometry(QtCore.QRect(20, 30, 371, 111))
        self.groupBox.setObjectName("groupBox")
        self.rbTokenKS = QtGui.QRadioButton(self.groupBox)
        self.rbTokenKS.setGeometry(QtCore.QRect(30, 30, 311, 20))
        self.rbTokenKS.setObjectName("rbTokenKS")
        self.rbLocalKS = QtGui.QRadioButton(self.groupBox)
        self.rbLocalKS.setGeometry(QtCore.QRect(30, 70, 201, 20))
        self.rbLocalKS.setObjectName("rbLocalKS")
        self.applyButton = QtGui.QPushButton(SecutiryProviderConfigDialog)
        self.applyButton.setGeometry(QtCore.QRect(150, 230, 111, 32))
        self.applyButton.setObjectName("applyButton")
        self.lineEdit = QtGui.QLineEdit(SecutiryProviderConfigDialog)
        self.lineEdit.setGeometry(QtCore.QRect(20, 185, 271, 22))
        self.lineEdit.setReadOnly(True)
        self.lineEdit.setObjectName("lineEdit")
        self.selectFileButton = QtGui.QPushButton(SecutiryProviderConfigDialog)
        self.selectFileButton.setGeometry(QtCore.QRect(290, 180, 101, 32))
        self.selectFileButton.setObjectName("selectFileButton")
        self.label = QtGui.QLabel(SecutiryProviderConfigDialog)
        self.label.setGeometry(QtCore.QRect(20, 165, 201, 16))
        self.label.setObjectName("label")

        self.retranslateUi(SecutiryProviderConfigDialog)
        QtCore.QMetaObject.connectSlotsByName(SecutiryProviderConfigDialog)

    def retranslateUi(self, SecutiryProviderConfigDialog):
        SecutiryProviderConfigDialog.setWindowTitle(QtGui.QApplication.translate("SecutiryProviderConfigDialog", "Security provider configuration", None, QtGui.QApplication.UnicodeUTF8))
        self.groupBox.setTitle(QtGui.QApplication.translate("SecutiryProviderConfigDialog", "Key storage type", None, QtGui.QApplication.UnicodeUTF8))
        self.rbTokenKS.setText(QtGui.QApplication.translate("SecutiryProviderConfigDialog", "USB Token key storage", None, QtGui.QApplication.UnicodeUTF8))
        self.rbLocalKS.setText(QtGui.QApplication.translate("SecutiryProviderConfigDialog", "Local key storage", None, QtGui.QApplication.UnicodeUTF8))
        self.applyButton.setText(QtGui.QApplication.translate("SecutiryProviderConfigDialog", "Apply", None, QtGui.QApplication.UnicodeUTF8))
        self.selectFileButton.setText(QtGui.QApplication.translate("SecutiryProviderConfigDialog", "select ...", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("SecutiryProviderConfigDialog", "Local key storage path", None, QtGui.QApplication.UnicodeUTF8))

