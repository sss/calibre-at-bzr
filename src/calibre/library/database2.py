from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
The database used to store ebook metadata
'''
import os, re, sys, shutil, cStringIO, glob, collections, textwrap, \
       operator, itertools, functools, traceback
from itertools import repeat
from datetime import datetime

from PyQt4.QtCore import QCoreApplication, QThread, QReadWriteLock
from PyQt4.QtGui import QApplication, QPixmap, QImage
__app = None

from calibre.library.database import LibraryDatabase
from calibre.library.sqlite import connect, IntegrityError
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.ebooks.metadata import string_to_authors, authors_to_string
from calibre.constants import preferred_encoding, iswindows, isosx


copyfile = os.link if hasattr(os, 'link') else shutil.copyfile
filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None: filesystem_encoding = 'utf-8'
iscaseinsensitive = iswindows or isosx

def normpath(x):
    # The builtin os.path.normcase doesn't work on OS X
    x = os.path.abspath(x)
    if iscaseinsensitive:
        x = x.lower()
    return x

_filename_sanitize = re.compile(r'[\0\\|\?\*<":>\+\[\]/]')
def sanitize_file_name(name, substitute='_'):
    '''
    Sanitize the filename `name`. All invalid characters are replaced by `substitute`.
    The set of invalid characters is the union of the invalid characters in Windows,
    OS X and Linux. Also removes leading an trailing whitespace.
    **WARNING:** This function also replaces path separators, so only pass file names
    and not full paths to it.
    *NOTE:* This function always returns byte strings, not unicode objects. The byte strings
    are encoded in the filesystem encoding of the platform, or UTF-8. 
    '''
    if isinstance(name, unicode):
        name = name.encode(filesystem_encoding, 'ignore')
    one = _filename_sanitize.sub(substitute, name)
    return re.sub(r'\s', ' ', one).strip()

FIELD_MAP = {'id':0, 'title':1, 'authors':2, 'publisher':3, 'rating':4, 'timestamp':5, 
             'size':6, 'tags':7, 'comments':8, 'series':9, 'series_index':10,
             'sort':11, 'author_sort':12, 'formats':13, 'isbn':14}
INDEX_MAP = dict(zip(FIELD_MAP.values(), FIELD_MAP.keys()))


class CoverCache(QThread):
    
    def __init__(self, library_path, parent=None):
        QThread.__init__(self, parent)
        self.library_path = library_path
        self.id_map = None
        self.id_map_lock = QReadWriteLock()
        self.load_queue = collections.deque()
        self.load_queue_lock = QReadWriteLock(QReadWriteLock.Recursive)
        self.cache = {}
        self.cache_lock = QReadWriteLock()
        self.id_map_stale = True
        self.keep_running = True
        
    def build_id_map(self):
        self.id_map_lock.lockForWrite()
        self.id_map = {}
        for f in glob.glob(os.path.join(self.library_path, '*', '* (*)', 'cover.jpg')):
            c = os.path.basename(os.path.dirname(f))
            try:
                id = int(re.search(r'\((\d+)\)', c[c.rindex('('):]).group(1))
                self.id_map[id] = f
            except:
                continue
        self.id_map_lock.unlock()
        self.id_map_stale = False
            
    
    def set_cache(self, ids):
        self.cache_lock.lockForWrite()
        already_loaded = set([])
        for id in self.cache.keys():
            if id in ids:
                already_loaded.add(id)
            else:
                self.cache.pop(id)
        self.cache_lock.unlock()
        ids = [i for i in ids if i not in already_loaded]
        self.load_queue_lock.lockForWrite()
        self.load_queue = collections.deque(ids)
        self.load_queue_lock.unlock()
        
    
    def run(self):
        while self.keep_running:
            if self.id_map is None or self.id_map_stale:
                self.build_id_map()
            while True: # Load images from the load queue
                self.load_queue_lock.lockForWrite()
                try:
                    id = self.load_queue.popleft()
                except IndexError:
                    break
                finally:
                    self.load_queue_lock.unlock()
                
                self.cache_lock.lockForRead()
                need = True
                if id in self.cache.keys():
                    need = False
                self.cache_lock.unlock()
                if not need:
                    continue
                path = None
                self.id_map_lock.lockForRead()
                if id in self.id_map.keys():
                    path = self.id_map[id]
                else:
                    self.id_map_stale = True
                self.id_map_lock.unlock()
                if path and os.access(path, os.R_OK):
                    try:
                        img = QImage()
                        data = open(path, 'rb').read()
                        img.loadFromData(data)
                        if img.isNull():
                            continue
                    except:
                        continue
                    self.cache_lock.lockForWrite()
                    self.cache[id] = img
                    self.cache_lock.unlock()
             
            self.sleep(1)
            
    def stop(self):
        self.keep_running = False
        
    def cover(self, id):
        val = None
        if self.cache_lock.tryLockForRead(50):
            val = self.cache.get(id, None)
            self.cache_lock.unlock()
        return val
    
    def clear_cache(self):
        self.cache_lock.lockForWrite()
        self.cache = {}
        self.cache_lock.unlock()

    def refresh(self, ids):
        self.cache_lock.lockForWrite()
        for id in ids:
            self.cache.pop(id, None)
        self.cache_lock.unlock()
        self.load_queue_lock.lockForWrite()
        for id in ids:
            self.load_queue.appendleft(id)
        self.load_queue_lock.unlock()
    
class ResultCache(SearchQueryParser):
    
    '''
    Stores sorted and filtered metadata in memory.
    '''
    
    def __init__(self):
        self._map = self._map_filtered = self._data = []
        SearchQueryParser.__init__(self)
        
    def __getitem__(self, row):
        return self._data[self._map_filtered[row]]
    
    def __len__(self):
        return len(self._map_filtered)
    
    def __iter__(self):
        for id in self._map_filtered:
            yield self._data[id]

    def universal_set(self):
        return set([i[0] for i in self._data if i is not None])

    def get_matches(self, location, query):
        matches = set([])
        if query and query.strip():
            location = location.lower().strip()
            query = query.lower()
            if location in ('tag', 'author', 'format'):
                location += 's'
            all = ('title', 'authors', 'publisher', 'tags', 'comments', 'series', 'formats')
            MAP = {}
            for x in all:
                MAP[x] = FIELD_MAP[x]
            location = [location] if location != 'all' else list(MAP.keys())
            for i, loc in enumerate(location):
                location[i] = MAP[loc]
            for item in self._data:
                if item is None: continue
                for loc in location:
                    if item[loc] and query in item[loc].lower():
                        matches.add(item[0])
                        break
        return matches
            
    def remove(self, id):
        self._data[id] = None
        if id in self._map:
            self._map.remove(id)
        if id in self._map_filtered:
            self._map_filtered.remove(id)
            
    def set(self, row, col, val):
        id = self._map_filtered[row]
        self._data[id][col] = val
        
    def index(self, id, cache=False):
        x = self._map if cache else self._map_filtered
        return x.index(id)
        
    def row(self, id):
        return self.index(id)
    
    def refresh_ids(self, conn, ids):
        for id in ids:
            self._data[id] = conn.get('SELECT * from meta WHERE id=?', (id,))[0]
        return map(self.row, ids)
    
    def books_added(self, ids, conn):
        if not ids:
            return
        self._data.extend(repeat(None, max(ids)-len(self._data)+2))
        for id in ids:
            self._data[id] = conn.get('SELECT * from meta WHERE id=?', (id,))[0]
        self._map[0:0] = ids
        self._map_filtered[0:0] = ids
    
    def refresh(self, db, field=None, ascending=True):
        temp = db.conn.get('SELECT * FROM meta')
        self._data = list(itertools.repeat(None, temp[-1][0]+2)) if temp else []
        for r in temp:
            self._data[r[0]] = r
        self._map = [i[0] for i in self._data if i is not None]
        if field is not None:
            self.sort(field, ascending)
        self._map_filtered = list(self._map)
    
    def seriescmp(self, x, y):
        ans = self.strcmp(self._data[x][9], self._data[y][9])
        if ans != 0: return ans
        return cmp(self._data[x][10], self._data[y][10])
    
    def cmp(self, loc, x, y, str=True):
        ans = cmp(self._data[x][loc].lower(), self._data[y][loc].lower()) if str else\
              cmp(self._data[x][loc], self._data[y][loc])
        if ans != 0: return ans
        return cmp(self._data[x][11].lower(), self._data[y][11].lower())
    
    def sort(self, field, ascending):
        import time
        start = time.time()
        field = field.lower().strip()
        if field in ('author', 'tag', 'comment'):
            field += 's'
        if field == 'date': field = 'timestamp'
        elif field == 'title': field = 'sort'
        elif field == 'author': field = 'author_sort'
        fcmp = self.seriescmp if field == 'series' else \
            functools.partial(self.cmp, FIELD_MAP[field], field not in ('size', 'rating', 'timestamp'))
        self._map.sort(cmp=fcmp, reverse=not ascending)
        print time.time() - start
                
    def search(self, query):
        if not query or not query.strip():
            self._map_filtered = list(self._map)
            return
        matches = sorted(self.parse(query))
        self._map_filtered = [id for id in self._map if id in matches]
    
    
class Tag(unicode):
    
    def __init__(self, name):
        unicode.__init__(self, name)
        self.count = 0
        self.state = 0
        
    def as_string(self):
        return u'[%d] %s'%(self.count, self)

class LibraryDatabase2(LibraryDatabase):
    '''
    An ebook metadata database that stores references to ebook files on disk.
    '''
    PATH_LIMIT = 40 if 'win32' in sys.platform else 100
    @apply
    def user_version():
        doc = 'The user version of this database'
        
        def fget(self):
            return self.conn.get('pragma user_version;', all=False)
        
        def fset(self, val):
            self.conn.execute('pragma user_version=%d'%int(val))
            self.conn.commit()
        
        return property(doc=doc, fget=fget, fset=fset)
    
    def connect(self):
        if 'win32' in sys.platform and len(self.library_path) + 4*self.PATH_LIMIT + 10 > 259:
            raise ValueError('Path to library too long. Must be less than %d characters.'%(259-4*self.PATH_LIMIT-10))
        exists = os.path.exists(self.dbpath)
        self.conn = connect(self.dbpath, self.row_factory)
        if exists and self.user_version == 0:
            self.conn.close()
            os.remove(self.dbpath)
            self.conn = connect(self.dbpath, self.row_factory)
        if self.user_version == 0: 
            self.initialize_database()
    
    def __init__(self, library_path, row_factory=False):
        if not os.path.exists(library_path):
            os.makedirs(library_path)
        self.listeners = set([])
        self.library_path = os.path.abspath(library_path)
        self.row_factory = row_factory
        self.dbpath = os.path.join(library_path, 'metadata.db')
        if isinstance(self.dbpath, unicode):
            self.dbpath = self.dbpath.encode(filesystem_encoding)
        self.connect()
        # Upgrade database 
        while True:
            meth = getattr(self, 'upgrade_version_%d'%self.user_version, None)
            if meth is None:
                break
            else:
                print 'Upgrading database to version %d...'%(self.user_version+1)
                meth()
                self.conn.commit()
                self.user_version += 1
        
        self.data    = ResultCache()
        self.data.refresh()
        self.search  = self.data.search
        self.refresh = functools.partial(self.data.refresh, self)
        self.sort    = functools.partial(self.data.refresh, self)
        self.index   = self.data.index
        self.refresh_ids = functools.partial(self.data.refresh_ids, self.conn)
        self.row     = self.data.row
        
    def initialize_database(self):
        from calibre.resources import metadata_sqlite
        self.conn.executescript(metadata_sqlite)
        self.user_version = 1
        
    def upgrade_version_1(self):
        '''
        Normalize indices.
        '''
        self.conn.executescript(textwrap.dedent('''\
        DROP INDEX authors_idx;
        CREATE INDEX authors_idx ON books (author_sort COLLATE NOCASE, sort COLLATE NOCASE);
        DROP INDEX series_idx;
        CREATE INDEX series_idx ON series (name COLLATE NOCASE);
        CREATE INDEX series_sort_idx ON books (series_index, id);
        '''))
        
    def upgrade_version_2(self):
        ''' Fix Foreign key constraints for deleting from link tables. '''
        script = textwrap.dedent('''\
        DROP TRIGGER fkc_delete_books_%(ltable)s_link;
        CREATE TRIGGER fkc_delete_on_%(table)s
        BEFORE DELETE ON %(table)s
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_%(ltable)s_link WHERE %(ltable_col)s=OLD.id) > 0
                THEN RAISE(ABORT, 'Foreign key violation: %(table)s is still referenced')
            END;
        END;
        DELETE FROM %(table)s WHERE (SELECT COUNT(id) FROM books_%(ltable)s_link WHERE %(ltable_col)s=%(table)s.id) < 1;
        ''')
        self.conn.executescript(script%dict(ltable='authors', table='authors', ltable_col='author'))
        self.conn.executescript(script%dict(ltable='publishers', table='publishers', ltable_col='publisher'))
        self.conn.executescript(script%dict(ltable='tags', table='tags', ltable_col='tag'))
        self.conn.executescript(script%dict(ltable='series', table='series', ltable_col='series'))
    
    def last_modified(self):
        ''' Return last modified time as a UTC datetime object'''
        return datetime.utcfromtimestamp(os.stat(self.dbpath).st_mtime)

    def path(self, index, index_is_id=False):
        'Return the relative path to the directory containing this books files as a unicode string.'
        id = index if index_is_id else self.id(index)
        path = self.conn.get('SELECT path FROM books WHERE id=?', (id,), all=False).replace('/', os.sep)
        return path
    
    def abspath(self, index, index_is_id=False):
        'Return the absolute path to the directory containing this books files as a unicode string.'
        path = os.path.join(self.library_path, self.path(index, index_is_id=index_is_id))
        if not os.path.exists(path):
            os.makedirs(path)
        return path
            
    
    def construct_path_name(self, id):
        '''
        Construct the directory name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = sanitize_file_name(authors.split(',')[0][:self.PATH_LIMIT]).decode(filesystem_encoding)
        title  = sanitize_file_name(self.title(id, index_is_id=True)[:self.PATH_LIMIT]).decode(filesystem_encoding)
        path   = author + '/' + title + ' (%d)'%id
        return path
    
    def construct_file_name(self, id):
        '''
        Construct the file name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = sanitize_file_name(authors.split(',')[0][:self.PATH_LIMIT]).decode(filesystem_encoding)
        title  = sanitize_file_name(self.title(id, index_is_id=True)[:self.PATH_LIMIT]).decode(filesystem_encoding)
        name   = title + ' - ' + author
        return name
    
    def set_path(self, index, index_is_id=False):
        '''
        Set the path to the directory containing this books files based on its
        current title and author. If there was a previous directory, its contents
        are copied and it is deleted.
        '''
        id = index if  index_is_id else self.id(index)
        path = self.construct_path_name(id)
        current_path = self.path(id, index_is_id=True).replace(os.sep, '/')
        formats = self.formats(id, index_is_id=True)
        formats = formats.split(',') if formats else []
        # Check if the metadata used to construct paths has changed
        fname = self.construct_file_name(id)
        changed = False
        for format in formats:
            name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
            if name and name != fname:
                changed = True
                break
        if path == current_path and not changed:
            return
        
        tpath = os.path.join(self.library_path, *path.split('/'))
        if not os.path.exists(tpath):
            os.makedirs(tpath)
        spath = os.path.join(self.library_path, *current_path.split('/'))
        
        if current_path and os.path.exists(spath): # Migrate existing files
            cdata = self.cover(id, index_is_id=True)
            if cdata is not None:
                open(os.path.join(tpath, 'cover.jpg'), 'wb').write(cdata)
            for format in formats:
                # Get data as string (can't use file as source and target files may be the same)
                f = self.format(id, format, index_is_id=True, as_file=False)
                if not  f:
                    continue
                stream = cStringIO.StringIO(f)
                self.add_format(id, format, stream, index_is_id=True, path=tpath)
        self.conn.execute('UPDATE books SET path=? WHERE id=?', (path, id))
        self.conn.commit()
        # Delete not needed directories
        if current_path and os.path.exists(spath):
            if normpath(spath) != normpath(tpath):
                shutil.rmtree(spath)
                parent  = os.path.dirname(spath)
                if len(os.listdir(parent)) == 0:
                    shutil.rmtree(parent)
            
    def add_listener(self, listener):
        '''
        Add a listener. Will be called on change events with two arguments.
        Event name and list of affected ids.
        '''
        self.listeners.add(listener)
    
    def notify(self, event, ids=[]):
        'Notify all listeners'
        for listener in self.listeners:
            try:
                listener(event, ids)
            except:
                traceback.print_exc()
                continue
    
    def cover(self, index, index_is_id=False, as_file=False, as_image=False):
        '''
        Return the cover image as a bytestring (in JPEG format) or None.
        
        `as_file` : If True return the image as an open file object
        `as_image`: If True return the image as a QImage object
        '''
        id = index if  index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if os.access(path, os.R_OK):
            f = open(path, 'rb')
            if as_image:
                img = QImage()
                img.loadFromData(f.read())
                return img
            return f if as_file else f.read()
        
    def has_cover(self, index, index_is_id=False):
        id = index if  index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        return os.access(path, os.R_OK)
    
    def set_cover(self, id, data):
        '''
        Set the cover for this book.
        
        `data`: Can be either a QImage, QPixmap, file object or bytestring
        '''
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if callable(getattr(data, 'save', None)):
            data.save(path)
        else:
            if not QCoreApplication.instance():
                global __app
                __app = QApplication([])
            p = QPixmap()
            if callable(getattr(data, 'read', None)):
                data = data.read()
            p.loadFromData(data)
            p.save(path)
            
    def all_formats(self):
        formats = self.conn.get('SELECT format from data')
        if not formats:
            return set([])
        return set([f[0] for f in formats])
    
    def formats(self, index, index_is_id=False):
        ''' Return available formats as a comma separated list or None if there are no available formats '''
        id = index if index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        try:
            formats = self.conn.get('SELECT format FROM data WHERE book=?', (id,))
            name = self.conn.get('SELECT name FROM data WHERE book=?', (id,), all=False)
            formats = map(lambda x:x[0], formats)
        except:
            return None
        ans = []
        for format in formats:
            _format = ('.' + format.lower()) if format else ''
            if os.access(os.path.join(path, name+_format), os.R_OK|os.W_OK):
                ans.append(format)
        return ','.join(ans)
                
    def has_format(self, index, format, index_is_id=False):
        id = index if index_is_id else self.id(index)
        name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        if name:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
            format = ('.' + format.lower()) if format else ''
            path = os.path.join(path, name+format)
            return os.access(path, os.R_OK|os.W_OK)
        return False
    
    def format_abspath(self, index, format, index_is_id=False):
        'Return absolute path to the ebook file of format `format`'
        id = index if index_is_id else self.id(index)
        name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        if name:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
            format = ('.' + format.lower()) if format else ''
            path = os.path.join(path, name+format)
            if os.access(path, os.R_OK|os.W_OK):
                return path
    
    def format(self, index, format, index_is_id=False, as_file=False, mode='r+b'):
        '''
        Return the ebook format as a bytestring or `None` if the format doesn't exist,
        or we don't have permission to write to the ebook file. 
        
        `as_file`: If True the ebook format is returned as a file object opened in `mode` 
        '''
        path = self.format_abspath(index, format, index_is_id=index_is_id)
        if path is not None:
            f = open(path, mode)
            return f if as_file else f.read()
        if self.has_format(index, format, index_is_id):
            self.remove_format(id, format, index_is_id=True)
        
    def add_format(self, index, format, stream, index_is_id=False, path=None):
        id = index if index_is_id else self.id(index)
        if path is None:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        if name:
            self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, format))
        name = self.construct_file_name(id)
        ext = ('.' + format.lower()) if format else ''
        dest = os.path.join(path, name+ext)
        pdir = os.path.dirname(dest)
        if not os.path.exists(pdir):
            os.makedirs(pdir)
        with open(dest, 'wb') as f:
            shutil.copyfileobj(stream, f)
        stream.seek(0, 2)
        size=stream.tell()
        self.conn.execute('INSERT INTO data (book,format,uncompressed_size,name) VALUES (?,?,?,?)',
                          (id, format.upper(), size, name))
        self.conn.commit()
        self.notify('metadata', [id])
        
    def delete_book(self, id):
        '''
        Removes book from the result cache and the underlying database.
        '''
        self.data.remove(id)
        path = os.path.join(self.library_path, self.path(id, True))
        if os.path.exists(path):
            shutil.rmtree(path)
            parent = os.path.dirname(path)
            if len(os.listdir(parent)) == 0:
                shutil.rmtree(parent)
        self.conn.execute('DELETE FROM books WHERE id=?', (id,))
        self.conn.commit()
        self.clean()
        self.notify('delete', [id])
    
    def remove_format(self, index, format, index_is_id=False):
        id = index if index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        name = name[0] if name else False
        if name:
            ext = ('.' + format.lower()) if format else ''
            path = os.path.join(path, name+ext)
            try:
                os.remove(path)
            except:
                pass
            self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, format.upper()))
            self.conn.commit()
            self.notify('metadata', [id])
    
    def clean(self):
        '''
        Remove orphaned entries.
        '''
        st = 'DELETE FROM %(table)s WHERE (SELECT COUNT(id) FROM books_%(ltable)s_link WHERE %(ltable_col)s=%(table)s.id) < 1;'
        self.conn.execute(st%dict(ltable='authors', table='authors', ltable_col='author'))
        self.conn.execute(st%dict(ltable='publishers', table='publishers', ltable_col='publisher'))
        self.conn.execute(st%dict(ltable='tags', table='tags', ltable_col='tag'))
        self.conn.execute(st%dict(ltable='series', table='series', ltable_col='series'))
        self.conn.commit()
    
    def get_categories(self, sort_on_count=False):
        categories = {}
        def get(name, category, field='name'):
            ans = self.conn.get('SELECT DISTINCT %s FROM %s'%(field, name))
            ans = [x[0].strip() for x in ans]
            try:
                ans.remove('')
            except ValueError: pass
            categories[category] = list(map(Tag, ans))
            tags = categories[category]
            if name != 'data':
                for tag in tags:
                    id = self.conn.get('SELECT id FROM %s WHERE %s=?'%(name, field), (tag,), all=False)
                    tag.id = id
                for tag in tags:
                    if tag.id is not None:
                        tag.count = self.conn.get('SELECT COUNT(id) FROM books_%s_link WHERE %s=?'%(name, category), (tag.id,), all=False)
            else:
                for tag in tags:
                    tag.count = self.conn.get('SELECT COUNT(format) FROM data WHERE format=?', (tag,), all=False)
            tags.sort(reverse=sort_on_count, cmp=(lambda x,y:cmp(x.count,y.count)) if sort_on_count else cmp)
        for x in (('authors', 'author'), ('tags', 'tag'), ('publishers', 'publisher'), 
                  ('series', 'series')):
            get(*x)
        get('data', 'format', 'format')
        return categories
        
    
    def set(self, row, column, val):
        '''
        Convenience method for setting the title, authors, publisher or rating
        '''
        id = self.data[row][0]
        col = {'title':1, 'authors':2, 'publisher':3, 'rating':4, 'tags':7}[column]

        self.data.set(row, col, val)
        if column == 'authors':
            val = string_to_authors(val)
            self.set_authors(id, val, notify=False)
        elif column == 'title':
            self.set_title(id, val, notify=False)
        elif column == 'publisher':
            self.set_publisher(id, val, notify=False)
        elif column == 'rating':
            self.set_rating(id, val)
        elif column == 'tags':
            self.set_tags(id, val.split(','), append=False, notify=False)
        self.data.refresh_ids(self.conn, [id])
        self.set_path(id, True)
        self.notify('metadata', [id])
    
    def set_metadata(self, id, mi):
        '''
        Set metadata for the book `id` from the `MetaInformation` object `mi` 
        '''
        if mi.title:
            self.set_title(id, mi.title)
        if not mi.authors:
                mi.authors = [_('Unknown')]
        authors = []
        for a in mi.authors:
            authors += a.split('&')
        self.set_authors(id, authors, notify=False)
        if mi.author_sort:
            self.set_author_sort(id, mi.author_sort)
        if mi.publisher:
            self.set_publisher(id, mi.publisher, notify=False)
        if mi.rating:
            self.set_rating(id, mi.rating)
        if mi.series:
            self.set_series(id, mi.series, notify=False)
        if mi.cover_data[1] is not None:
            self.set_cover(id, mi.cover_data[1])
        if mi.tags:
            self.set_tags(id, mi.tags, notify=False)
        if mi.comments:
            self.set_comment(id, mi.comments)
        if mi.isbn and mi.isbn.strip():
            self.set_isbn(id, mi.isbn)
        self.set_path(id, True)
        self.notify('metadata', [id])
        
    def set_authors(self, id, authors, notify=True):
        '''
        `authors`: A list of authors.
        '''
        self.conn.execute('DELETE FROM books_authors_link WHERE book=?',(id,))
        self.conn.execute('DELETE FROM authors WHERE (SELECT COUNT(id) FROM books_authors_link WHERE author=authors.id) < 1')
        for a in authors:
            if not a:
                continue
            a = a.strip().replace(',', '|')
            if not isinstance(a, unicode):
                a = a.decode(preferred_encoding, 'replace')
            author = self.conn.get('SELECT id from authors WHERE name=?', (a,), all=False)
            if author:
                aid = author
                # Handle change of case
                self.conn.execute('UPDATE authors SET name=? WHERE id=?', (a, aid))
            else:
                aid = self.conn.execute('INSERT INTO authors(name) VALUES (?)', (a,)).lastrowid
            try:
                self.conn.execute('INSERT INTO books_authors_link(book, author) VALUES (?,?)', (id, aid))
            except IntegrityError: # Sometimes books specify the same author twice in their metadata
                pass
        self.set_path(id, True)
        self.notify('metadata', [id])
        
    def set_title(self, id, title, notify=True):
        if not title:
            return
        if not isinstance(title, unicode):
            title = title.decode(preferred_encoding, 'replace')
        self.conn.execute('UPDATE books SET title=? WHERE id=?', (title, id))
        self.set_path(id, True)
        self.notify('metadata', [id])
    
    def set_publisher(self, id, publisher, notify=True):
        self.conn.execute('DELETE FROM books_publishers_link WHERE book=?',(id,))
        self.conn.execute('DELETE FROM publishers WHERE (SELECT COUNT(id) FROM books_publishers_link WHERE publisher=publishers.id) < 1')
        if publisher:
            if not isinstance(publisher, unicode):
                publisher = publisher.decode(preferred_encoding, 'replace')
            pub = self.conn.get('SELECT id from publishers WHERE name=?', (publisher,), all=False)
            if pub:
                aid = pub
            else:
                aid = self.conn.execute('INSERT INTO publishers(name) VALUES (?)', (publisher,)).lastrowid
            self.conn.execute('INSERT INTO books_publishers_link(book, publisher) VALUES (?,?)', (id, aid))
        self.conn.commit()
        self.notify('metadata', [id])
    
    def set_tags(self, id, tags, append=False, notify=True):
        '''
        @param tags: list of strings
        @param append: If True existing tags are not removed
        '''
        if not append:
            self.conn.execute('DELETE FROM books_tags_link WHERE book=?', (id,))
            self.conn.execute('DELETE FROM tags WHERE (SELECT COUNT(id) FROM books_tags_link WHERE tag=tags.id) < 1')
        for tag in set(tags):
            tag = tag.lower().strip()
            if not tag:
                continue
            if not isinstance(tag, unicode):
                tag = tag.decode(preferred_encoding, 'replace')
            t = self.conn.get('SELECT id FROM tags WHERE name=?', (tag,), all=False)
            if t:
                tid = t
            else:
                tid = self.conn.execute('INSERT INTO tags(name) VALUES(?)', (tag,)).lastrowid

            if not self.conn.get('SELECT book FROM books_tags_link WHERE book=? AND tag=?',
                                        (id, tid), all=False):
                self.conn.execute('INSERT INTO books_tags_link(book, tag) VALUES (?,?)',
                              (id, tid))
        self.conn.commit()
        self.notify('metadata', [id])

    
    def set_series(self, id, series, notify=True):
        self.conn.execute('DELETE FROM books_series_link WHERE book=?',(id,))
        self.conn.execute('DELETE FROM series WHERE (SELECT COUNT(id) FROM books_series_link WHERE series=series.id) < 1')
        if series:
            if not isinstance(series, unicode):
                series = series.decode(preferred_encoding, 'replace')
            s = self.conn.get('SELECT id from series WHERE name=?', (series,), all=False)
            if s:
                aid = s
            else:
                aid = self.conn.execute('INSERT INTO series(name) VALUES (?)', (series,)).lastrowid
            self.conn.execute('INSERT INTO books_series_link(book, series) VALUES (?,?)', (id, aid))
        self.conn.commit()
        try:
            row = self.row(id)
            if row is not None:
                self.data.set(row, 9, series)
        except ValueError:
            pass
        self.notify('metadata', [id])
            
    def set_series_index(self, id, idx, notify=True):
        if idx is None:
            idx = 1
        idx = int(idx)
        self.conn.execute('UPDATE books SET series_index=? WHERE id=?', (int(idx), id))
        self.conn.commit()
        try:
            row = self.row(id)
            if row is not None:
                self.data.set(row, 10, idx)
        except ValueError:
            pass
        self.notify('metadata', [id])
        
    def add_books(self, paths, formats, metadata, uris=[], add_duplicates=True):
        '''
        Add a book to the database. The result cache is not updated.
        @param paths: List of paths to book files or file-like objects
        '''
        formats, metadata, uris = iter(formats), iter(metadata), iter(uris)
        duplicates = []
        ids = []
        for path in paths:
            mi = metadata.next()
            format = formats.next()
            try:
                uri = uris.next()
            except StopIteration:
                uri = None
            if not add_duplicates and self.has_book(mi):
                duplicates.append((path, format, mi, uri))
                continue
            series_index = 1 if mi.series_index is None else mi.series_index
            aus = mi.author_sort if mi.author_sort else ', '.join(mi.authors)
            obj = self.conn.execute('INSERT INTO books(title, uri, series_index, author_sort) VALUES (?, ?, ?, ?)', 
                              (mi.title, uri, series_index, aus))
            id = obj.lastrowid
            ids.append(id)
            self.set_path(id, True)
            self.conn.commit()
            self.set_metadata(id, mi)
            stream = path if hasattr(path, 'read') else open(path, 'rb')
            stream.seek(0)
            
            self.add_format(id, format, stream, index_is_id=True)
            if not hasattr(path, 'read'):
                stream.close()
        self.conn.commit()
        if ids:
            self.data.books_added(ids, self.conn)
        if duplicates:
            paths    = tuple(duplicate[0] for duplicate in duplicates)
            formats  = tuple(duplicate[1] for duplicate in duplicates)
            metadata = tuple(duplicate[2] for duplicate in duplicates)
            uris     = tuple(duplicate[3] for duplicate in duplicates)
            return (paths, formats, metadata, uris), len(ids)
        return None, len(ids)
     
    def import_book(self, mi, formats):
        series_index = 1 if mi.series_index is None else mi.series_index
        if not mi.authors:
            mi.authors = ['Unknown']
        aus = mi.author_sort if mi.author_sort else ', '.join(mi.authors)
        obj = self.conn.execute('INSERT INTO books(title, uri, series_index, author_sort) VALUES (?, ?, ?, ?)', 
                          (mi.title, None, series_index, aus))
        id = obj.lastrowid
        self.set_path(id, True)
        self.set_metadata(id, mi)
        for path in formats:
            ext = os.path.splitext(path)[1][1:].lower()
            stream = open(path, 'rb')
            self.add_format(id, ext, stream, index_is_id=True)
        self.conn.commit()
        self.data.books_added([id], self.conn)
        self.notify('add', [id])
        
    def move_library_to(self, newloc, progress=None):
        header = _(u'<p>Copying books to %s<br><center>')%newloc
        books = self.conn.get('SELECT id, path, title FROM books')
        if progress is not None:
            progress.setValue(0)
            progress.setLabelText(header)
            QCoreApplication.processEvents()
            progress.setAutoReset(False)
            progress.setRange(0, len(books))
        if not os.path.exists(newloc):
            os.makedirs(newloc)
        old_dirs = set([])
        for i, book in enumerate(books):
            if progress is not None:
                progress.setLabelText(header+_(u'Copying <b>%s</b>')%book[2])
            path = book[1]
            if not path:
                continue
            dir = path.split('/')[0]
            srcdir = os.path.join(self.library_path, dir)
            tdir = os.path.join(newloc, dir)
            if os.path.exists(tdir):
                shutil.rmtree(tdir)
            if os.path.exists(srcdir):
                shutil.copytree(srcdir, tdir)
            old_dirs.add(srcdir)
            if progress is not None:
                progress.setValue(i+1)
        
        dbpath = os.path.join(newloc, os.path.basename(self.dbpath))
        shutil.copyfile(self.dbpath, dbpath)
        opath = self.dbpath
        self.conn.close()
        self.library_path, self.dbpath = newloc, dbpath
        self.connect()
        try:
            os.unlink(opath)
            for dir in old_dirs:
                shutil.rmtree(dir)
        except:
            pass
        if progress is not None:
            progress.reset()
            progress.hide()
            
    
    def __iter__(self):
        if len(self.data._data) == 0:
            self.refresh('timestamp', True)
        for record in self.data._data:
            if record is not None:
                yield record
    
    def all_ids(self):
        for i in iter(self):
            yield i['id']
            
    def count(self):
        return len(self.data._map)
    
    def get_data_as_dict(self, prefix=None, authors_as_string=False):
        '''
        Return all metadata stored in the database as a dict. Includes paths to
        the cover and each format.
        
        :param prefix: The prefix for all paths. By default, the prefix is the absolute path
        to the library folder.
        '''
        if prefix is None:
            prefix = self.library_path
        FIELDS = set(['title', 'authors', 'publisher', 'rating', 'timestamp', 'size', 'tags', 'comments', 'series', 'series_index', 'isbn'])
        data = []
        if len(self.data) == 0:
            self.refresh(None, True)
        for record in self.data:
            if record is None: continue
            x = {}
            for field in FIELDS:
                x[field] = record[field]
            data.append(x)
            x['id'] = record[0]
            x['formats'] = []
            x['authors'] = [i.replace('|', ',') for i in x['authors'].split(',')]
            if authors_as_string:
                x['authors'] = authors_to_string(x['authors'])
            x['tags'] = [i.replace('|', ',').strip() for i in x['tags'].split(',')] if x['tags'] else []
            path = os.path.join(prefix, self.path(record['id'], index_is_id=True))
            x['cover'] = os.path.join(path, 'cover.jpg')
            if not self.has_cover(x['id'], index_is_id=True):
                x['cover'] = None
            path += os.sep +  self.construct_file_name(record['id']) + '.%s'
            formats = self.formats(record['id'], index_is_id=True)
            if formats:
                for fmt in formats.split(','):
                    x['formats'].append(path%fmt.lower())
                    x['fmt_'+fmt.lower()] = path%fmt.lower()
                x['available_formats'] = [i.upper() for i in formats.split(',')]
            
        return data
    
    def migrate_old(self, db, progress):
        header = _(u'<p>Migrating old database to ebook library in %s<br><center>')%self.library_path
        progress.setValue(0)
        progress.setLabelText(header)
        QCoreApplication.processEvents()
        db.conn.row_factory = lambda cursor, row : tuple(row)
        db.conn.text_factory = lambda x : unicode(x, 'utf-8', 'replace')
        books = db.conn.get('SELECT id, title, sort, timestamp, uri, series_index, author_sort, isbn FROM books ORDER BY id ASC')
        progress.setAutoReset(False)
        progress.setRange(0, len(books))
        
        for book in books:
            self.conn.execute('INSERT INTO books(id, title, sort, timestamp, uri, series_index, author_sort, isbn) VALUES(?, ?, ?, ?, ?, ?, ?, ?);', book)
            
        tables = '''
authors  ratings      tags    series    books_tags_link        
comments               publishers
books_authors_link     conversion_options     
books_publishers_link                   
books_ratings_link                        
books_series_link      feeds
'''.split()
        for table in tables:
            rows = db.conn.get('SELECT * FROM %s ORDER BY id ASC'%table) 
            for row in rows:
                self.conn.execute('INSERT INTO %s VALUES(%s)'%(table, ','.join(repeat('?', len(row)))), row)
                
        for i, book in enumerate(books):
            progress.setLabelText(header+_(u'Copying <b>%s</b>')%book[1])
            id = book[0]
            self.set_path(id, True)
            formats = db.formats(id, index_is_id=True)
            if not formats:
                formats = []
            else:
                formats = formats.split(',')
            for format in formats:
                data = db.format(id, format, index_is_id=True)
                if data:
                    self.add_format(id, format, cStringIO.StringIO(data), index_is_id=True)
            cover = db.cover(id, index_is_id=True)
            if cover:
                self.set_cover(id, cover)
            progress.setValue(i+1)
        self.conn.commit()
        progress.setLabelText(_('Compacting database'))
        self.vacuum()
        progress.reset()
        return len(books)
        
        
