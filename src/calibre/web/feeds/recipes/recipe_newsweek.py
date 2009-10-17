__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
    
import re
from calibre import strftime
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.web.feeds.news import BasicNewsRecipe
    
class Newsweek(BasicNewsRecipe):
    

    title          = 'Newsweek'
    __author__     = 'Kovid Goyal and Sujata Raman'
    description    = 'Weekly news and current affairs in the US'
    no_stylesheets = True

    extra_css = '''
                    h1{font-family:Arial,Helvetica,sans-serif; font-size:large; color:#383733;}
                    .deck{font-family:Georgia,sans-serif; color:#383733;}
                    .bylineDate{font-family:georgia ; color:#58544A; font-size:x-small;}
                    .authorInfo{font-family:arial,helvetica,sans-serif; color:#0066CC; font-size:x-small;}
                    .articleUpdated{font-family:arial,helvetica,sans-serif; color:#73726C; font-size:x-small;}
                    .issueDate{font-family:arial,helvetica,sans-serif; color:#73726C; font-size:x-small; font-style:italic;}
                    h5{font-family:arial,helvetica,sans-serif; color:#73726C; font-size:x-small;}
                    h6{font-family:arial,helvetica,sans-serif; color:#73726C; font-size:x-small;}
                    .story{font-family:georgia,sans-serif ; color:#363636;}
                    .photoCredit{color:#999999; font-family:Arial,Helvetica,sans-serif;font-size:x-small;}
                    .photoCaption{color:#0A0A09;font-family:Arial,Helvetica,sans-serif;font-size:x-small;}
                    .fwArticle{font-family:Arial,Helvetica,sans-serif;font-size:x-small;font-weight:bold;}
                    '''
   
    encoding       = 'utf-8'
    language = 'en'

    remove_tags = [
            {'class':['fwArticle noHr','fwArticle','subinfo','hdlBulletItem','head-content','navbar','link', 'ad', 'sponsorLinksArticle', 'mm-content',
                'inline-social-links-wrapper', 'email-article','ToolBox',
                'inlineComponentRight',
                'comments-and-social-links-wrapper', 'EmailArticleBlock']},
            {'id' : ['footer', 'ticker-data', 'topTenVertical',
                'digg-top-five', 'mesothorax', 'nw-comments',
                'ToolBox', 'EmailMain']},
            {'class': re.compile('related-cloud')},
            dict(name='li', attrs={'id':['slug_bigbox']})
            ]

  
    keep_only_tags = [{'class':['article HorizontalHeader', 'articlecontent','photoBox']}, ]
    recursions = 1
    match_regexps = [r'http://www.newsweek.com/id/\S+/page/\d+']

    def find_title(self, section):
        d = {'scope':'Scope', 'thetake':'The Take', 'features':'Features',
                None:'Departments', 'culture':'Culture'}
        ans = None
        a = section.find('a', attrs={'name':True})
        if a is not None:
            ans = a['name']
        return d.get(ans, ans)


    def find_articles(self, section):
        ans = []
        for x in section.findAll('h5'):
            title = ' '.join(x.findAll(text=True)).strip()
            a = x.find('a')
            if not a: continue
            href = a['href']
            ans.append({'title':title, 'url':href, 'description':'', 'date': strftime('%a, %d %b')})
        if not ans:
            for x in section.findAll('div', attrs={'class':'hdlItem'}):
                a = x.find('a', href=True)
                if not a : continue
                title = ' '.join(a.findAll(text=True)).strip()
                href = a['href']
                if 'http://xtra.newsweek.com' in href: continue
                ans.append({'title':title, 'url':href, 'description':'', 'date': strftime('%a, %d %b')})

        #for x in ans:
        #    x['url'] += '/output/print'
        return ans


    def parse_index(self):
        soup = self.get_current_issue()
        if not soup:
            raise RuntimeError('Unable to connect to newsweek.com. Try again later.')
        sections = soup.findAll('div', attrs={'class':'featurewell'})
        titles = map(self.find_title, sections)
        articles = map(self.find_articles, sections)
        ans = list(zip(titles, articles))
        def fcmp(x, y):
            tx, ty = x[0], y[0]
            if tx == "Features": return cmp(1, 2)
            if ty == "Features": return cmp(2, 1)
            return cmp(tx, ty)
        return sorted(ans, cmp=fcmp)

    def ensure_html(self, soup):
        root = soup.find(name=True)
        if root.name == 'html': return soup
        nsoup = BeautifulSoup('<html><head></head><body/></html>')
        nroot = nsoup.find(name='body')
        for x in soup.contents:
            if getattr(x, 'name', False):
                x.extract()
                nroot.insert(len(nroot), x)
        return nsoup

    def postprocess_html(self, soup, first_fetch):
        if not first_fetch:
            h1 = soup.find(id='headline')
            if h1:
                h1.extract()
            div = soup.find(attrs={'class':'articleInfo'})
            if div:
                div.extract()
        divs = list(soup.findAll('div', 'pagination'))
        if not divs:
            return self.ensure_html(soup)
        for div in divs[1:]: div.extract()
        all_a = divs[0].findAll('a', href=True)
        divs[0]['style']="display:none"
        if len(all_a) > 1:
            all_a[-1].extract()
        test = re.compile(self.match_regexps[0])
        for a in soup.findAll('a', href=test):
            if a not in all_a:
                del a['href']
        return self.ensure_html(soup)

    def get_current_issue(self):
        soup = self.index_to_soup('http://www.newsweek.com')
        div = soup.find('div', attrs={'class':re.compile('more-from-mag')})
        if div is None: return None
        a = div.find('a')
        if a is not None:
            href = a['href'].split('#')[0]
            return self.index_to_soup(href)

    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup('http://www.newsweek.com')
        link_item = soup.find('div',attrs={'class':'cover-image'})
        if link_item and link_item.a and link_item.a.img:
           cover_url = link_item.a.img['src']
        return cover_url


    def postprocess_book(self, oeb, opts, log) :

        def extractByline(href) :
            soup = BeautifulSoup(str(oeb.manifest.hrefs[href]))
            byline = soup.find(True,attrs={'class':'authorInfo'})
            byline = self.tag_to_string(byline) if byline is not None else ''
            issueDate = soup.find(True,attrs={'class':'issueDate'})
            issueDate = self.tag_to_string(issueDate) if issueDate is not None else ''
            issueDate = re.sub(',','', issueDate)
            if byline > '' and issueDate > '' :
                return byline + ' | ' + issueDate
            else :
                return byline + issueDate

        def extractDescription(href) :
            soup = BeautifulSoup(str(oeb.manifest.hrefs[href]))
            description = soup.find(True,attrs={'name':'description'})
            if description is not None and description.has_key('content'):
                description = description['content']
                if description.startswith('Newsweek magazine online plus') :
                    description = soup.find(True, attrs={'class':'story'})
                    firstPara = soup.find('p')
                    description = self.tag_to_string(firstPara)
            else :
                description = soup.find(True, attrs={'class':'story'})
                firstPara = soup.find('p')
                description = self.tag_to_string(firstPara)
            return description

        for section in oeb.toc :
            for article in section :
                if article.author is None :
                    article.author = extractByline(article.href)
                if article.description is None :
                    article.description = extractDescription(article.href)
        return

