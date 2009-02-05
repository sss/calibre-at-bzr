#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
market-ticker.denninger.net
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Themarketticker(BasicNewsRecipe):
    title                 = 'The Market Ticker'
    __author__            = 'Darko Miletic'
    description           = 'Commentary On The Capital Markets'    
    oldest_article        = 7
    max_articles_per_feed = 100
    language = _('English')
    no_stylesheets        = True
    use_embedded_content  = True
    html2lrf_options = [  '--comment'       , description
                        , '--category'      , 'blog,news,finances'
                        , '--base-font-size', '10'
                       ]
    feeds = [(u'Posts', u'http://market-ticker.denninger.net/feeds/index.rss2')]
