from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'
__docformat__ = 'restructuredtext en'

import sys, re
from threading import Thread
from Queue import Queue
from urllib import urlencode

from lxml.html import soupparser, tostring

from calibre import browser, preferred_encoding
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import MetaInformation, check_isbn, \
    authors_to_sort_string
from calibre.ebooks.metadata.fetch import MetadataSource
from calibre.library.comments import sanitize_comments_html
from calibre.utils.config import OptionParser
from calibre.utils.cleantext import clean_ascii_chars, unescape
from calibre.utils.date import parse_date, utcnow


class Fictionwise(MetadataSource):

    author = 'Sengian'
    name = 'Fictionwise'
    description = _('Downloads metadata from Fictionwise')
    has_html_comments = True

    def fetch(self):
        try:
            self.results = search(self.title, self.book_author, self.publisher,
                self.isbn, max_results=10, verbose=self.verbose)
        except Exception, e:
            import traceback
            self.exception = e
            self.tb = traceback.format_exc()


class FictionwiseError(Exception):
    pass

class ThreadwithResults(Thread):
    def __init__(self, func, *args, **kargs):
        self.func = func
        self.args = args
        self.kargs = kargs
        self.result = None
        Thread.__init__(self)

    def get_result(self):
        return self.result

    def run(self):
        self.result = self.func(*self.args, **self.kargs)

def report(verbose):
    if verbose:
        import traceback
        traceback.print_exc()


class Query(object):

    BASE_URL = 'http://www.fictionwise.com/servlet/mw'

    def __init__(self, title=None, author=None, publisher=None, keywords=None, max_results=20):
        assert not(title is None and author is None and publisher is None and keywords is None)
        assert (max_results < 21)
        
        if title == _('Unknown'):
            title=None
        if author == _('Unknown'):
            author=None
        self.max_results = int(max_results)
        
        q = {   'template' : 'searchresults_adv.htm' ,
                'searchtitle' : '',
                'searchauthor' : '',
                'searchpublisher' : '',
                'searchkeyword' : '',
                #possibilities startoflast, fullname, lastfirst
                'searchauthortype' : 'startoflast',
                'searchcategory' : '',
                'searchcategory2' : '',
                'searchprice_s' : '0',
                'searchprice_e' : 'ANY',
                'searchformat' : '',
                'searchgeo' : 'US',
                'searchfwdatetype' : '',
                #maybe use dates fields if needed?
                #'sortorder' : 'DESC',
                #many options available: b.SortTitle, a.SortName,
                #b.DateFirstPublished, b.FWPublishDate
                'sortby' : 'b.SortTitle'
            }
        
        if title is not None:
            q['searchtitle'] = title
        if author is not None:
            q['searchauthor'] = author
        if publisher is not None:
            q['searchpublisher'] = publisher
        if keywords is not None:
            q['searchkeyword'] = keywords

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        self.urldata = urlencode(q)

    def __call__(self, browser, verbose, timeout = 5.):
        if verbose:
            print _('Query: %s POST: %s') % (self.BASE_URL, self.urldata)

        try:
            raw = browser.open_novisit(self.BASE_URL, self.urldata, timeout=timeout).read()
        except Exception, e:
            import socket
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return None
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                raise FictionwiseError(_('Fictionwise timed out. Try again later.'))
            raise FictionwiseError(_('Fictionwise encountered an error.'))
        if '<title>404 - ' in raw:
            return None
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            feed = soupparser.fromstring(raw)
        except:
            try:
                #remove ASCII invalid chars
                feed = soupparser.fromstring(clean_ascii_chars(raw))
            except:
                return None

        # get list of results as links
        results = feed.xpath("//table[3]/tr/td[2]/table/tr/td/p/table[2]/tr[@valign]")
        results = results[:self.max_results]
        results = [i.xpath('descendant-or-self::a')[0].get('href') for i in results]
        #return feed if no links ie normally a single book or nothing
        if not results:
            return [feed], False
        return results, True

