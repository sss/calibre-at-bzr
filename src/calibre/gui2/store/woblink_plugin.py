# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
import urllib
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class WoblinkStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):

        url = 'http://woblink.com/publication'
        detail_url = None

        if detail_item:
            detail_url = 'http://woblink.com' + detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://woblink.com/publication?query=' + urllib.quote_plus(query.encode('utf-8'))

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="book-item"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//td[@class="w10 va-t"]/a[1]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//td[@class="w10 va-t"]/a[1]/img/@src'))
                title = ''.join(data.xpath('.//h3[@class="title"]/a[1]/text()'))
                author = ', '.join(data.xpath('.//p[@class="author"]/a/text()'))
                price = ''.join(data.xpath('.//div[@class="prices"]/p[1]/span/text()'))
                price = re.sub('PLN', ' zł', price)
                price = re.sub('\.', ',', price)

                counter -= 1

                s = SearchResult()
                s.cover_url = 'http://woblink.com' + cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_LOCKED
                s.formats = 'EPUB'

                yield s
