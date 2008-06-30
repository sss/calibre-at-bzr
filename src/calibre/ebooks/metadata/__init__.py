#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

"""
Provides abstraction for metadata reading.writing from a variety of ebook formats. 
"""
import os, mimetypes, sys
from urllib import unquote, quote
from urlparse import urlparse


from calibre import __version__ as VERSION, relpath
from calibre import OptionParser

def get_parser(extension):
    ''' Return an option parser with the basic metadata options already setup'''
    parser = OptionParser(usage='%prog [options] myfile.'+extension+'\n\nRead and write metadata from an ebook file.')
    parser.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help=_("Set the book title"), default=None)
    parser.add_option("-a", "--authors", action="store", type="string", \
                    dest="authors", help=_("Set the authors"), default=None)
    parser.add_option("-c", "--category", action="store", type="string", \
                    dest="category", help=_("The category this book belongs to. E.g.: History"), default=None)
    parser.add_option('--comment', dest='comment', default=None, action='store',
                      help=_('Set the comment'))
    return parser

class Resource(object):
    '''
    Represents a resource (usually a file on the filesystem or a URL pointing 
    to the web. Such resources are commonly referred to in OPF files.
    
    They have the interface:
    
    :member:`path`
    :member:`mime_type`
    :method:`href`
    
    '''
    
    def __init__(self, href_or_path, basedir=os.getcwd(), is_path=True):
        self._href = None
        self._basedir = None
        self.path = None
        self.fragment = ''
        try:
            self.mime_type = mimetypes.guess_type(href_or_path)[0]
        except:
            self.mime_type = None
        if self.mime_type is None:
            self.mime_type = 'application/octet-stream'
        if is_path:
            path = href_or_path
            if not os.path.isabs(path):
                path = os.path.abspath(os.path.join(path, basedir))
            if isinstance(path, str):
                path = path.decode(sys.getfilesystemencoding())
            self.path = path
        else:
            url = urlparse(href_or_path)
            if url[0] not in ('', 'file'):
                self._href = href_or_path
            else:
                self.path = os.path.abspath(os.path.join(basedir, unquote(url[2]).replace('/', os.sep)))
                self.fragment = unquote(url[-1])
        
    
    def href(self, basedir=None):
        '''
        Return a URL pointing to this resource. If it is a file on the filesystem
        the URL is relative to `basedir`.
        
        `basedir`: If None, the basedir of this resource is used (see :method:`set_basedir`).
        If this resource has no basedir, then the current working directory is used as the basedir.
        '''
        if basedir is None:
            if self._basedir:
                basedir = self._basedir
            else:
                basedir = os.getcwd()
        if self.path is None:
            return self._href
        f = self.fragment.encode('utf-8') if isinstance(self.fragment, unicode) else self.fragment
        frag = '#'+quote(f) if self.fragment else ''
        if self.path == basedir:
            return ''+frag
        try:
            rpath = relpath(self.path, basedir)
        except OSError: # On windows path and basedir could be on different drives
            rpath = self.path
        if isinstance(rpath, unicode):
            rpath = rpath.encode('utf-8')
        return quote(rpath.replace(os.sep, '/'))+frag
    
    def set_basedir(self, path):
        self._basedir = path
        
    def basedir(self):
        return self._basedir
    
    def __repr__(self):
        return 'Resource(%s, %s)'%(repr(self.path), repr(self.href()))
        
        
class ResourceCollection(object):
    
    def __init__(self):
        self._resources = []
        
    def __iter__(self):
        for r in self._resources:
            yield r
            
    def __len__(self):
        return len(self._resources)
    
    def __getitem__(self, index):
        return self._resources[index]
    
    def __bool__(self):
        return len(self._resources) > 0
    
    def __str__(self):
        resources = map(repr, self)
        return '[%s]'%', '.join(resources)
    
    def __repr__(self):
        return str(self)
    
    def append(self, resource):
        if not isinstance(resource, Resource):
            raise ValueError('Can only append objects of type Resource')
        self._resources.append(resource)
        
    def remove(self, resource):
        self._resources.remove(resource)
        
    @staticmethod
    def from_directory_contents(top, topdown=True):
        collection = ResourceCollection()
        for spec in os.walk(top, topdown=topdown):
            path = os.path.abspath(os.path.join(spec[0], spec[1]))
            res = Resource.from_path(path)
            res.set_basedir(top)
            collection.append(res)
        return collection
    
    def set_basedir(self, path):
        for res in self:
            res.set_basedir(path)
        


