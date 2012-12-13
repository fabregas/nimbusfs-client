#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.gui.files_inprogress_dialog
@author Konstantin Andrusenko
@date December 09, 2012
"""

from PySide.QtCore import QTimer
from PySide.QtGui import QDialog, QFileDialog,  QTableWidgetItem

from forms.files_inprogress_form import Ui_FilesInprogressDialog


class FilesInprogressDialog(QDialog):
    def __init__(self, nibbler, parent=None):
        super(FilesInprogressDialog, self).__init__(parent)

        self.__cache = []
        self.nibbler = nibbler
        self.ui = Ui_FilesInprogressDialog()
        self.ui.setupUi(self)

        self.timer = QTimer()
        self.timer.timeout.connect(self.on_update_table)
        self.on_update_table()

    def resizeEvent(self, event):
        w = self.ui.tableWidget.size().width()

        self.ui.tableWidget.setColumnWidth(0, int(w*0.2)-2)
        self.ui.tableWidget.setColumnWidth(1, int(w*0.8)-2)

    def showEvent(self, event):
        self.timer.start(1000)

    def closeEvent(self, event):
        self.timer.stop()

    def on_update_table(self):
        ops = self.nibbler.inprocess_operations()
        operations = []
        for op in ops:
            operations.append((op.op_type, op.file_name))

        if self.__cache == operations:
            return

        self.__cache = operations
        self.show_inprogress_operations()

    def show_inprogress_operations(self):
        self.ui.tableWidget.setRowCount(len(self.__cache))
        for i, (op_type, file_name) in enumerate(self.__cache):
            self.ui.tableWidget.setItem(i, 0,   QTableWidgetItem(op_type))
            self.ui.tableWidget.setItem(i, 1,   QTableWidgetItem(file_name))

