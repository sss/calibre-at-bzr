#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.tijd.be
'''
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class DeTijd(BasicNewsRecipe):
    title                 = 'De Tijd'
    __author__            = 'Darko Miletic'
    description           = 'News from Belgium in Dutch'
    publisher             = 'De Tijd'
    category              = 'news, politics, Belgium'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    language = 'nl'

    lang                  = 'nl-BE'
    direction             = 'ltr'

    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0cm; margin-top: 0em; margin-bottom: 0.5em} "'

    keep_only_tags = [dict(name='div', attrs={'id':'lcol'})]
    remove_tags    = [
                         dict(name=['embed','object'])
                       , dict (name='div',attrs={'id':'art_reactwrap'})
                     ]
    remove_tags_after  = dict(name='div', attrs={'id':'art_author'})

    feeds = [
              (u'Volledig nieuwsaanbod', u'http://www.tijd.be/rss/nieuws.xml'        )
             ,(u'Markten'              , u'http://www.tijd.be/rss/markten.xml'       )
             ,(u'Ondernemingen'        , u'http://www.tijd.be/rss/ondernemingen.xml' )
             ,(u'Chemie-Farma'         , u'http://www.tijd.be/rss/chemie_farma.xml'  )
             ,(u'Consumptie'           , u'http://www.tijd.be/rss/consumptie.xml'    )
             ,(u'Diensten'             , u'http://www.tijd.be/rss/diensten.xml'      )
             ,(u'Energie'              , u'http://www.tijd.be/rss/energie.xml'       )
             ,(u'Financen'             , u'http://www.tijd.be/rss/financien.xml'     )
             ,(u'Industrie'            , u'http://www.tijd.be/rss/industrie.xml'     )
             ,(u'Media'                , u'http://www.tijd.be/rss/media_telecom.xml' )
             ,(u'Technologie'          , u'http://www.tijd.be/rss/technologie.xml'   )
             ,(u'Economie & Financien' , u'http://www.tijd.be/rss/economie.xml'      )
             ,(u'Binnenland'           , u'http://www.tijd.be/rss/binnenland.xml'    )
             ,(u'Buitenland'           , u'http://www.tijd.be/rss/buitenland.xml'    )
             ,(u'De wijde wereld'      , u'http://www.tijd.be/rss/cultuur.xml'       )
            ]

    def preprocess_html(self, soup):
        del soup.body['onload']
        for item in soup.findAll(style=True):
            del item['style']
        soup.html['lang']     = self.lang
        soup.html['dir' ]     = self.direction
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return soup

