#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
economist.com
'''
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup

import mechanize, string, urllib

class Economist(BasicNewsRecipe):

    title = 'The Economist'
    language = 'en'

    __author__ = "Kovid Goyal"
    description = 'Global news and current affairs from a European perspective'
    oldest_article = 7.0
    needs_subscription = False # Strange but true
    INDEX = 'http://www.economist.com/printedition'
    cover_url = 'http://www.economist.com/images/covers/currentcovereu_large.jpg'
    remove_tags = [dict(name=['script', 'noscript', 'title'])]
    remove_tags_before = dict(name=lambda tag: tag.name=='title' and tag.parent.name=='body')
    needs_subscription = True

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        br.open('http://www.economist.com')
        req = mechanize.Request(
                'http://www.economist.com/members/members.cfm?act=exec_login',
                headers = {
                    'Referer':'http://www.economist.com/',
                    },
                data=urllib.urlencode({
                    'logging_in' : 'Y',
                    'returnURL'  : '/',
                    'email_address': self.username,
                    'fakepword' : 'Password',
                    'pword'     : self.password,
                    'x'         : '0',
                    'y'         : '0',
                    }))
        br.open(req).read()
        return br

    def parse_index(self):
        soup = BeautifulSoup(self.browser.open(self.INDEX).read(),
                             convertEntities=BeautifulSoup.HTML_ENTITIES)
        index_started = False
        feeds = {}
        ans = []
        key = None
        for tag in soup.findAll(['h1', 'h2']):
            text = ''.join(tag.findAll(text=True))
            if tag.name == 'h1':
                if 'Classified ads' in text:
                    break
                if 'The world this week' in text:
                    index_started = True
                if not index_started:
                    continue
                text = string.capwords(text)
                if text not in feeds.keys():
                    feeds[text] = []
                if text not in ans:
                    ans.append(text)
                key = text
                continue
            if key is None:
                continue
            a = tag.find('a', href=True)
            if a is not None:
                url=a['href'].replace('displaystory', 'PrinterFriendly').strip()
                if url.startswith('Printer'):
                    url = '/'+url
                if url.startswith('/'):
                    url = 'http://www.economist.com' + url
                try:
                   subtitle = tag.previousSibling.contents[0].contents[0]
                   text = subtitle + ': ' + text
                except:
                   pass
                article = dict(title=text,
                    url = url,
                    description='', content='', date='')
                feeds[key].append(article)

        ans = [(key, feeds[key]) for key in ans if feeds.has_key(key)]
        return ans
