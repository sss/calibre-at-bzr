__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
standaard.be
'''

from calibre.web.feeds.news import BasicNewsRecipe

class DeStandaard(BasicNewsRecipe):
    title                 = u'De Standaard'
    __author__            = u'Darko Miletic'
    language              = _('Dutch')
    description           = u'News from Belgium'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
	
    keep_only_tags    = [dict(name='div' , attrs={'id':['intro','continued']})]
    
    feeds          = [(u'De Standaard Online', u'http://feeds.feedburner.com/dso-front')]

					 
    def get_article_url(self, article):
        return article.get('guid',  None)
 
    def print_version(self, url):
        return url.replace('/Detail.aspx?','/PrintArtikel.aspx?')
