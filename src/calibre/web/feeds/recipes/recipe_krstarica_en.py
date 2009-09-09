#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
vesti.krstarica.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Krstarica_en(BasicNewsRecipe):
    title                 = 'Krstarica - news in english'
    __author__            = 'Darko Miletic'
    description           = 'News from Serbia and world'    
    publisher             = 'Krstarica'
    category              = 'news, politics, Serbia'
    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True
    encoding              = 'utf-8'
    language = 'en'

    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em}"' 
        
    feeds          = [
                        (u'Daily news', u'http://vesti.krstarica.com/index.php?rss=1&rubrika=aktuelno&lang=1'     )
                       ,(u'Serbia'    , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=scg&lang=1'          )
                       ,(u'Politics'  , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=politika&lang=1'     )
                       ,(u'Economy'   , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=ekonomija&lang=1'    )
                       ,(u'Culture'   , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=kultura&lang=1'      )
                       ,(u'Sports'    , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=sport&lang=1'        )
                     ]

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>'
        soup.head.insert(0,mtag)
        titletag = soup.find('h4')
        if titletag:
           realtag = titletag.parent.parent
           realtag.extract()
           for item in soup.findAll(['table','center']):
               item.extract()
           soup.body.insert(1,realtag)            
           realtag.name = 'div'
        for item in soup.findAll(style=True):
            del item['style']
        for item in soup.findAll(align=True):
            del item['align']
        return soup
