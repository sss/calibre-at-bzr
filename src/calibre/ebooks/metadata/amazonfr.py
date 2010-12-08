from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'

import sys, textwrap, re, traceback
from threading import Thread
from Queue import Queue
from urllib import urlencode
from math import ceil

from lxml.html import soupparser, tostring

from calibre.utils.date import parse_date, utcnow, replace_months
from calibre.utils.cleantext import clean_ascii_chars
from calibre import browser, preferred_encoding
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import MetaInformation, check_isbn, \
    authors_to_sort_string
from calibre.ebooks.metadata.fetch import MetadataSource
from calibre.utils.config import OptionParser
from calibre.library.comments import sanitize_comments_html


class AmazonFr(MetadataSource):

    name = 'Amazon French'
    description = _('Downloads metadata from amazon.fr')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Sengian'
    version = (1, 0, 0)
    has_html_comments = True

    def fetch(self):
        try:
            self.results = search(self.title, self.book_author, self.publisher,
                                  self.isbn, max_results=10, verbose=self.verbose, lang='fr')
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

class AmazonEs(MetadataSource):

    name = 'Amazon Spanish'
    description = _('Downloads metadata from amazon.com in spanish')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Sengian'
    version = (1, 0, 0)
    has_html_comments = True

    def fetch(self):
        try:
            self.results = search(self.title, self.book_author, self.publisher,
                                  self.isbn, max_results=10, verbose=self.verbose, lang='es')
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

class AmazonEn(MetadataSource):

    name = 'Amazon English'
    description = _('Downloads metadata from amazon.com in english')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Sengian'
    version = (1, 0, 0)
    has_html_comments = True

    def fetch(self):
        try:
            self.results = search(self.title, self.book_author, self.publisher,
                                  self.isbn, max_results=10, verbose=self.verbose, lang='en')
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

class AmazonDe(MetadataSource):

    name = 'Amazon German'
    description = _('Downloads metadata from amazon.de')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Sengian'
    version = (1, 0, 0)
    has_html_comments = True

    def fetch(self):
        try:
            self.results = search(self.title, self.book_author, self.publisher,
                                  self.isbn, max_results=10, verbose=self.verbose, lang='de')
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

class Amazon(MetadataSource):

    name = 'Amazon'
    description = _('Downloads metadata from amazon.com')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Kovid Goyal & Sengian'
    version = (1, 1, 0)
    has_html_comments = True

    def fetch(self):
        # if not self.site_customization:
            # return
        try:
            self.results = search(self.title, self.book_author, self.publisher,
                                  self.isbn, max_results=10, verbose=self.verbose, lang='all')
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

    # @property
    # def string_customization_help(self):
        # return _('You can select here the language for metadata search with amazon.com')


def report(verbose):
    if verbose:
        traceback.print_exc()

class AmazonError(Exception):
    pass

