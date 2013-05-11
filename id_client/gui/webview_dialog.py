#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package id_client.gui.webview_dialog
@author Konstantin Andrusenko
@date May 8, 2013
"""

from PySide.QtCore import Qt, QUrl
from PySide.QtGui import QDialog

from forms.web_view_form import Ui_WebView

class WebViewDialog(QDialog):
    def __init__(self, parent=None):
        super(WebViewDialog, self).__init__(parent)

        self.ui = Ui_WebView()
        self.ui.setupUi(self)

    def load(self, url):
        self.ui.webView.load(QUrl(url))
        self.ui.webView.loadFinished.connect(self.on_page_loaded)

    def on_page_loaded(self, is_loaded):
        if not is_loaded:
            self.ui.webView.setHtml('''
                <html>
                <body>
                    <div style="position:relative; width:100%; height:200px;"></div>
                    <div>
                        <h1 style="color: red; text-align:center;">ERROR</h1>
                        <h2 style="text-align:center;">iDepostitBox management server does not found!</h2>
                    </div>
                <body>
                </html>''')
