# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
import urllib

from PyQt4.Qt import QDialog, QUrl

from calibre.gui2.store.web_store_dialog_ui import Ui_Dialog

class WebStoreDialog(QDialog, Ui_Dialog):

    def __init__(self, gui, base_url, parent=None, detail_item=None):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)
        
        self.gui = gui
        self.base_url = base_url
        
        self.view.set_gui(self.gui)
        self.view.loadStarted.connect(self.load_started)
        self.view.loadProgress.connect(self.load_progress)
        self.view.loadFinished.connect(self.load_finished)
        self.home.clicked.connect(self.go_home)
        self.reload.clicked.connect(self.view.reload)
        self.back.clicked.connect(self.view.back)
        
        self.go_home(detail_item=detail_item)

    def load_started(self):
        self.progress.setValue(0)
    
    def load_progress(self, val):
        self.progress.setValue(val)
        
    def load_finished(self, ok=True):
        self.progress.setValue(100)
    
    def go_home(self, checked=False, detail_item=None):
        url = self.base_url
        if detail_item:
            url, q, ref = url.partition('?')
            url = url + '/' + urllib.quote(detail_item) + q + ref
            
        # Reduce redundant /'s because some stores
        # (Feedbooks) and server frameworks (cherrypy)
        # choke on them. 
        url = re.sub(r'(?<!http:)/{2,}', '/', url)
        self.view.load(QUrl(url))
