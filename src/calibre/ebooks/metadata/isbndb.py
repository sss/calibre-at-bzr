__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Interface to isbndb.com. My key HLLXQX2A.
'''

import sys, re
from urllib import quote

from calibre.utils.config import OptionParser
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup
from calibre import browser

BASE_URL = 'http://isbndb.com/api/books.xml?access_key=%(key)s&page_number=1&results=subjects,authors,texts&'

class ISBNDBError(Exception):
    pass

def fetch_metadata(url, max=100, timeout=5.):
    books = []
    page_number = 1
    total_results = sys.maxint
    br = browser()
    while len(books) < total_results and max > 0:
        try:
            raw = br.open(url, timeout=timeout).read()
        except Exception, err:
            raise ISBNDBError('Could not fetch ISBNDB metadata. Error: '+str(err))
        soup = BeautifulStoneSoup(raw,
                convertEntities=BeautifulStoneSoup.XML_ENTITIES)
        book_list = soup.find('booklist')
        if book_list is None:
            errmsg = soup.find('errormessage').string
            raise ISBNDBError('Error fetching metadata: '+errmsg)
        total_results = int(book_list['total_results'])
        np = '&page_number=%s&'%(page_number+1)
        url = re.sub(r'\&page_number=\d+\&', np, url)
        books.extend(book_list.findAll('bookdata'))
        max -= 1
    return books


class ISBNDBMetadata(MetaInformation):

    def __init__(self, book):
        MetaInformation.__init__(self, None, [])

        self.isbn = book.get('isbn13', book.get('isbn'))
        self.title = book.find('titlelong').string
        if not self.title:
            self.title = book.find('title').string
        self.title = unicode(self.title).strip()
        au = unicode(book.find('authorstext').string).strip()
        temp = au.split(',')
        self.authors = []
        for au in temp:
            if not au: continue
            self.authors.extend([a.strip() for a in au.split('&amp;')])

        try:
            self.author_sort = book.find('authors').find('person').string
            if self.authors and self.author_sort == self.authors[0]:
                self.author_sort = None
        except:
            pass
        self.publisher = book.find('publishertext').string

        summ = book.find('summary')
        if summ and hasattr(summ, 'string') and summ.string:
            self.comments = 'SUMMARY:\n'+summ.string


def build_isbn(base_url, opts):
    return base_url + 'index1=isbn&value1='+opts.isbn

def build_combined(base_url, opts):
    query = ''
    for e in (opts.title, opts.author, opts.publisher):
        if e is not None:
            query += ' ' + e
    query = query.strip()
    if len(query) == 0:
        raise ISBNDBError('You must specify at least one of --author, --title or --publisher')

    query = re.sub(r'\s+', '+', query)
    if isinstance(query, unicode):
        query = query.encode('utf-8')
    return base_url+'index1=combined&value1='+quote(query, '+')


def option_parser():
    parser = OptionParser(usage=\
_('''
%prog [options] key

Fetch metadata for books from isndb.com. You can specify either the
books ISBN ID or its title and author. If you specify the title and author,
then more than one book may be returned.

key is the account key you generate after signing up for a free account from isbndb.com.

'''))
    parser.add_option('-i', '--isbn', default=None, dest='isbn',
                      help=_('The ISBN ID of the book you want metadata for.'))
    parser.add_option('-a', '--author', dest='author',
                      default=None, help=_('The author whose book to search for.'))
    parser.add_option('-t', '--title', dest='title',
                      default=None, help=_('The title of the book to search for.'))
    parser.add_option('-p', '--publisher', default=None, dest='publisher',
                      help=_('The publisher of the book to search for.'))
    parser.add_option('-v', '--verbose', default=False,
                      action='store_true', help=_('Verbose processing'))

    return parser


def create_books(opts, args, timeout=5.):
    base_url = BASE_URL%dict(key=args[1])
    if opts.isbn is not None:
        url = build_isbn(base_url, opts)
    else:
        url = build_combined(base_url, opts)

    if opts.verbose:
        print ('ISBNDB query: '+url)

    return [ISBNDBMetadata(book) for book in fetch_metadata(url, timeout=timeout)]

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print ('You must supply the isbndb.com key')
        return 1

    for book in create_books(opts, args):
        print unicode(book).encode('utf-8')

    return 0

if __name__ == '__main__':
    sys.exit(main())