class ResultList(list):

    BASE_URL = 'http://www.fictionwise.com'
    COLOR_VALUES = {'BLUE': 4, 'GREEN': 3, 'YELLOW': 2, 'RED': 1, 'NA': 0}

    def __init__(self, islink):
        self.islink = islink
        self.thread = []
        self.retitle = re.compile(r'\[[^\[\]]+\]')
        self.rechkauth = re.compile(r'.*book\s*by', re.I)
        self.redesc = re.compile(r'book\s*description\s*:\s*(<br[^>]+>)*(?P<desc>.*)<br[^>]*>.{,15}publisher\s*:', re.I)
        self.repub = re.compile(r'.*publisher\s*:\s*', re.I)
        self.redate = re.compile(r'.*release\s*date\s*:\s*', re.I)
        self.retag = re.compile(r'.*book\s*category\s*:\s*', re.I)
        self.resplitbr = re.compile(r'<br[^>]*>', re.I)
        self.recomment = re.compile(r'(?s)<!--.*?-->')
        self.reimg = re.compile(r'<img[^>]*>', re.I)
        self.resanitize = re.compile(r'\[HTML_REMOVED\]\s*', re.I)
        self.renbcom = re.compile('(?P<nbcom>\d+)\s*Reader Ratings:')
        self.recolor = re.compile('(?P<ncolor>[^/]+).gif')
        self.resplitbrdiv = re.compile(r'(<br[^>]+>|</?div[^>]*>)', re.I)
        self.reisbn = re.compile(r'.*ISBN\s*:\s*', re.I)

    def strip_tags_etree(self, etreeobj, invalid_tags):
        for (itag, rmv) in invalid_tags.iteritems():
            if rmv:
                for elts in etreeobj.getiterator(itag):
                    elts.drop_tree()
            else:
                for elts in etreeobj.getiterator(itag):
                    elts.drop_tag()

    def clean_entry(self, entry, invalid_tags = {'script': True},
                invalid_id = (), invalid_class=(), invalid_xpath = ()):
        #invalid_tags: remove tag and keep content if False else remove
        #remove tags
        if invalid_tags:
            self.strip_tags_etree(entry, invalid_tags)
        #remove xpath
        if invalid_xpath:
            for eltid in invalid_xpath:
                elt = entry.xpath(eltid)
                for el in elt:
                    el.drop_tree()
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

    def output_entry(self, entry, prettyout = True, rmhtmlchar=True):
        out = tostring(entry, pretty_print=prettyout)
        #remove html chars
        if rmhtmlchar:
            out = unescape(out, rm=True)
        # Remove \n\t\r.
        reclean = re.compile('(\n+|\t+|\r+)')
        return reclean.sub('', out)

    def get_title(self, entry):
        title = entry.findtext('./')
        return self.retitle.sub('', title).strip()

    def get_authors(self, entry):
        authortext = entry.find('./br').tail
        if not self.rechkauth.search(authortext):
            return []
        authortext = self.rechkauth.sub('', authortext)
        return [a.strip() for a in authortext.split('&')]

    def get_rating(self, entrytable, verbose):
        nbcomment = tostring(entrytable.getprevious())
        try:
            nbcomment = self.renbcom.search(nbcomment).group("nbcom")
        except:
            report(verbose)
            return None
        hval = dict((self.COLOR_VALUES[self.recolor.search(image.get('src', default='NA.gif')).group("ncolor")],
                    float(image.get('height', default=0))) \
                        for image in entrytable.getiterator('img'))
        #ratings as x/5
        return float(1.25*sum(k*v for (k, v) in hval.iteritems())/sum(hval.itervalues()))

    def get_description(self, entry):
        description = self.output_entry(entry.xpath('./p')[1],rmhtmlchar=False)
        description = self.redesc.search(description)
        if not description or not description.group("desc"):
            return None
        #remove invalid tags
        description = self.reimg.sub('', description.group("desc"))
        description = self.recomment.sub('', description)
        description = self.resanitize.sub('', sanitize_comments_html(description))
        return _('SUMMARY:\n %s') % re.sub(r'\n\s+</p>','\n</p>', description)

    def get_publisher(self, entry):
        publisher = self.output_entry(entry.xpath('./p')[1])
        publisher = filter(lambda x: self.repub.search(x) is not None,
            self.resplitbr.split(publisher))
        if not len(publisher):
            return None
        publisher = self.repub.sub('', publisher[0])
        return publisher.split(',')[0].strip()

    def get_tags(self, entry):
        tag = self.output_entry(entry.xpath('./p')[1])
        tag = filter(lambda x: self.retag.search(x) is not None,
            self.resplitbr.split(tag))
        if not len(tag):
            return []
        return map(lambda x: x.strip(), self.retag.sub('', tag[0]).split('/'))

    def get_date(self, entry, verbose):
        date = self.output_entry(entry.xpath('./p')[1])
        date = filter(lambda x: self.redate.search(x) is not None,
            self.resplitbr.split(date))
        if not len(date):
            return None
        try:
            d = self.redate.sub('', date[0])
            if d:
                default = utcnow().replace(day=15)
                d = parse_date(d, assume_utc=True, default=default)
            else:
                d = None
        except:
            report(verbose)
            d = None
        return d

    def get_ISBN(self, entry):
        isbns = self.output_entry(entry.xpath('./p')[2])
        isbns = filter(lambda x: self.reisbn.search(x) is not None,
            self.resplitbrdiv.split(isbns))
        if not len(isbns):
            return None
        isbns = [self.reisbn.sub('', x) for x in isbns if check_isbn(self.reisbn.sub('', x))]
        return sorted(isbns, cmp=lambda x,y:cmp(len(x), len(y)))[-1]

    def fill_MI(self, data, verbose):
        inv_tags ={'script': True, 'a': False, 'font': False, 'strong': False, 'b': False,
            'ul': False, 'span': False}
        inv_xpath =('./table',)
        try:
            entry = data.xpath("//table[3]/tr/td[2]/table[1]/tr/td/font/table/tr/td")[0]
            self.clean_entry(entry, invalid_tags=inv_tags, invalid_xpath=inv_xpath)
            title = self.get_title(entry)
            authors = self.get_authors(entry)
        except Exception, e:
            if verbose:
                print _('Failed to get all details for an entry')
                print e
            return None
        mi = MetaInformation(title, authors)
        mi.author_sort = authors_to_sort_string(authors)
        try:
            ratings = entry.xpath("./p/table")
            if len(ratings) >= 2:
                mi.rating = self.get_rating(ratings[1], verbose)
            mi.comments = self.get_description(entry)
            mi.publisher = self.get_publisher(entry)
            mi.tags = self.get_tags(entry)
            mi.pubdate = self.get_date(entry, verbose)
            mi.isbn = self.get_ISBN(entry)
        except:
            pass
        return mi

    def get_individual_metadata(self, url, br, verbose):
        try:
            raw = br.open_novisit(url).read()
        except Exception, e:
            import socket
            report(verbose)
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return None
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                raise FictionwiseError(_('Fictionwise timed out. Try again later.'))
            raise FictionwiseError(_('Fictionwise encountered an error.'))
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

    def fetchdatathread(self, qbr, qsync, nb, url, verbose):
        try:
            browser = qbr.get(True)
            entry = self.get_individual_metadata(url, browser, verbose)
        except:
            report(verbose)
            entry = None
        finally:
            qbr.put(browser, True)
            qsync.put(nb, True)
            return entry

    def producer(self, sync, urls, br, verbose=False):
        for i in xrange(len(urls)):
            thread = ThreadwithResults(self.fetchdatathread, br, sync,
                                i, self.BASE_URL+urls[i], verbose)
            thread.start()
            self.thread.append(thread)

    def consumer(self, sync, total_entries, verbose=False):
        res=[None]*total_entries
        i=0
        while i < total_entries:
            nb = int(sync.get(True))
            self.thread[nb].join()
            entry = self.thread[nb].get_result()
            i+=1
            if entry is not None:
                res[nb] = self.fill_MI(entry, verbose)
        return res

    def populate(self, entries, br, verbose=False, brcall=3):
        if not self.islink:
            #single entry
            self.append(self.fill_MI(entries[0], verbose))
        else:
            #multiple entries
            pbr = Queue(brcall)
            sync = Queue(1)
            for i in xrange(brcall-1):
                pbr.put(browser(), True)
            pbr.put(br, True)
            
            prod_thread = Thread(target=self.producer, args=(sync, entries, pbr, verbose))
            cons_thread = ThreadwithResults(self.consumer, sync, len(entries), verbose)
            prod_thread.start()
            cons_thread.start()
            prod_thread.join()
            cons_thread.join()
            self.extend(cons_thread.get_result())


