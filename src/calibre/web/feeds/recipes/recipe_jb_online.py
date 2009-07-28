#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
jbonline.terra.com.br
'''

from calibre.web.feeds.news import BasicNewsRecipe

class JBOnline(BasicNewsRecipe):
    title                 = 'Jornal Brasileiro Online'
    __author__            = 'Darko Miletic'
    description           = 'News from Brasil'
    publisher             = 'Jornal Brasileiro'
    category              = 'news, politics, Brasil'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    cover_url             = 'http://jbonline.terra.com.br/img/logo_01.gif'
    remove_javascript     = True

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags = [dict(name='div', attrs={'id':'corpoNoticia'})]

    remove_tags = [dict(name=['script','object','form'])]

    feeds = [(u'Todos as editorias', u'http://jbonline.terra.com.br/extra/rsstrjb.xml')]

    def preprocess_html(self, soup):
        ifr = soup.find('iframe')
        if ifr:
           ifr.extract()
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    language = _('Portuguese')
