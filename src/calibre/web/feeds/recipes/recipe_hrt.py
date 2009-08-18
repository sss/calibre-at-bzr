#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
www.hrt.hr
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class HRT(BasicNewsRecipe):
    title                 = 'HRT: Vesti'
    __author__            = 'Darko Miletic'
    description           = 'News from Croatia'
    publisher             = 'HRT'
    category              = 'news, politics, Croatia, HRT'
    no_stylesheets        = True
    encoding              = 'utf-8'
    use_embedded_content  = False
    language              = _("Croatian")
    lang                  = 'hr-HR'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'
    
    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }

    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [dict(name='div', attrs={'class':'bigVijest'})]
        
    remove_tags = [dict(name=['object','link','embed'])]

    remove_tags_after  = dict(name='div', attrs={'class':'nsAuthor'})
    
    feeds = [
               (u'Vijesti'             , u'http://www.hrt.hr/?id=316&type=100&rss=vijesti'     )
              ,(u'Sport'               , u'http://www.hrt.hr/?id=316&type=100&rss=sport'       )
              ,(u'Zabava'              , u'http://www.hrt.hr/?id=316&type=100&rss=zabava'      )
              ,(u'Filmovi i serije'    , u'http://www.hrt.hr/?id=316&type=100&rss=filmovi'     )
              ,(u'Dokumentarni program', u'http://www.hrt.hr/?id=316&type=100&rss=dokumentarci')
              ,(u'Glazba'              , u'http://www.hrt.hr/?id=316&type=100&rss=glazba'      )
              ,(u'Kultura'             , u'http://www.hrt.hr/?id=316&type=100&rss=kultura'     )
              ,(u'Mladi'               , u'http://www.hrt.hr/?id=316&type=100&rss=mladi'       )
              ,(u'Manjine'             , u'http://www.hrt.hr/?id=316&type=100&rss=manjine'     )
              ,(u'Radio'               , u'http://www.hrt.hr/?id=316&type=100&rss=radio'       )
            ]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=UTF-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        for item in soup.findAll(style=True):
            del item['style']        
        return self.adeify_images(soup)