def search(title=None, author=None, publisher=None, isbn=None,
           min_viewability='none', verbose=False, max_results=5,
            keywords=None):
    br = browser()
    islink = False
    entries, islink = Query(title=title, author=author, publisher=publisher,
        keywords=keywords, max_results=max_results)(br, verbose, timeout = 15.)

    if entries is None or len(entries) == 0:
        return None

    #List of entry
    ans = ResultList(islink)
    ans.populate(entries, br, verbose)
    return [x for x in ans if x is not None]


def option_parser():
    import textwrap
    parser = OptionParser(textwrap.dedent(\
    _('''\
        %prog [options]

        Fetch book metadata from Fictionwise. You must specify one of title, author,
        or keywords. No ISBN specification possible. Will fetch a maximum of 20 matches,
        so you should make your query as specific as possible.
    ''')
    ))
    parser.add_option('-t', '--title', help=_('Book title'))
    parser.add_option('-a', '--author', help=_('Book author(s)'))
    parser.add_option('-p', '--publisher', help=_('Book publisher'))
    parser.add_option('-k', '--keywords', help=_('Keywords'))
    parser.add_option('-m', '--max-results', default=20,
                      help=_('Maximum number of results to fetch'))
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help=_('Be more verbose about errors'))
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    try:
        results = search(opts.title, opts.author, publisher=opts.publisher,
            keywords=opts.keywords, verbose=opts.verbose, max_results=opts.max_results)
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

# calibre-debug -e "H:\Mes eBooks\Developpement\calibre\src\calibre\ebooks\metadata\fictionwise.py" -m 5 -a gore -v>data.html