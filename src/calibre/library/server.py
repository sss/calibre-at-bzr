#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
HTTP server for remote access to the calibre database.
'''

import sys, textwrap, cStringIO, mimetypes, operator, os, re, logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from threading import Thread

import cherrypy
from PIL import Image

from calibre.constants import __version__, __appname__
from calibre.utils.genshi.template import MarkupTemplate
from calibre import fit_image
from calibre.resources import jquery, server_resources, build_time
from calibre.library import server_config as config
from calibre.library.database2 import LibraryDatabase2, FIELD_MAP
from calibre.utils.config import config_dir

build_time = datetime.strptime(build_time, '%d %m %Y %H%M%S')
server_resources['jquery.js'] = jquery

def expose(func):
    
    def do(self, *args, **kwargs):
        dict.update(cherrypy.response.headers, {'Server':self.server_name})
        return func(self, *args, **kwargs)
    
    return cherrypy.expose(do)

log_access_file = os.path.join(config_dir, 'server_access_log.txt')
log_error_file = os.path.join(config_dir, 'server_error_log.txt')
    

class LibraryServer(object):
    
    server_name = __appname__ + '/' + __version__

    BOOK = textwrap.dedent('''\
        <book xmlns:py="http://genshi.edgewall.org/" 
            id="${r[0]}" 
            title="${r[1]}"
            sort="${r[11]}"
            author_sort="${r[12]}"
            authors="${authors}" 
            rating="${r[4]}"
            timestamp="${r[5].strftime('%Y/%m/%d %H:%M:%S')}" 
            size="${r[6]}" 
            isbn="${r[14] if r[14] else ''}"
            formats="${r[13] if r[13] else ''}"
            series = "${r[9] if r[9] else ''}"
            series_index="${r[10]}"
            tags="${r[7] if r[7] else ''}"
            publisher="${r[3] if r[3] else ''}">${r[8] if r[8] else ''}
            </book>
        ''')
    
    LIBRARY = MarkupTemplate(textwrap.dedent('''\
    <?xml version="1.0" encoding="utf-8"?>
    <library xmlns:py="http://genshi.edgewall.org/" start="$start" num="${len(books)}" total="$total" updated="${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}">
    <py:for each="book in books">
        ${Markup(book)}
    </py:for>
    </library>
    '''))
    
    STANZA_ENTRY=MarkupTemplate(textwrap.dedent('''\
    <entry xmlns:py="http://genshi.edgewall.org/">
        <title>${record['title']}</title>
        <id>urn:calibre:${record['id']}</id>
        <author><name>${authors}</name></author>
        <updated>${record['timestamp'].strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
        <link type="application/epub+zip" href="http://${server}:${port}/get/epub/${record['id']}" />
        <link rel="x-stanza-cover-image" type="image/jpeg" href="http://${server}:${port}/get/cover/${record['id']}" />
        <link rel="x-stanza-cover-image-thumbnail" type="image/jpeg" href="http://${server}:${port}/get/thumb/${record['id']}" />
        <content type="xhtml">
          <div xmlns="http://www.w3.org/1999/xhtml"><pre>${record['comments']}</pre></div>
        </content>
    </entry>
    '''))
    
    STANZA = MarkupTemplate(textwrap.dedent('''\
    <?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:py="http://genshi.edgewall.org/">
      <title>calibre Library</title>
      <id>$id</id>
      <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
      <author>
        <name>calibre</name>
        <uri>http://calibre.kovidgoyal.net</uri>
      </author>
      <subtitle>
            ${subtitle}
      </subtitle>
      <py:for each="entry in data">
      ${Markup(entry)}
      </py:for>
    </feed>
    '''))

    
    def __init__(self, db, opts, embedded=False, show_tracebacks=True):
        self.db = db
        for item in self.db:
            item
            break
        self.opts = opts
        
        cherrypy.config.update({
                                'log.screen'             : opts.develop,
                                'engine.autoreload_on'   : opts.develop,
                                'tools.log_headers.on'   : opts.develop,
                                'checker.on'             : opts.develop,
                                'request.show_tracebacks': show_tracebacks,
                                'server.socket_host'     : '0.0.0.0',
                                'server.socket_port'     : opts.port,
                                'server.socket_timeout'  : opts.timeout, #seconds
                                'server.thread_pool'     : opts.thread_pool, # number of threads
                               })
        if embedded:
            cherrypy.config.update({'engine.SIGHUP'          : None,
                                    'engine.SIGTERM'         : None,})
        self.config = {'global': {
            'tools.gzip.on'        : True,
            'tools.gzip.mime_types': ['text/html', 'text/plain', 'text/xml', 'text/javascript', 'text/css'],
        }}
        if opts.password:
            g = self.config['global']
            g['tools.digest_auth.on']    = True
            g['tools.digest_auth.realm'] = _('Password to access your calibre library. Username is ') + opts.username.strip()
            g['tools.digest_auth.users'] = {opts.username.strip():opts.password.strip()} 
            
        self.is_running = False
        self.exception = None
        
    def setup_loggers(self):
        access_file = log_access_file
        error_file  = log_error_file
        log = cherrypy.log

        maxBytes = getattr(log, "rot_maxBytes", 10000000)
        backupCount = getattr(log, "rot_backupCount", 1000)
        
        # Make a new RotatingFileHandler for the error log.
        h = RotatingFileHandler(error_file, 'a', maxBytes, backupCount)
        h.setLevel(logging.DEBUG)
        h.setFormatter(cherrypy._cplogging.logfmt)
        log.error_log.addHandler(h)
        
        # Make a new RotatingFileHandler for the access log.
        h = RotatingFileHandler(access_file, 'a', maxBytes, backupCount)
        h.setLevel(logging.DEBUG)
        h.setFormatter(cherrypy._cplogging.logfmt)
        log.access_log.addHandler(h)

    
    def start(self):
        self.is_running = False
        self.setup_loggers()
        cherrypy.tree.mount(self, '', config=self.config)
        try:
            cherrypy.engine.start()
            self.is_running = True
            cherrypy.engine.block()
        except Exception, e:
            self.exception = e
        finally:
            self.is_running = False
        
    def exit(self):
        cherrypy.engine.exit()
    
    def get_cover(self, id, thumbnail=False):
        cover = self.db.cover(id, index_is_id=True, as_file=True)
        if cover is None:
            cover = cStringIO.StringIO(server_resources['default_cover.jpg'])
        cherrypy.response.headers['Content-Type'] = 'image/jpeg'
        path = getattr(cover, 'name', False)
        updated = datetime.utcfromtimestamp(os.stat(path).st_mtime) if path and os.access(path, os.R_OK) else build_time
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        if not thumbnail:
            return cover.read()
        try:
            im = Image.open(cover)
            width, height = im.size
            scaled, width, height = fit_image(width, height, 80, 60)
            if not scaled:
                return cover.read()
            im.thumbnail((width, height))
            o = cStringIO.StringIO()
            im.save(o, 'JPEG')
            return o.getvalue()
        except Exception, err:
            raise cherrypy.HTTPError(404, 'failed to generate thumbnail: %s'%err)
        
    def get_format(self, id, format):
        format = format.upper()
        fmt = self.db.format(id, format, index_is_id=True, as_file=True, mode='rb')
        if fmt is None:
            raise cherrypy.HTTPError(404, 'book: %d does not have format: %s'%(id, format))
        mt = mimetypes.guess_type('dummy.'+format.lower())[0]
        if mt is None:
            mt = 'application/octet-stream'
        cherrypy.response.headers['Content-Type'] = mt
        path = getattr(fmt, 'name', None)
        if path and os.path.exists(path):
            updated = datetime.utcfromtimestamp(os.stat(path).st_mtime)
            cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        return fmt.read()
    
    def sort(self, items, field, order):
        field = field.lower().strip()
        if field == 'author':
            field = 'authors'
        if field == 'date':
            field = 'timestamp'
        if field not in ('title', 'authors', 'rating', 'timestamp', 'tags', 'size', 'series'):
            raise cherrypy.HTTPError(400, '%s is not a valid sort field'%field)
        cmpf = cmp if field in ('rating', 'size', 'timestamp') else \
                lambda x, y: cmp(x.lower() if x else '', y.lower() if y else '')
        field = FIELD_MAP[field]
        getter = operator.itemgetter(field)
        items.sort(cmp=lambda x, y: cmpf(getter(x), getter(y)), reverse=not order)
    
    def last_modified(self, updated):
        lm = updated.strftime('day, %d month %Y %H:%M:%S GMT')
        day ={0:'Sun', 1:'Mon', 2:'Tue', 3:'Wed', 4:'Thu', 5:'Fri', 6:'Sat'}
        lm = lm.replace('day', day[int(updated.strftime('%w'))])
        month = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 7:'Jul',
                 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'}
        return lm.replace('month', month[updated.month])
        
        
    @expose
    def stanza(self):
        ' Feeds to read calibre books on a ipod with stanza.'
        books = []
        for record in iter(self.db):
            if 'EPUB' in record[FIELD_MAP['formats']].upper():
                authors = ' & '.join([i.replace('|', ',') for i in record[2].split(',')])
                books.append(self.STANZA_ENTRY.generate(authors=authors,
                                                        record=record,
                                                        port=self.opts.port,
                                                        server=self.opts.hostname,
                                                        ).render('xml').decode('utf8'))
        
        updated = self.db.last_modified()
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        cherrypy.response.headers['Content-Type'] = 'text/xml'
        
        return self.STANZA.generate(subtitle='', data=books,
                    updated=updated, id='urn:calibre:main').render('xml')
    
    @expose
    def library(self, start='0', num='50', sort=None, search=None, _=None, order='ascending'):
        '''
        Serves metadata from the calibre database as XML.
        
        :param sort: Sort results by ``sort``. Can be one of `title,author,rating`.
        :param search: Filter results by ``search`` query. See :class:`SearchQueryParser` for query syntax
        :param start,num: Return the slice `[start:start+num]` of the sorted and filtered results
        :param _: Firefox seems to sometimes send this when using XMLHttpRequest with no caching 
        '''
        try:
            start = int(start)
        except ValueError:
            raise cherrypy.HTTPError(400, 'start: %s is not an integer'%start)
        try:
            num = int(num)
        except ValueError:
            raise cherrypy.HTTPError(400, 'num: %s is not an integer'%num)
        order = order.lower().strip() == 'ascending'
        ids = self.db.data.parse(search) if search and search.strip() else self.db.data.universal_set()
        ids = sorted(ids)
        items = [r for r in iter(self.db) if r[0] in ids]
        if sort is not None:
            self.sort(items, sort, order)
        
        book, books = MarkupTemplate(self.BOOK), []
        for record in items[start:start+num]:
            authors = '|'.join([i.replace('|', ',') for i in record[2].split(',')])
            books.append(book.generate(r=record, authors=authors).render('xml').decode('utf-8'))
        updated = self.db.last_modified()
        
        cherrypy.response.headers['Content-Type'] = 'text/xml'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        return self.LIBRARY.generate(books=books, start=start, updated=updated, 
                                     total=len(ids)).render('xml')
    
    @expose
    def index(self):
        'The / URL'
        return self.static('index.html')
    
    @expose
    def get(self, what, id):
        'Serves files, covers, thumbnails from the calibre database'
        try:
            id = int(id)
        except ValueError:
            id = id.rpartition('_')[-1].partition('.')[0]
            match = re.search(r'\d+', id)
            if not match:
                raise cherrypy.HTTPError(400, 'id:%s not an integer'%id)
            id = int(match.group())
        if not self.db.has_id(id):
            raise cherrypy.HTTPError(400, 'id:%d does not exist in database'%id)
        if what == 'thumb':
            return self.get_cover(id, thumbnail=True)
        if what == 'cover':
            return self.get_cover(id)
        return self.get_format(id, what)
    
    @expose
    def static(self, name):
        'Serves static content'
        name = name.lower()
        cherrypy.response.headers['Content-Type'] = {
                     'js'   : 'text/javascript',
                     'css'  : 'text/css',
                     'png'  : 'image/png',
                     'gif'  : 'image/gif',
                     'html' : 'text/html',
                     ''      : 'application/octet-stream',
                     }[name.rpartition('.')[-1].lower()]
        cherrypy.response.headers['Last-Modified'] = self.last_modified(build_time)
        if self.opts.develop and name in ('gui.js', 'gui.css', 'index.html'):
            path = os.path.join(os.path.dirname(__file__), 'static', name)
            lm = datetime.fromtimestamp(os.stat(path).st_mtime)
            cherrypy.response.headers['Last-Modified'] = self.last_modified(lm)
            return open(path, 'rb').read()
        else:
            if server_resources.has_key(name):
                return server_resources[name]
            raise cherrypy.HTTPError(404, '%s not found'%name)

def start_threaded_server(db, opts):
    server = LibraryServer(db, opts, embedded=True)
    server.thread = Thread(target=server.start)
    server.thread.setDaemon(True)
    server.thread.start()
    return server
    
def stop_threaded_server(server):
    server.exit()
    server.thread = None
    
def option_parser():
    return config().option_parser('%prog '+ _('[options]\n\nStart the calibre content server.'))

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    cherrypy.log.screen = True
    from calibre.utils.config import prefs
    db = LibraryDatabase2(prefs['library_path'], row_factory=True)
    server = LibraryServer(db, opts)
    server.start()
    return 0

if __name__ == '__main__':
    sys.exit(main())