class BrowserThread(Thread):

    def __init__(self, url, verbose=False, timeout=10., ex=Exception, name='Meta'):
        self.url = url
        self.ex = ex
        self.plugname = name
        self.verbose = verbose
        self.timeout = timeout
        self.result = None
        self.br = browser()
        Thread.__init__(self)

    def get_result(self):
        return self.result, self.br

    def run(self):
        try:
            raw = self.br.open_novisit(self.url, timeout=self.timeout).read()
        except Exception, e:
            report(self.verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                self.result = None
            if isinstance(getattr(e, 'args', [None])[0], socket.timeout):
                raise self.ex(_('%s timed out. Try again later.') % self.plugname)
            raise self.ex(_('%s encountered an error.') % self.plugname)
        if '<title>404 - ' in raw:
            report(self.verbose)
            self.result = None
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            self.result = soupparser.fromstring(raw)
        except:
            try:
                #remove ASCII invalid chars
                self.result = soupparser.fromstring(clean_ascii_chars(raw))
            except:
                self.result = None


class Query(object):

    BASE_URL_ALL = 'http://www.amazon.com'
    BASE_URL_FR = 'http://www.amazon.fr'
    BASE_URL_DE = 'http://www.amazon.de'

    def __init__(self, title=None, author=None, publisher=None, isbn=None, keywords=None,
        max_results=20, rlang='all'):
        assert not(title is None and author is None and publisher is None \
            and isbn is None and keywords is None)
        assert (max_results < 21)

        self.max_results = int(max_results)
        self.renbres = re.compile(u'\s*(\d+)\s*')

        q = {   'search-alias' : 'stripbooks' ,
                'unfiltered' : '1',
                'field-keywords' : '',
                'field-author' : '',
                'field-title' : '',
                'field-isbn' : '',
                'field-publisher' : ''
                #get to amazon detailed search page to get all options
                # 'node' : '',
                # 'field-binding' : '',
                #before, during, after
                # 'field-dateop' : '',
                #month as number
                # 'field-datemod' : '',
                # 'field-dateyear' : '',
                #french only
                # 'field-collection' : '',
                #many options available
            }

        if rlang =='all':
            q['sort'] = 'relevanceexprank'
            self.urldata = self.BASE_URL_ALL
        elif rlang =='es':
            q['sort'] = 'relevanceexprank'
            q['field-language'] = 'Spanish'
            self.urldata = self.BASE_URL_ALL
        elif rlang =='en':
            q['sort'] = 'relevanceexprank'
            q['field-language'] = 'English'
            self.urldata = self.BASE_URL_ALL
        elif rlang =='fr':
            q['sort'] = 'relevancerank'
            self.urldata = self.BASE_URL_FR
        elif rlang =='de':
            q['sort'] = 'relevancerank'
            self.urldata = self.BASE_URL_DE
        self.baseurl = self.urldata

        if isbn is not None:
            q['field-isbn'] = isbn.replace('-', '')
        else:
            if title is not None:
                q['field-title'] = title
            if author is not None:
                q['field-author'] = author
            if publisher is not None:
                q['field-publisher'] = publisher
            if keywords is not None:
                q['field-keywords'] = keywords

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        self.urldata += '/gp/search/ref=sr_adv_b/?' + urlencode(q)

    def __call__(self, browser, verbose, timeout = 5.):
        if verbose:
            print _('Query: %s') % self.urldata

        try:
            raw = browser.open_novisit(self.urldata, timeout=timeout).read()
        except Exception, e:
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return None, self.urldata
            if isinstance(getattr(e, 'args', [None])[0], socket.timeout):
                raise AmazonError(_('Amazon timed out. Try again later.'))
            raise AmazonError(_('Amazon encountered an error.'))
        if '<title>404 - ' in raw:
            return None, self.urldata
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]

        try:
            feed = soupparser.fromstring(raw)
        except:
            try:
                #remove ASCII invalid chars
                return soupparser.fromstring(clean_ascii_chars(raw))
            except:
                return None, self.urldata

        #nb of page
        try:
            nbresults = self.renbres.findall(feed.xpath("//*[@class='resultCount']")[0].text)
        except:
            return None, self.urldata

        pages =[feed]
        if len(nbresults) > 1:
            nbpagetoquery = int(ceil(float(min(int(nbresults[2]), self.max_results))/ int(nbresults[1])))
            for i in xrange(2, nbpagetoquery + 1):
                try:
                    urldata = self.urldata + '&page=' + str(i)
                    raw = browser.open_novisit(urldata, timeout=timeout).read()
                except Exception, e:
                    continue
                if '<title>404 - ' in raw:
                    continue
                raw = xml_to_unicode(raw, strip_encoding_pats=True,
                        resolve_entities=True)[0]
                try:
                    feed = soupparser.fromstring(raw)
                except:
                    try:
                        #remove ASCII invalid chars
                        return soupparser.fromstring(clean_ascii_chars(raw))
                    except:
                        continue
                pages.append(feed)

        results = []
        for x in pages:
            results.extend([i.getparent().get('href') \
                for i in x.xpath("//a/span[@class='srTitle']")])
        return results[:self.max_results], self.baseurl

