#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
latimes.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class LATimes(BasicNewsRecipe):
    title                 = u'The Los Angeles Times'
    __author__            = u'Darko Miletic'
    description           = u'News from Los Angeles'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    keep_only_tags    = [ dict(name='div', attrs={'id':'center'   }) ]
    remove_tags_after = [ dict(name='div', attrs={'id':'socialnet'}) ]
    remove_tags       = [
                           dict(name='div' , attrs={'id':'wrapper_vid'    })
                          ,dict(name='div' , attrs={'id':'article_related'})
                          ,dict(name='div' , attrs={'id':'socialnet'      })
                        ]

    feeds          = [(u'News', u'http://feeds.latimes.com/latimes/news')]