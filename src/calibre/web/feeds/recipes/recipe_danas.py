#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
danas.rs
'''
import re

from calibre.web.feeds.news import BasicNewsRecipe

class Danas(BasicNewsRecipe):
    title                 = u'Danas'
    __author__            = 'Darko Miletic'
    description           = 'Vesti'
    publisher             = 'Danas d.o.o.'
    category              = 'news, politics, Serbia'    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = False
    remove_javascript     = True
    use_embedded_content  = False
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "monospace1";src:url(res:///opt/sony/ebook/FONT/tt0419m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: left; font-family: serif1, serif} .article_date{font-family: monospace1, monospace} .article_description{font-family: sans1, sans-serif} .navbar{font-family: monospace1, monospace}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
 

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [dict(name='div', attrs={'id':'left'})]
    remove_tags = [
                     dict(name='div', attrs={'class':['width_1_4','metaClanka','baner']})
                    ,dict(name='div', attrs={'id':'comments'})
                    ,dict(name=['object','link'])
                  ]

    feeds          = [ (u'Vesti', u'http://www.danas.rs/rss/rss.asp')]

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn"/>'
        soup.head.insert(0,mtag)    
        for item in soup.findAll(style=True):
            del item['style']
        return soup
    language              = _('Serbian')