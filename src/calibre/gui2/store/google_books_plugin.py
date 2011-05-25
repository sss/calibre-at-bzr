# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

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

class GoogleBooksStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://books.google.com/'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.google.com/search?tbm=bks&q=' + urllib.quote_plus(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ol[@id="rso"]/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//h3/a/@href'))
                if not id:
                    continue

                title = ''.join(data.xpath('.//h3/a//text()'))
                authors = data.xpath('.//span[@class="gl"]//a//text()')
                if authors[-1].strip().lower() in ('preview', 'read'):
                    authors = authors[:-1]
                else:
                    continue
                author = ', '.join(authors)

                counter -= 1
                
                s = SearchResult()
                s.title = title.strip()
                s.author = author.strip()
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNKNOWN
                
                yield s
                
    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            doc = html.fromstring(nf.read())
            
            search_result.cover_url = ''.join(doc.xpath('//div[@class="sidebarcover"]//img/@src'))
            
            # Try to get the set price.
            price = ''.join(doc.xpath('//div[@class="buy-price-container"]/span[contains(@class, "buy-price")]/text()'))
            # Try to get the price inside of a buy button.
            if not price.strip():
                price = ''.join(doc.xpath('//div[@class="buy-container"]/a/text()'))
                price = price.split('-')[-1]
            # No price set for this book.
            if not price.strip():
                price = '$0.00'
            search_result.price = price.strip()
            
            search_result.formats = ', '.join(doc.xpath('//div[contains(@class, "download-panel-div")]//a/text()')).upper()
            if not search_result.formats:
                search_result.formats = _('Unknown')
            
        return True

