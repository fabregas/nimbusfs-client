# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'id_client/gui/forms/files_inprogress_form.ui'
#
# Created: Sun Dec  9 14:48:11 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_FilesInprogressDialog(object):
    def setupUi(self, FilesInprogressDialog):
        FilesInprogressDialog.setObjectName("FilesInprogressDialog")
        FilesInprogressDialog.resize(700, 250)
        self.verticalLayout = QtGui.QVBoxLayout(FilesInprogressDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tableWidget = QtGui.QTableWidget(FilesInprogressDialog)
        self.tableWidget.setColumnCount(2)
        self.tableWidget.setObjectName("tableWidget")
        self.tableWidget.setColumnCount(2)
        self.tableWidget.setRowCount(0)
        item = QtGui.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(0, item)
        item = QtGui.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(1, item)
        self.tableWidget.horizontalHeader().setCascadingSectionResizes(False)
        self.verticalLayout.addWidget(self.tableWidget)

        self.retranslateUi(FilesInprogressDialog)
        QtCore.QMetaObject.connectSlotsByName(FilesInprogressDialog)

    def retranslateUi(self, FilesInprogressDialog):
        FilesInprogressDialog.setWindowTitle(QtGui.QApplication.translate("FilesInprogressDialog", "Files in progress...", None, QtGui.QApplication.UnicodeUTF8))
        self.tableWidget.horizontalHeaderItem(0).setText(QtGui.QApplication.translate("FilesInprogressDialog", "Operation", None, QtGui.QApplication.UnicodeUTF8))
        self.tableWidget.horizontalHeaderItem(1).setText(QtGui.QApplication.translate("FilesInprogressDialog", "File name", None, QtGui.QApplication.UnicodeUTF8))

