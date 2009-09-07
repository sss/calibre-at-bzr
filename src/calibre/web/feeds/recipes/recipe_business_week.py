#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
businessweek.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class BusinessWeek(BasicNewsRecipe):
    title          = 'Business Week'
    description    = 'Business News, Stock Market and Financial Advice'
    __author__     = 'ChuckEggDotCom and Sujata Raman'
    language = 'en'

    oldest_article = 7
    max_articles_per_feed = 10
    no_stylesheets = True


    extra_css = '''
                h1{font-family :Arial,Helvetica,sans-serif; font-size:large;}
                h2{font-family :Arial,Helvetica,sans-serif; font-size:small;color:#666666;}
                p{font-family :Arial,Helvetica,sans-serif; }
                #lede600{font-size:x-small;}
                #storybody{font-size:x-small;}
                .strap{font-family :Arial,Helvetica,sans-serif; font-size:x-small; color:#064599;}
                .byline{font-family :Arial,Helvetica,sans-serif; font-size:x-small;}
                .postedBy{font-family :Arial,Helvetica,sans-serif; font-size:x-small;color:#666666;}
                .trackback{font-family :Arial,Helvetica,sans-serif; font-size:x-small;color:#666666;}
                .date{font-family :Arial,Helvetica,sans-serif; font-size:x-small;color:#666666;}
                .wrapper{font-family :Arial,Helvetica,sans-serif; font-size:x-small;}
                .photoCredit{font-family :Arial,Helvetica,sans-serif; font-size:x-small;color:#666666;}
                .tagline{font-family :Arial,Helvetica,sans-serif; font-size:x-small;color:#666666;}
                '''

    remove_tags = [  dict(name='div', attrs={'id':["bw2-header","column2","wrapper-bw2-footer","wrapper-mgh-footer","inset","commentForm","commentDisplay","bwExtras","bw2-umbrella","readerComments","pageNav","leg"]}),
                    ]

    feeds          = [
                      (u'Top Stories', u'http://www.businessweek.com/topStories/rss/topStories.rss'),
                      (u'Top News', u'http://www.businessweek.com/rss/bwdaily.rss'),
                      (u'Asia', u'http://www.businessweek.com/rss/asia.rss'),
                      (u'Autos', u'http://www.businessweek.com/rss/autos/index.rss'),
                      (u'Classic Cars', u'http://rss.businessweek.com/bw_rss/classiccars'),
                      (u'Hybrids', u'http://rss.businessweek.com/bw_rss/hybrids'),
                      (u'Europe', u'http://www.businessweek.com/rss/europe.rss'),
                      (u'Auto Reviews', u'http://rss.businessweek.com/bw_rss/autoreviews'),
                      (u'Innovation & Design', u'http://www.businessweek.com/rss/innovate.rss'),
                      (u'Architecture', u'http://www.businessweek.com/rss/architecture.rss'),
                      (u'Brand Equity', u'http://www.businessweek.com/rss/brandequity.rss'),
                      (u'Auto Design', u'http://www.businessweek.com/rss/carbuff.rss'),
                      (u'Game Room', u'http://rss.businessweek.com/bw_rss/gameroom'),
                      (u'Technology', u'http://www.businessweek.com/rss/technology.rss'),
                      (u'Investing', u'http://rss.businessweek.com/bw_rss/investor'),
                      (u'Small Business', u'http://www.businessweek.com/rss/smallbiz.rss'),
                      (u'Careers', u'http://rss.businessweek.com/bw_rss/careers'),
                      (u'B-Schools', u'http://www.businessweek.com/rss/bschools.rss'),
                      (u'Magazine Selections', u'http://www.businessweek.com/rss/magazine.rss'),
                      (u'CEO Guide to Tech', u'http://www.businessweek.com/rss/ceo_guide_tech.rss'),
                      ]

    def get_article_url(self, article):

        url = article.get('guid', None)

        if 'podcasts' in url or 'surveys' in url:
            url = None

        return url

    def postrocess_html(self, soup, first):

            for tag in soup.findAll(name=['ul','li']):
                tag.name = 'div'

            return soup

