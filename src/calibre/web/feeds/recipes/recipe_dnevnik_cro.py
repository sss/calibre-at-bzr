#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
dnevnik.hr
'''

import re
from calibre.web.feeds.recipes import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class DnevnikCro(BasicNewsRecipe):
    title                 = 'Dnevnik - Hr'
    __author__            = 'Darko Miletic'
    description           = "Vijesti iz Hrvatske"
    publisher             = 'Dnevnik.hr'
    category              = 'news, politics, Croatia'    
    oldest_article        = 2
    max_articles_per_feed = 100
    delay                 = 4
    no_stylesheets        = True
    encoding              = 'utf-8'
    use_embedded_content  = False
    language              = _('Croatian')
    lang                  = 'hr-HR'
    direction             = 'ltr'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'
    
    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }
     
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [dict(name='div', attrs={'id':'article'})]
        
    remove_tags = [
                    dict(name=['object','link','embed'])
                   ,dict(name='div', attrs={'class':'menu'})
                   ,dict(name='div', attrs={'id':'video'})
                  ]

    remove_tags_after  = dict(name='div', attrs={'id':'content'})

    feeds = [(u'Vijesti', u'http://rss.dnevnik.hr/index.rss')]

    def preprocess_html(self, soup):
        soup.html['lang'] = self.lang
        soup.html['dir' ] = self.direction
        
        attribs = [  'style','font','valign'
                    ,'colspan','width','height'
                    ,'rowspan','summary','align'
                    ,'cellspacing','cellpadding'
                    ,'frames','rules','border'
                  ]
        for item in soup.body.findAll(name=['table','td','tr','th','caption','thead','tfoot','tbody','colgroup','col']):
            item.name = 'div'
            for attrib in attribs:
                if item.has_key(attrib):
                   del item[attrib]                        
        
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=UTF-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return self.adeify_images(soup)