class ResultList(list):

    def __init__(self, baseurl, lang = 'all'):
        self.baseurl = baseurl
        self.lang = lang
        self.repub = re.compile(u'\((.*)\)')
        self.rerat = re.compile(u'([0-9.]+)')
        self.reattr = re.compile(r'<([a-zA-Z0-9]+)\s[^>]+>')
        self.reoutp = re.compile(r'(?s)<em>--This text ref.*?</em>')
        self.recom = re.compile(r'(?s)<!--.*?-->')
        self.republi = re.compile(u'(Editeur|Publisher|Verlag)', re.I)
        self.reisbn = re.compile(u'(ISBN-10|ISBN-10|ASIN)', re.I)
        self.relang = re.compile(u'(Language|Langue|Sprache)', re.I)
        self.reratelt = re.compile(u'(Average\s*Customer\s*Review|Moyenne\s*des\s*commentaires\s*client|Durchschnittliche\s*Kundenbewertung)', re.I)
        self.reprod = re.compile(u'(Product\s*Details|D.tails\s*sur\s*le\s*produit|Produktinformation)', re.I)

    def strip_tags_etree(self, etreeobj, invalid_tags):
        for (itag, rmv) in invalid_tags.iteritems():
            if rmv:
                for elts in etreeobj.getiterator(itag):
                    elts.drop_tree()
            else:
                for elts in etreeobj.getiterator(itag):
                    elts.drop_tag()

    def clean_entry(self, entry, invalid_tags = {'script': True},
                invalid_id = (), invalid_class=()):
        #invalid_tags: remove tag and keep content if False else remove
        #remove tags
        if invalid_tags:
            self.strip_tags_etree(entry, invalid_tags)
        #remove id
        if invalid_id:
            for eltid in invalid_id:
                elt = entry.get_element_by_id(eltid)
                if elt is not None:
                    elt.drop_tree()
        #remove class
        if invalid_class:
            for eltclass in invalid_class:
                elts = entry.find_class(eltclass)
                if elts is not None:
                    for elt in elts:
                        elt.drop_tree()

    def get_title(self, entry):
        title = entry.get_element_by_id('btAsinTitle')
        if title is not None:
            title = title.text
        return unicode(title.replace('\n', '').strip())

    def get_authors(self, entry):
        author = entry.get_element_by_id('btAsinTitle')
        while author.getparent().tag != 'div':
            author = author.getparent()
        author = author.getparent()
        authortext = []
        for x in author.getiterator('a'):
            authortext.append(unicode(x.text_content().strip()))
        return authortext

    def get_description(self, entry, verbose):
        try:
            description = entry.get_element_by_id("productDescription").find("div[@class='content']")
            inv_class = ('seeAll', 'emptyClear')
            inv_tags ={'img': True, 'a': False}
            self.clean_entry(description, invalid_tags=inv_tags, invalid_class=inv_class)
            description = tostring(description, method='html', encoding=unicode).strip()
            # remove all attributes from tags
            description = self.reattr.sub(r'<\1>', description)
            # Remove the notice about text referring to out of print editions
            description = self.reoutp.sub('', description)
            # Remove comments
            description = self.recom.sub('', description)
            return unicode(sanitize_comments_html(description))
        except:
            report(verbose)
            return None

    def get_tags(self, entry, verbose):
        try:
            tags = entry.get_element_by_id('tagContentHolder')
            testptag = tags.find_class('see-all')
            if testptag:
                for x in testptag:
                    alink = x.xpath('descendant-or-self::a')
                    if alink:
                        if alink[0].get('class') == 'tgJsActive':
                            continue
                        link = self.baseurl + alink[0].get('href')
                        entry = self.get_individual_metadata(link, verbose)
                        tags = entry.get_element_by_id('tagContentHolder')
                        break
            tags = [a.text for a in tags.getiterator('a') if a.get('rel') == 'tag']
        except:
            report(verbose)
            tags = []
        return tags

    def get_book_info(self, entry, mi, verbose):
        try:
            entry = entry.get_element_by_id('SalesRank').getparent()
        except:
            try:
                for z in entry.getiterator('h2'):
                    if self.reprod.search(z.text_content()):
                        entry = z.getparent().find("div[@class='content']/ul")
                        break
            except:
                report(verbose)
                return mi
        elts = entry.findall('li')
        #pub & date
        elt = filter(lambda x: self.republi.search(x.find('b').text), elts)
        if elt:
            pub = elt[0].find('b').tail
            mi.publisher = unicode(self.repub.sub('', pub).strip())
            d = self.repub.search(pub)
            if d is not None:
                d = d.group(1)
                try:
                    default = utcnow().replace(day=15)
                    if self.lang != 'all':
                        d = replace_months(d, self.lang)
                    d = parse_date(d, assume_utc=True, default=default)
                    mi.pubdate = d
                except:
                    report(verbose)
        #ISBN
        elt = filter(lambda x: self.reisbn.search(x.find('b').text), elts)
        if elt:
            isbn = elt[0].find('b').tail.replace('-', '').strip()
            if check_isbn(isbn):
                    mi.isbn = unicode(isbn)
            elif len(elt) > 1:
                isbn = elt[1].find('b').tail.replace('-', '').strip()
                if check_isbn(isbn):
                    mi.isbn = unicode(isbn)
        #Langue
        elt = filter(lambda x: self.relang.search(x.find('b').text), elts)
        if elt:
            langue = elt[0].find('b').tail.strip()
            if langue:
                mi.language = unicode(langue)
        #ratings
        elt = filter(lambda x: self.reratelt.search(x.find('b').text), elts)
        if elt:
            ratings = elt[0].find_class('swSprite')
            if ratings:
                ratings = self.rerat.findall(ratings[0].get('title'))
                if len(ratings) == 2:
                    mi.rating = float(ratings[0])/float(ratings[1]) * 5
        return mi

    def fill_MI(self, entry, br, verbose):
        try:
            title = self.get_title(entry)
            authors = self.get_authors(entry)
        except Exception, e:
            if verbose:
                print _('Failed to get all details for an entry')
                print e
                print _('URL who failed: %s') % x
                report(verbose)
            return None
        mi = MetaInformation(title, authors)
        mi.author_sort = authors_to_sort_string(authors)
        try:
            mi.comments = self.get_description(entry, verbose)
            mi = self.get_book_info(entry, mi, verbose)
            mi.tags = self.get_tags(entry, br, verbose)
        except:
            pass
        return mi

    def get_individual_metadata(self, url, br, verbose):
        try:
            raw = br.open_novisit(url).read()
        except Exception, e:
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return None
            if isinstance(getattr(e, 'args', [None])[0], socket.timeout):
                raise AmazonError(_('Amazon timed out. Try again later.'))
            raise AmazonError(_('Amazon encountered an error.'))
        if '<title>404 - ' in raw:
            report(verbose)
            return None
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            return soupparser.fromstring(raw)
        except:
            try:
                #remove ASCII invalid chars
                return soupparser.fromstring(clean_ascii_chars(raw))
            except:
                report(verbose)
                return None

    def producer(self, q, data, verbose=False):
        for x in data:
            thread = BrowserThread(x, verbose=verbose, ex=AmazonError,
                name='Amazon')
            thread.start()
            q.put(thread, True)

    def consumer(self, q, total_entries, verbose=False):
        while len(self) < total_entries:
            thread = q.get(True)
            thread.join()
            mi, br = thread.get_result()
            if mi is None:
                self.append(None)
            else:
                self.append(self.fill_MI(mi, br, verbose))

    def populate(self, entries, verbose=False, brcall=5):
        #multiple entries
        q = Queue(brcall)
        prod_thread = Thread(target=self.producer, args=(q, entries, verbose))
        cons_thread = Thread(target=self.consumer, args=(q, len(entries), verbose))
        prod_thread.start()
        cons_thread.start()
        prod_thread.join()
        cons_thread.join()


