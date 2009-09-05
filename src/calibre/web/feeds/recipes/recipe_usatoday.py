#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
usatoday.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
import re

class USAToday(BasicNewsRecipe):

    title = 'USA Today'
    timefmt  = ' [%d %b %Y]'
    __author__ = 'Kovid Goyal and Sujata Raman'
    max_articles_per_feed = 20
    language = 'en'


    no_stylesheets = True
    extra_css = '''
            .inside-head{font-family:Arial,Helvetica,sans-serif; font-size:large; font-weight:bold }
            .inside-head2{font-family:Arial,Helvetica,sans-serif; font-size:large; font-weight:bold }
            .inside-head3{font-family:Arial,Helvetica,sans-serif; font-size:large; font-weight:bold }
            h3{font-family:Arial,Helvetica,sans-serif; font-size:large; font-weight:bold; }
            h4{font-family:Arial,Helvetica,sans-serif; font-size:x-small; font-weight:bold; }
            .side-by-side{font-family:Arial,Helvetica,sans-serif; font-size:x-small;}
            #byLineTag{font-family:Arial,Helvetica,sans-serif; font-size:xx-small;}
            .inside-copy{font-family:Arial,Helvetica,sans-serif; font-size:x-small;text-align:left;}
            .caption{font-family:Arial,Helvetica,sans-serif; font-size:x-small;}
            li{font-family:Arial,Helvetica,sans-serif; font-size:x-small;text-align:left ;}
            .vatext{font-family:Arial,Helvetica,sans-serif; font-size:x-small;text-align:left ;}
            .vaTextBold{font-family:Arial,Helvetica,sans-serif; font-size:x-small;font-weight:bold; color:#666666;}
            '''
    remove_tags = [
                   {'class':['tagListLabel','piped-taglist-string',]}
                  ]

    conversion_options = { 'linearize_tables' : True }

    preprocess_regexps = [
        (re.compile(r'<BODY.*?<!--Article Goes Here-->', re.IGNORECASE | re.DOTALL), lambda match : '<BODY>'),
        (re.compile(r'<!--Article End-->.*?</BODY>', re.IGNORECASE | re.DOTALL), lambda match : '</BODY>'),
        ]


    feeds =  [
                ('Top Headlines', 'http://rssfeeds.usatoday.com/usatoday-NewsTopStories'),
                ('Sport Headlines', 'http://rssfeeds.usatoday.com/UsatodaycomSports-TopStories'),
                ('Tech Headlines', 'http://rssfeeds.usatoday.com/usatoday-TechTopStories'),
                ('Travel Headlines', 'http://rssfeeds.usatoday.com/UsatodaycomTravel-TopStories'),
                ('Money Headlines', 'http://rssfeeds.usatoday.com/UsatodaycomMoney-TopStories'),
                ('Entertainment Headlines', 'http://rssfeeds.usatoday.com/usatoday-LifeTopStories'),
                ('Weather Headlines', 'http://rssfeeds.usatoday.com/usatoday-WeatherTopStories'),
                ('Most Popular', 'http://rssfeeds.usatoday.com/Usatoday-MostViewedArticles'),
                ]

    ## Getting the print version

    def print_version(self, url):
        return 'http://www.printthis.clickability.com/pt/printThis?clickMap=printThis&fb=Y&url=' + url

    def postprocess_html(self, soup, first_fetch):
        for t in soup.findAll(['table', 'tr', 'td']):
            t.name = 'div'
        return soup
