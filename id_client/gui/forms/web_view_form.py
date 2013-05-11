# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'id_client/gui/forms/web_view_form.ui'
#
# Created: Wed May  8 22:54:55 2013
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_WebView(object):
    def setupUi(self, WebView):
        WebView.setObjectName("WebView")
        WebView.resize(800, 600)
        WebView.setMinimumSize(QtCore.QSize(800, 600))
        self.horizontalLayout = QtGui.QHBoxLayout(WebView)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.webView = QtWebKit.QWebView(WebView)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.webView.sizePolicy().hasHeightForWidth())
        self.webView.setSizePolicy(sizePolicy)
        self.webView.setUrl(QtCore.QUrl("about:blank"))
        self.webView.setObjectName("webView")
        self.horizontalLayout.addWidget(self.webView)

        self.retranslateUi(WebView)
        QtCore.QMetaObject.connectSlotsByName(WebView)

    def retranslateUi(self, WebView):
        WebView.setWindowTitle(QtGui.QApplication.translate("WebView", "iDepositBox management console", None, QtGui.QApplication.UnicodeUTF8))

from PySide import QtWebKit
