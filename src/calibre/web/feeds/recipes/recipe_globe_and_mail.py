#!/usr/bin/env  python
__license__   = 'GPL v3'

__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
globeandmail.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class GlobeAndMail(BasicNewsRecipe):
    title = u'Globe and Mail'
    language = 'en_CA'

    __author__ = 'Kovid Goyal'
    oldest_article = 2
    max_articles_per_feed = 10
    no_stylesheets = True
    extra_css = '''
    h3 {font-size: 22pt; font-weight:bold; margin:0px; padding:0px 0px 8pt 0px;}
    h4 {margin-top: 0px;}
    #byline { font-family: monospace; font-weight:bold; }
    #placeline {font-weight:bold;}
    #credit {margin-top:0px;}
    .tag {font-size: 22pt;}'''
    description = 'Canada\'s national newspaper'
    remove_tags_before = dict(id="article-top")
    remove_tags = [
		{'id':['util', 'article-tabs', 'comments', 'article-relations',
		'gallery-controls', 'video', 'galleryLoading','deck','header'] },
		{'class':['credit','inline-img-caption','tab-pointer'] },
		dict(name='div', attrs={'id':'lead-photo'}),
		dict(name='div', attrs={'class':'right'}),
		dict(name='div', attrs={'id':'footer'}),
		dict(name='div', attrs={'id':'beta-msg'}),
		dict(name='img', attrs={'class':'headshot'}),
		dict(name='div', attrs={'class':'brand'}),
		dict(name='div', attrs={'id':'nav-wrap'}),
		dict(name='div', attrs={'id':'featureTopics'}),
		dict(name='div', attrs={'id':'videoNav'}),
		dict(name='div', attrs={'id':'blog-header'}),
		dict(name='div', attrs={'id':'right-rail'}),
		dict(name='div', attrs={'id':'group-footer-container'}),
		dict(name=['iframe','img'])
		]
    remove_tags_after = [{'id':['article-content']},
		{'class':['pull','inline-img'] },
		dict(name='img', attrs={'class':'inline-media-embed'}),
		]
    feeds = [
            (u'Latest headlines', u'http://www.theglobeandmail.com/?service=rss'),
            (u'Top stories', u'http://www.theglobeandmail.com/?service=rss&feed=topstories'),
            (u'National', u'http://www.theglobeandmail.com/news/national/?service=rss'),
            (u'Politics', u'http://www.theglobeandmail.com/news/politics/?service=rss'),
            (u'World', u'http://www.theglobeandmail.com/news/world/?service=rss'),
            (u'Business', u'http://www.theglobeandmail.com/report-on-business/?service=rss'),
            (u'Opinions', u'http://www.theglobeandmail.com/news/opinions/?service=rss'),
            (u'Columnists', u'http://www.theglobeandmail.com/news/opinions/columnists/?service=rss'),
            (u'Globe Investor', u'http://www.theglobeandmail.com/globe-investor/?service=rss'),
            (u'Sports', u'http://www.theglobeandmail.com/sports/?service=rss'),
            (u'Technology', u'http://www.theglobeandmail.com/news/technology/?service=rss'),
            (u'Arts', u'http://www.theglobeandmail.com/news/arts/?service=rss'),
            (u'Life', u'http://www.theglobeandmail.com/life/?service=rss'),
            (u'Blogs', u'http://www.theglobeandmail.com/blogs/?service=rss'),
            (u'Real Estate', u'http://www.theglobeandmail.com/real-estate/?service=rss'),
            (u'Auto', u'http://www.theglobeandmail.com/auto/?service=rss')
            ]

