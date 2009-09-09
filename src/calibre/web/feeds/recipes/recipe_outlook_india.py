#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid at kovidgoyal.net>'
import re
from calibre.web.feeds.news import BasicNewsRecipe

class OutlookIndia(BasicNewsRecipe):

    title          = 'Outlook India'
    __author__     = 'Kovid Goyal and Sujata Raman'
    description    = 'Weekly news and current affairs in India'
    no_stylesheets = True
    encoding       = 'utf-8'
    language = 'en'

    recursions = 1
    extra_css = '''
                 body{font-family:Arial,Helvetica,sans-serif; font-size:xx-small;}
                .fspheading{color:#AF0E25 ; font-family:"Times New Roman",Times,serif; font-weight:bold ; font-size:large; }
                .fspauthor{color:#AF0E25; font-family:Arial,Helvetica,sans-serif; font-size:xx-small;}
                .fspintro{color:#666666; font-family:Arial,Helvetica,sans-serif; font-size:xx-small;}
                .fspchannelhome{font-family:Arial,Helvetica,sans-serif; font-size:x-small;}
                .fspphotocredit{color:##999999; font-family:Arial,Helvetica,sans-serif; font-size:xx-small;}
                '''
    keep_only_tags = [
                      dict(name='div', attrs={'id':["ctl00_cphpagemiddle_reparticle_ctl00_divfullstorytext","ctl00_cphpagemiddle_reparticle_ctl00_divartpic","ctl00_cphpagemiddle_reparticle_ctl00_divfspheading", "ctl00_cphpagemiddle_reparticle_ctl00_divartpiccaption",  "ctl00_cphpagemiddle_reparticle_ctl00_divartpiccredit","ctl00_cphpagemiddle_reparticle_ctl00_divfspintro", "ctl00_cphpagemiddle_reparticle_ctl00_divartbyline", "ctl00_cphpagemiddle_divglitteratiregulars","ctl00_cphpagemiddle_divcartoon","feedbackslatestfirst","ctl00_cphpagemiddle_divregulars","ctl00_cphpagemiddle_divquotes"]}),
                           ]
    remove_tags = [dict(name=['script','object','hr']),]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser(self)
        # This site sends article titles in the cookie which occasionally
        # contain non ascii characters causing httplib to fail. Instead just
        # disable cookies as they're not needed for download. Proper solution
        # would be to implement a unicode aware cookie jar
        br.set_cookiejar(None)
        return br

    def parse_index(self):


        soup = self.index_to_soup('http://www.outlookindia.com/issues.aspx')
        # find cover pic
        div = soup.find('div', attrs={'class':re.compile('cententcellpadding')})

        if div is None: return None
        a = div.find('a')

        if a is not None:
            href =  'http://www.outlookindia.com/' + a['href']

        soup = self.index_to_soup(href)
        cover = soup.find('img', attrs={'id':"ctl00_cphpagemiddle_dlissues_ctl00_imgcoverpic"}, src=True)
        if cover is not None:

            self.cover_url = cover['src']

         # end find cover pic
         #find current issue
        div = soup.find('table', attrs={'id':re.compile('ctl00_cphpagemiddle_dlissues')})

        if div is None: return None
        a = div.find('a')

        if a is not None:
            href =  'http://www.outlookindia.com/' + a['href']

        soup = self.index_to_soup(href)
        #find current issue

        #find the articles in the current issue
        articles = []

        for a in soup.findAll('a', attrs={'class':['contentpgsubheadinglink',"contentpgtext6",]}):

            if a and a.has_key('href'):

                url = 'http://www.outlookindia.com/' + a['href']
            else:
                url =''

            title = self.tag_to_string(a)

            desc = ''
            date = ''
            articles.append({
                                 'title':title,
                                 'date':date,
                                 'url':url,
                                 'description':desc,
                                })
        for a in soup.findAll('a', attrs={'id':["ctl00_cphpageleft_hlglitterati","ctl00_cphpageleft_hlposcape",]}):

            if a and a.has_key('href'):

                url = 'http://www.outlookindia.com/' + a['href']
            else:
                url =''

            title = self.tag_to_string(a)

            desc = ''
            date = ''
            articles.append({
                                 'title':title,
                                 'date':date,
                                 'url':url,
                                 'description':desc,
                                })


        return [('Current Issue', articles)]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        return self.adeify_images(soup)



    def postrocess_html(self, soup, first):

            for item in soup.findAll(align = "left"):
                del item['align']

            for tag in soup.findAll(name=['table', 'tr','td','tbody','ul','li','font','span']):
                tag.name = 'div'

            return soup

