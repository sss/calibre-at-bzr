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

class EbookpointStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        pid = '5557Y'

        url = 'http://ebookpoint.pl/view/' + pid
        detail_url = None

        if detail_item:
            book_id = re.sub(r'http://ebookpoint.pl/ksiazki', '', detail_item)
            if book_id:
                detail_url = url + book_id

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://ebookpoint.pl/search.scgi?szukaj=' + urllib.quote(query) + '&serwisyall=0&x=0&y=0'
        ebook_string = 'eBook.'

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="book-list"]/ul[2]/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[@class="cover"]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//a[@class="cover"]/img/@src'))
                title = ''.join(data.xpath('.//h3/a/text()'))
                title = re.sub(ebook_string, '', title)
                author = ''.join(data.xpath('.//p[@class="author"]/text()'))
                price = ''.join(data.xpath('.//p[@class="price"]/ins/text()'))

                with closing(br.open(id.strip(), timeout=timeout)) as nf:
                    idata = html.fromstring(nf.read())
                    formats = ', '.join(idata.xpath('//div[@class="col-left"]/h2[contains(., "' + ebook_string + '")]/@class'))

                counter -= 1

                s = SearchResult()
                s.cover_url = 'http://ebookpoint.pl' + cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = re.sub(r'\.',',',price)
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = formats.upper().strip()

                yield s
