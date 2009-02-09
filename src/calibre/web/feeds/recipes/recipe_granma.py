#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
granma.cubaweb.cu
'''
import urllib

from calibre.web.feeds.news import BasicNewsRecipe

class Granma(BasicNewsRecipe):
    title                 = 'Diario Granma'
    __author__            = 'Darko Miletic'
    description           = 'Organo oficial del Comite Central del Partido Comunista de Cuba'    
    publisher             = 'Granma'
    category              = 'news, politics, Cuba'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    cover_url             = 'http://www.granma.cubaweb.cu/imagenes/granweb229d.jpg'
    remove_javascript     = True
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 

    keep_only_tags = [dict(name='table', attrs={'height':'466'})]

    feeds = [(u'Noticias', u'http://www.granma.cubaweb.cu/noticias.xml' )]

    
    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="es-CU"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll('table'):
            if item.has_key('width'):
               del item['width']
            if item.has_key('height'):
               del item['height']            
        for item in soup.findAll(style=True):
            del item['style']
        return soup
    
    language = _('Spanish')