def search(title=None, author=None, publisher=None, isbn=None,
           max_results=5, verbose=False, keywords=None, lang='all'):
    br = browser()
    entries, baseurl = Query(title=title, author=author, isbn=isbn, publisher=publisher,
        keywords=keywords, max_results=max_results,rlang=lang)(br, verbose)

    if entries is None or len(entries) == 0:
        return

    #List of entry
    ans = ResultList(baseurl, lang)
    ans.populate(entries, verbose)
    return [x for x in ans if x is not None]

def option_parser():
    parser = OptionParser(textwrap.dedent(\
    _('''\
        %prog [options]

        Fetch book metadata from Amazon. You must specify one of title, author,
        ISBN, publisher or keywords. Will fetch a maximum of 10 matches,
        so you should make your query as specific as possible.
        You can chose the language for metadata retrieval:
        All & english & french & german & spanish
    '''
    )))
    parser.add_option('-t', '--title', help='Book title')
    parser.add_option('-a', '--author', help='Book author(s)')
    parser.add_option('-p', '--publisher', help='Book publisher')
    parser.add_option('-i', '--isbn', help='Book ISBN')
    parser.add_option('-k', '--keywords', help='Keywords')
    parser.add_option('-m', '--max-results', default=10,
                      help='Maximum number of results to fetch')
    parser.add_option('-l', '--lang', default='all',
                      help='Chosen language for metadata search (all, en, fr, es, de)')
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help='Be more verbose about errors')
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    try:
        results = search(opts.title, opts.author, isbn=opts.isbn, publisher=opts.publisher,
            keywords=opts.keywords, verbose=opts.verbose, max_results=opts.max_results,
                lang=opts.lang)
    except AssertionError:
        report(True)
        parser.print_help()
        return 1
    if results is None or len(results) == 0:
        print _('No result found for this search!')
        return 0
    for result in results:
        print unicode(result).encode(preferred_encoding, 'replace')
        print

if __name__ == '__main__':
    sys.exit(main())
    # import cProfile
    # sys.exit(cProfile.run("import calibre.ebooks.metadata.amazonfr; calibre.ebooks.metadata.amazonfr.main()"))
    # sys.exit(cProfile.run("import calibre.ebooks.metadata.amazonfr; calibre.ebooks.metadata.amazonfr.main()", "profile_tmp"))

# calibre-debug -e "H:\Mes eBooks\Developpement\calibre\src\calibre\ebooks\metadata\amazonfr.py" -m 5 -a gore -v>data.html