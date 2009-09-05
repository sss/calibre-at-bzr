#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

class CraigsList(BasicNewsRecipe):
     title          = u'craigslist - Best Of'
     oldest_article = 365
     max_articles_per_feed = 100
     language = 'en'

     __author__ = 'kiodane'

     feeds          = [(u'Best of craigslist',
 u'http://www.craigslist.org/about/best/all/index.rss'), ]

