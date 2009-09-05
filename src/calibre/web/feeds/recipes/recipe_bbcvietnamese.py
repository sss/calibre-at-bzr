#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Huan Komrade T <huantnh at gmail.com>'
'''
bbc.co.uk
'''

from calibre.web.feeds.news import BasicNewsRecipe

class BBCVietnamese(BasicNewsRecipe):
    title          = u'BBC Vietnamese'
    __author__     = 'Huan Komrade T'
    description    = 'Vietnam news and current affairs from the British Broadcasting Corporation'
    no_stylesheets = True
    language = 'vi'

    encoding = 'utf-8'
    recursions = 0

    remove_tags    = [dict(name='div', attrs={'class':'footer'})]
    extra_css      = '.headline {font-size: x-large;} \n .fact { padding-top: 10pt  }' 

    feeds          = [
                      ('Index', 'http://www.bbc.co.uk/vietnamese/index.xml'), 
                      ('Vietnam', 'http://www.bbc.co.uk/vietnamese/vietnam/index.xml'),
                      ('Business', 'http://www.bbc.co.uk/vietnamese/business/index.xml'),
                      ('Culture', 'http://www.bbc.co.uk/vietnamese/culture/index.xml'),
                      ('Football', 'http://www.bbc.co.uk/vietnamese/football/index.xml'),
                      ('Forum', 'http://www.bbc.co.uk/vietnamese/forum/index.xml'),
                      ('In Depth', 'http://www.bbc.co.uk/vietnamese/indepth/index.xml'),
                    ]

    def print_version(self, url):
        return url.replace('http://www.bbc.co.uk/vietnamese/', 'http://www.bbc.co.uk/vietnamese/lg/')
