#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
ambito.com
'''


from calibre.web.feeds.news import BasicNewsRecipe

class Ambito(BasicNewsRecipe):
    title                 = 'Ambito.com'
    __author__            = 'Darko Miletic'
    description           = 'Informacion Libre las 24 horas'    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'iso--8859-1'
    cover_url             = 'http://www.ambito.com/img/logo_.jpg'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Argentina'
                        , '--publisher'     , title
                        ]

    feeds = [ 
              (u'Principales Noticias', u'http://www.ambito.com/rss/noticiasp.asp'                         )
             ,(u'Economia'            , u'http://www.ambito.com/rss/noticias.asp?S=Econom%EDa'             )
             ,(u'Politica'            , u'http://www.ambito.com/rss/noticias.asp?S=Pol%EDtica'             )
             ,(u'Informacion General' , u'http://www.ambito.com/rss/noticias.asp?S=Informaci%F3n%20General')
             ,(u'Agro'                , u'http://www.ambito.com/rss/noticias.asp?S=Agro'                   )
             ,(u'Internacionales'     , u'http://www.ambito.com/rss/noticias.asp?S=Internacionales'        )
             ,(u'Deportes'            , u'http://www.ambito.com/rss/noticias.asp?S=Deportes'               )
             ,(u'Espectaculos'        , u'http://www.ambito.com/rss/noticias.asp?S=Espect%E1culos'         )
             ,(u'Tecnologia'          , u'http://www.ambito.com/rss/noticias.asp?S=Tecnologia'             )
             ,(u'Salud'               , u'http://www.ambito.com/rss/noticias.asp?S=Salud'                  )
             ,(u'Ambito Nacional'     , u'http://www.ambito.com/rss/noticias.asp?S=Ambito%20Nacional'      )
            ]

    def print_version(self, url):
        return url.replace('http://www.ambito.com/noticia.asp?','http://www.ambito.com/noticias/imprimir.asp?')
