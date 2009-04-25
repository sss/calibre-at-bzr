# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Gerhard Aigner <gerhard.aigner at gmail.com>'

''' http://www.derstandard.at - Austrian Newspaper '''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class TelepolisNews(BasicNewsRecipe):
	title          = u'Telepolis (News)'
	__author__ = 'Gerhard Aigner'
	publisher = 'Heise Zeitschriften Verlag GmbH & Co KG'
	description = 'News from telepolis'
	category = 'news'
	oldest_article = 7
	max_articles_per_feed = 100
	recursion = 0
	no_stylesheets = True
	encoding = "utf-8"

	use_embedded_content = False
	remove_empty_feeds = True

	preprocess_regexps = [(re.compile(r'<a[^>]*>', re.DOTALL|re.IGNORECASE), lambda match: ''),
		(re.compile(r'</a>', re.DOTALL|re.IGNORECASE), lambda match: ''),]

	keep_only_tags = [dict(name = 'table',attrs={'class':'blogtable'})]
	remove_tags = [dict(name='img'), dict(name='td',attrs={'class':'blogbottom'})]

	feeds          = [(u'News', u'http://www.heise.de/tp/news.rdf')]

	html2lrf_options = [
		'--comment'  , description
		, '--category' , category
		, '--publisher', publisher
	]

	html2epub_options  = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

	def get_article_url(self, article):
		'''if the linked article is of kind artikel don't take it'''
		if (article.link.count('artikel') > 0) :
			return None
		return article.link

	def preprocess_html(self, soup):
		mtag = '<meta http-equiv="Content-Type" content="text/html; charset=' + self.encoding + '">'
		soup.head.insert(0,mtag)
		return soup