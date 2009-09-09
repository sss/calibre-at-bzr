#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.theoldfoodie.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class TheOldFoodie(BasicNewsRecipe):
    title                 = 'The Old Foodie'
    __author__            = 'Darko Miletic'
    description           = 'Food blog'
    category              = 'cuisine, food, blog'
    oldest_article        = 30
    max_articles_per_feed = 100
    use_embedded_content  = True
    no_stylesheets        = True
    encoding              = 'utf-8'
    language = 'en'


    conversion_options = {
                             'comments'    : description
                            ,'tags'        : category
                            ,'language'    : 'en'
                         }

    feeds = [(u'Articles', u'http://www.theoldfoodie.com/feeds/posts/default?alt=rss')]
