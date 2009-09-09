#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
politico.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Politico(BasicNewsRecipe):
    title                 = 'Politico'
    __author__            = 'Darko Miletic'
    description           = 'Political news from USA'
    publisher             = 'Capitol News Company, LLC'
    category              = 'news, politics, USA'
    oldest_article        = 7
    max_articles_per_feed = 100
    use_embedded_content  = False
    no_stylesheets        = True
    remove_javascript     = True
    encoding              = 'cp1252'
    language = 'en'

    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True' 

    remove_tags       = [dict(name=['notags','embed','object','link','img'])]

    feeds = [
               (u'Top Stories' , u'http://www.politico.com/rss/politicopicks.xml' )
              ,(u'Congress'    , u'http://www.politico.com/rss/congress.xml'      )
              ,(u'Ideas'       , u'http://www.politico.com/rss/ideas.xml'         )
              ,(u'Life'        , u'http://www.politico.com/rss/life.xml'          )
              ,(u'Lobbyists'   , u'http://www.politico.com/rss/lobbyists.xml'     )
              ,(u'Pitboss'     , u'http://www.politico.com/rss/pitboss.xml'       )
              ,(u'Politics'    , u'http://www.politico.com/rss/politics.xml'      )
              ,(u'Roger Simon' , u'http://www.politico.com/rss/rogersimon.xml'    )
              ,(u'Suite Talk'  , u'http://www.politico.com/rss/suitetalk.xml'     )
              ,(u'Playbook'    , u'http://www.politico.com/rss/playbook.xml'      )
              ,(u'The Huddle'  , u'http://www.politico.com/rss/huddle.xml'        )
            ]

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="en-US"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    def print_url(self, soup, default):
        printtags = soup.findAll('a',href=True)
        for printtag in printtags:
            if printtag.string == "Print":
               return printtag['href']
        return default

    def print_version(self, url):
        soup = self.index_to_soup(url)
        return self.print_url(soup, None)