class MetaInformation(object):
    '''Convenient encapsulation of book metadata'''
    
    @staticmethod
    def copy(mi):
        ans = MetaInformation(mi.title, mi.authors)
        for attr in ('author_sort', 'title_sort', 'comments', 'category',
                     'publisher', 'series', 'series_index', 'rating',
                     'isbn', 'tags', 'cover_data', 'application_id', 'guide',
                     'manifest', 'spine', 'toc', 'cover', 'language'):
            if hasattr(mi, attr):
                setattr(ans, attr, getattr(mi, attr))
        
    
    def __init__(self, title, authors=[_('Unknown')]):
        '''
        @param title: title or "Unknown" or a MetaInformation object
        @param authors: List of strings or []
        '''
        mi = None
        if isinstance(title, MetaInformation):
            mi = title
            title = mi.title
            authors = mi.authors
        self.title = title
        self.author = authors # Needed for backward compatibility
        #: List of strings or []
        self.authors = authors
        #: Sort text for author
        self.author_sort  = None if not mi else mi.author_sort
        self.title_sort   = None if not mi else mi.title_sort
        self.comments     = None if not mi else mi.comments
        self.category     = None if not mi else mi.category
        self.publisher    = None if not mi else mi.publisher
        self.series       = None if not mi else mi.series
        self.series_index = None if not mi else mi.series_index
        self.rating       = None if not mi else mi.rating
        self.isbn         = None if not mi else mi.isbn
        self.tags         = []  if not mi else mi.tags
        self.language     = None if not mi else mi.language # Typically a string describing the language
        #: mi.cover_data = (ext, data)
        self.cover_data   = mi.cover_data if (mi and hasattr(mi, 'cover_data')) else (None, None)
        self.application_id    = mi.application_id  if (mi and hasattr(mi, 'application_id')) else None
        self.manifest = getattr(mi, 'manifest', None) 
        self.toc      = getattr(mi, 'toc', None)
        self.spine    = getattr(mi, 'spine', None)
        self.guide    = getattr(mi, 'guide', None)
        self.cover    = getattr(mi, 'cover', None)
    
    def smart_update(self, mi):
        '''
        Merge the information in C{mi} into self. In case of conflicts, the information
        in C{mi} takes precedence, unless the information in mi is NULL.
        '''
        if mi.title and mi.title.lower() != 'unknown':
            self.title = mi.title
            
        if mi.authors and mi.authors[0].lower() != 'unknown':
            self.authors = mi.authors
            
        for attr in ('author_sort', 'title_sort', 'comments', 'category',
                     'publisher', 'series', 'series_index', 'rating',
                     'isbn', 'application_id', 'manifest', 'spine', 'toc', 
                     'cover', 'language', 'guide'):
            if hasattr(mi, attr):
                val = getattr(mi, attr)
                if val is not None:
                    setattr(self, attr, val)
                    
        self.tags += mi.tags
        self.tags = list(set(self.tags))
        
        if getattr(mi, 'cover_data', None) and mi.cover_data[0] is not None:
            self.cover_data = mi.cover_data
            
            
    def __str__(self):
        ans = u''
        ans += u'Title    : ' + unicode(self.title) + u'\n'
        if self.authors:
            ans += u'Author   : ' + (', '.join(self.authors) if self.authors is not None else u'None')
            ans += ((' (' + self.author_sort + ')') if self.author_sort else '') + u'\n'
        if self.publisher:
            ans += u'Publisher: '+ unicode(self.publisher) + u'\n'
        if self.category: 
            ans += u'Category : ' + unicode(self.category) + u'\n'
        if self.comments:
            ans += u'Comments : ' + unicode(self.comments) + u'\n'
        if self.isbn:
            ans += u'ISBN     : '     + unicode(self.isbn) + u'\n'
        if self.tags:
            ans += u'Tags     : ' +unicode(self.tags) + '\n'
        if self.series:
            ans += u'Series   : '+unicode(self.series) + ' #%d\n'%self.series_index  
        if self.language:
            ans += u'Language : '     + unicode(self.language) + u'\n'
        return ans.strip()
    
    def __nonzero__(self):
        return bool(self.title or self.author or self.comments or self.category)
