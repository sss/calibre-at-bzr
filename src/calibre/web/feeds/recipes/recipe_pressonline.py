#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
pressonline.rs
'''

import re
from calibre.web.feeds.recipes import BasicNewsRecipe

class PressOnline(BasicNewsRecipe):
    title                 = 'Press Online'
    __author__            = 'Darko Miletic'
    description           = 'Press Online portal dnevnih novina Press.Najnovije vesti iz Srbije i sveta,Sport,Dzet Set,Politika,Hronika,Komenteri,Zabava,Slike,Video,Horoskop,Nagradne igre,Kvizovi,Igrice'
    publisher             = 'Press Publishing group'
    category              = 'news, politics, Serbia'    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'utf8'
    use_embedded_content  = True
    cover_url             = 'http://www.pressonline.rs/img/logo.gif'
    language              = _('Serbian')

    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} img {margin-top: 0em; margin-bottom: 0.4em}"' 
     
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    feeds = [ 
               (u'Vesti Dana'      , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=37')
              ,(u'Politika'        , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=29')
              ,(u'U Fokusu'        , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=33')
              ,(u'Globus'          , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=40')
              ,(u'Komentar Dana'   , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=62')
              ,(u'Hronika'         , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=39')
              ,(u'Regioni'         , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=56')
              ,(u'Republika Srpska', u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=51')
              ,(u'Beograd'         , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=43')
              ,(u'Dzet-Set Svet'   , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=41')
              ,(u'Lifestyle'       , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=42')
              ,(u'Sport'           , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=44')
              ,(u'Press Magazine'  , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=63')
              ,(u'Lola'            , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=70')
              ,(u'Duplerica'       , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=72')
              ,(u'Presspedia'      , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=80')
              ,(u'Kolumne'         , u'http://www.pressonline.rs/page/stories/sr.html?view=rss&sectionId=57')              
            ]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = 'sr-Latn-RS'
        soup.html['lang']     = 'sr-Latn-RS'
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn-RS"/>\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
        for img in soup.findAll('img', align=True):
            del img['align']
        return soup        