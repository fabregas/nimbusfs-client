# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'id_client/gui/forms/settings_base_form.ui'
#
# Created: Mon Dec 10 23:30:04 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_SettingsDialog(object):
    def setupUi(self, SettingsDialog):
        SettingsDialog.setObjectName("SettingsDialog")
        SettingsDialog.resize(647, 491)
        self.verticalLayout = QtGui.QVBoxLayout(SettingsDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.securityProviderBox = QtGui.QGroupBox(SettingsDialog)
        self.securityProviderBox.setObjectName("securityProviderBox")
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.securityProviderBox)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.groupBox = QtGui.QGroupBox(self.securityProviderBox)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(200)
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setMinimumSize(QtCore.QSize(0, 100))
        self.groupBox.setTitle("")
        self.groupBox.setObjectName("groupBox")
        self.rbTokenKS = QtGui.QRadioButton(self.groupBox)
        self.rbTokenKS.setGeometry(QtCore.QRect(30, 20, 311, 20))
        self.rbTokenKS.setObjectName("rbTokenKS")
        self.rbLocalKS = QtGui.QRadioButton(self.groupBox)
        self.rbLocalKS.setGeometry(QtCore.QRect(30, 60, 201, 20))
        self.rbLocalKS.setObjectName("rbLocalKS")
        self.verticalLayout_2.addWidget(self.groupBox)
        self.label = QtGui.QLabel(self.securityProviderBox)
        self.label.setObjectName("label")
        self.verticalLayout_2.addWidget(self.label)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.lineEdit = QtGui.QLineEdit(self.securityProviderBox)
        self.lineEdit.setReadOnly(True)
        self.lineEdit.setObjectName("lineEdit")
        self.horizontalLayout.addWidget(self.lineEdit)
        self.selectFileButton = QtGui.QPushButton(self.securityProviderBox)
        self.selectFileButton.setObjectName("selectFileButton")
        self.horizontalLayout.addWidget(self.selectFileButton)
        self.verticalLayout_2.addLayout(self.horizontalLayout)
        self.verticalLayout.addWidget(self.securityProviderBox)
        self.nimbusFSBox = QtGui.QGroupBox(SettingsDialog)
        self.nimbusFSBox.setObjectName("nimbusFSBox")
        self.verticalLayout_3 = QtGui.QVBoxLayout(self.nimbusFSBox)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.horizontalLayout_6 = QtGui.QHBoxLayout()
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.label_4 = QtGui.QLabel(self.nimbusFSBox)
        self.label_4.setObjectName("label_4")
        self.horizontalLayout_6.addWidget(self.label_4)
        self.serviceURL = QtGui.QLineEdit(self.nimbusFSBox)
        self.serviceURL.setObjectName("serviceURL")
        self.horizontalLayout_6.addWidget(self.serviceURL)
        self.verticalLayout_3.addLayout(self.horizontalLayout_6)
        self.horizontalLayout_5 = QtGui.QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.label_2 = QtGui.QLabel(self.nimbusFSBox)
        self.label_2.setMinimumSize(QtCore.QSize(180, 0))
        self.label_2.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.label_2.setObjectName("label_2")
        self.horizontalLayout_5.addWidget(self.label_2)
        self.downloadCount = QtGui.QSpinBox(self.nimbusFSBox)
        self.downloadCount.setMinimum(1)
        self.downloadCount.setMaximum(10)
        self.downloadCount.setObjectName("downloadCount")
        self.horizontalLayout_5.addWidget(self.downloadCount)
        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_5.addItem(spacerItem)
        self.verticalLayout_3.addLayout(self.horizontalLayout_5)
        self.horizontalLayout_4 = QtGui.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.label_3 = QtGui.QLabel(self.nimbusFSBox)
        self.label_3.setMinimumSize(QtCore.QSize(180, 0))
        self.label_3.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.label_3.setObjectName("label_3")
        self.horizontalLayout_4.addWidget(self.label_3)
        self.uploadCount = QtGui.QSpinBox(self.nimbusFSBox)
        self.uploadCount.setMinimum(1)
        self.uploadCount.setMaximum(10)
        self.uploadCount.setObjectName("uploadCount")
        self.horizontalLayout_4.addWidget(self.uploadCount)
        spacerItem1 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_4.addItem(spacerItem1)
        self.verticalLayout_3.addLayout(self.horizontalLayout_4)
        self.verticalLayout.addWidget(self.nimbusFSBox)
        self.webdavBox = QtGui.QGroupBox(SettingsDialog)
        self.webdavBox.setObjectName("webdavBox")
        self.verticalLayout_4 = QtGui.QVBoxLayout(self.webdavBox)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.horizontalLayout_7 = QtGui.QHBoxLayout()
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.label_5 = QtGui.QLabel(self.webdavBox)
        self.label_5.setMinimumSize(QtCore.QSize(100, 0))
        self.label_5.setObjectName("label_5")
        self.horizontalLayout_7.addWidget(self.label_5)
        self.webdavBindAddr = QtGui.QLineEdit(self.webdavBox)
        self.webdavBindAddr.setObjectName("webdavBindAddr")
        self.horizontalLayout_7.addWidget(self.webdavBindAddr)
        self.verticalLayout_4.addLayout(self.horizontalLayout_7)
        self.horizontalLayout_8 = QtGui.QHBoxLayout()
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.label_6 = QtGui.QLabel(self.webdavBox)
        self.label_6.setMinimumSize(QtCore.QSize(100, 0))
        self.label_6.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.label_6.setObjectName("label_6")
        self.horizontalLayout_8.addWidget(self.label_6)
        self.webdavBindPort = QtGui.QSpinBox(self.webdavBox)
        self.webdavBindPort.setMinimumSize(QtCore.QSize(100, 0))
        self.webdavBindPort.setMinimum(1)
        self.webdavBindPort.setMaximum(65535)
        self.webdavBindPort.setObjectName("webdavBindPort")
        self.horizontalLayout_8.addWidget(self.webdavBindPort)
        spacerItem2 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_8.addItem(spacerItem2)
        self.verticalLayout_4.addLayout(self.horizontalLayout_8)
        self.verticalLayout.addWidget(self.webdavBox)
        self.widget = QtGui.QWidget(SettingsDialog)
        self.widget.setObjectName("widget")
        self.horizontalLayout_3 = QtGui.QHBoxLayout(self.widget)
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem3 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem3)
        self.applyButton = QtGui.QPushButton(self.widget)
        self.applyButton.setMinimumSize(QtCore.QSize(150, 0))
        self.applyButton.setObjectName("applyButton")
        self.horizontalLayout_2.addWidget(self.applyButton)
        self.cancelButton = QtGui.QPushButton(self.widget)
        self.cancelButton.setObjectName("cancelButton")
        self.horizontalLayout_2.addWidget(self.cancelButton)
        self.horizontalLayout_3.addLayout(self.horizontalLayout_2)
        self.verticalLayout.addWidget(self.widget)

        self.retranslateUi(SettingsDialog)
        QtCore.QMetaObject.connectSlotsByName(SettingsDialog)

    def retranslateUi(self, SettingsDialog):
        SettingsDialog.setWindowTitle(QtGui.QApplication.translate("SettingsDialog", "Settings", None, QtGui.QApplication.UnicodeUTF8))
        self.securityProviderBox.setTitle(QtGui.QApplication.translate("SettingsDialog", "Security provider", None, QtGui.QApplication.UnicodeUTF8))
        self.rbTokenKS.setText(QtGui.QApplication.translate("SettingsDialog", "USB Token key storage", None, QtGui.QApplication.UnicodeUTF8))
        self.rbLocalKS.setText(QtGui.QApplication.translate("SettingsDialog", "Local key storage", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("SettingsDialog", "Local key storage path", None, QtGui.QApplication.UnicodeUTF8))
        self.selectFileButton.setText(QtGui.QApplication.translate("SettingsDialog", "select ...", None, QtGui.QApplication.UnicodeUTF8))
        self.nimbusFSBox.setTitle(QtGui.QApplication.translate("SettingsDialog", "Nimbus FS", None, QtGui.QApplication.UnicodeUTF8))
        self.label_4.setText(QtGui.QApplication.translate("SettingsDialog", "Service URL", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("SettingsDialog", "Parallel downloads count", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("SettingsDialog", "Parallel upload count", None, QtGui.QApplication.UnicodeUTF8))
        self.webdavBox.setTitle(QtGui.QApplication.translate("SettingsDialog", "WebDav server", None, QtGui.QApplication.UnicodeUTF8))
        self.label_5.setText(QtGui.QApplication.translate("SettingsDialog", "Bind address", None, QtGui.QApplication.UnicodeUTF8))
        self.label_6.setText(QtGui.QApplication.translate("SettingsDialog", "Bind port", None, QtGui.QApplication.UnicodeUTF8))
        self.applyButton.setText(QtGui.QApplication.translate("SettingsDialog", "Apply", None, QtGui.QApplication.UnicodeUTF8))
        self.cancelButton.setText(QtGui.QApplication.translate("SettingsDialog", "Cancel", None, QtGui.QApplication.UnicodeUTF8))

