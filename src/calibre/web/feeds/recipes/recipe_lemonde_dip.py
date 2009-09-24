#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
mondediplo.com
'''

import re, urllib
from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class LeMondeDiplomatiqueEn(BasicNewsRecipe):
    title                  = 'Le Monde diplomatique - English edition'
    __author__             = 'Darko Miletic'
    description            = 'Real journalism making sense of the world around us'
    publisher              = 'Le Monde diplomatique'
    category               = 'news, politics, world'
    no_stylesheets         = True
    oldest_article         = 31
    delay                  = 1
    encoding               = 'utf-8'
    needs_subscription     = True
    PREFIX                 = 'http://mondediplo.com/'
    LOGIN                  = PREFIX + '2009/09/02congo'
    INDEX                  = PREFIX + strftime('%Y/%m/')
    use_embedded_content   = False
    language               = 'en'

    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : language
                        }

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        br.open(self.LOGIN)
        if self.username is not None and self.password is not None:
            data = urllib.urlencode({ 'login':self.username
                                     ,'pass':self.password
                                     ,'enter':'enter'
                                   })
            br.open(self.LOGIN,data)
        return br

    keep_only_tags    =[dict(name='div', attrs={'id':'contenu'})]
    remove_tags = [dict(name=['object','link','script','iframe','base'])]
    
    def parse_index(self):
        articles = []
        soup = self.index_to_soup(self.INDEX)
        cnt = soup.find('div',attrs={'class':'som_num'})
        for item in cnt.findAll('li'):
            description = ''
            feed_link = item.find('a')
            desc = item.find('div',attrs={'class':'chapo'})
            if desc:
               description = desc.string
            if feed_link and feed_link.has_key('href'):
                url   = self.PREFIX + feed_link['href'].partition('/../')[2]
                title = self.tag_to_string(feed_link)
                date  = strftime(self.timefmt)
                articles.append({
                                  'title'      :title
                                 ,'date'       :date
                                 ,'url'        :url
                                 ,'description':description
                                })
        return [(soup.head.title.string, articles)]
        
