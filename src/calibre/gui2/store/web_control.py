# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import urllib2
from cookielib import Cookie, CookieJar
from urlparse import urlparse

from PyQt4.Qt import QWebView, QWebPage, QNetworkCookieJar, QNetworkRequest, QString, \
    QFileDialog, QNetworkProxy

from calibre import USER_AGENT, browser, get_proxies, get_download_filename
from calibre.ebooks import BOOK_EXTENSIONS

class NPWebView(QWebView):

    def __init__(self, *args):
        QWebView.__init__(self, *args)
        self.gui = None
        self.tags = ''

        self.setPage(NPWebPage())
        self.page().networkAccessManager().setCookieJar(QNetworkCookieJar())

        http_proxy = get_proxies().get('http', None)
        if http_proxy:
            proxy_parts = urlparse(http_proxy)
            proxy = QNetworkProxy()
            proxy.setType(QNetworkProxy.HttpProxy)
            proxy.setUser(proxy_parts.username)
            proxy.setPassword(proxy_parts.password)
            proxy.setHostName(proxy_parts.hostname)
            proxy.setPort(proxy_parts.port)
            self.page().networkAccessManager().setProxy(proxy)            
        
        self.page().setForwardUnsupportedContent(True)
        self.page().unsupportedContent.connect(self.start_download)
        self.page().downloadRequested.connect(self.start_download)
        self.page().networkAccessManager().sslErrors.connect(self.ignore_ssl_errors)
    
    def createWindow(self, type):
        if type == QWebPage.WebBrowserWindow:
            return self
        else:
            return None

    def set_gui(self, gui):
        self.gui = gui
        
    def set_tags(self, tags):
        self.tags = tags
        
    def start_download(self, request):
        if not self.gui:
            return
        
        url = unicode(request.url().toString())
        cj = self.get_cookies()
        
        filename = get_download_filename(url, cj)
        ext = os.path.splitext(filename)[1][1:].lower()
        if ext not in BOOK_EXTENSIONS:
            home = os.path.expanduser('~')
            name = QFileDialog.getSaveFileName(self,
                _('File is not a supported ebook type. Save to disk?'),
                os.path.join(home, filename),
                '*.*')
            if name:
                self.gui.download_from_store(url, cj, name, name, False)
        else:
            self.gui.download_from_store(url, cj, filename, tags=self.tags)

    def ignore_ssl_errors(self, reply, errors):
        reply.ignoreSslErrors(errors)
    
    def get_cookies(self):
        cj = CookieJar()
        
        # Translate Qt cookies to cookielib cookies for use by mechanize.
        for c in self.page().networkAccessManager().cookieJar().allCookies():
            version = 0
            name = unicode(QString(c.name()))
            value = unicode(QString(c.value()))
            port = None
            port_specified = False
            domain = unicode(c.domain())
            if domain:
                domain_specified = True
                if domain.startswith('.'):
                    domain_initial_dot = True
                else:
                    domain_initial_dot = False
            else:
                domain = None
                domain_specified = False
            path = unicode(c.path())
            if path:
                path_specified = True
            else:
                path = None
                path_specified = False
            secure = c.isSecure()
            expires = c.expirationDate().toMSecsSinceEpoch() / 1000
            discard = c.isSessionCookie()
            comment = None
            comment_url = None
            rest = None
            
            cookie = Cookie(version, name, value,
                 port, port_specified,
                 domain, domain_specified, domain_initial_dot,
                 path, path_specified,
                 secure,
                 expires,
                 discard,
                 comment,
                 comment_url,
                 rest) 
            
            cj.set_cookie(cookie)
            
        return cj


class NPWebPage(QWebPage):
    
    def userAgentForUrl(self, url):
        return USER_AGENT
