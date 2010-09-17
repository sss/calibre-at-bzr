#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, itertools
from itertools import repeat
from datetime import timedelta
from threading import Thread, RLock
from Queue import Queue, Empty

from PyQt4.Qt import QImage, Qt

from calibre.utils.config import tweaks
from calibre.utils.date import parse_date, now, UNDEFINED_DATE
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.utils.pyparsing import ParseException
from calibre.ebooks.metadata import title_sort
from calibre import fit_image

class CoverCache(Thread):

    def __init__(self, db):
        Thread.__init__(self)
        self.daemon = True
        self.db = db
        self.load_queue = Queue()
        self.keep_running = True
        self.cache = {}
        self.lock = RLock()
        self.null_image = QImage()

    def stop(self):
        self.keep_running = False

    def _image_for_id(self, id_):
        img = self.db.cover(id_, index_is_id=True, as_image=True)
        if img is None:
            img = QImage()
        if not img.isNull():
            scaled, nwidth, nheight = fit_image(img.width(),
                    img.height(), 600, 800)
            if scaled:
                img = img.scaled(nwidth, nheight, Qt.KeepAspectRatio,
                        Qt.SmoothTransformation)

        return img

    def run(self):
        while self.keep_running:
            try:
                id_ = self.load_queue.get(True, 1)
            except Empty:
                continue
            try:
                img = self._image_for_id(id_)
            except:
                import traceback
                traceback.print_exc()
                continue
            with self.lock:
                self.cache[id_] = img

    def set_cache(self, ids):
        with self.lock:
            already_loaded = set([])
            for id in self.cache.keys():
                if id in ids:
                    already_loaded.add(id)
                else:
                    self.cache.pop(id)
        for id_ in set(ids) - already_loaded:
            self.load_queue.put(id_)

    def cover(self, id_):
        with self.lock:
            return self.cache.get(id_, self.null_image)

    def clear_cache(self):
        with self.lock:
            self.cache = {}

    def refresh(self, ids):
        with self.lock:
            for id_ in ids:
                self.cache.pop(id_, None)
                self.load_queue.put(id_)

### Global utility function for get_match here and in gui2/library.py
CONTAINS_MATCH = 0
EQUALS_MATCH   = 1
REGEXP_MATCH   = 2
def _match(query, value, matchkind):
    for t in value:
        t = t.lower()
        try:     ### ignore regexp exceptions, required because search-ahead tries before typing is finished
            if ((matchkind == EQUALS_MATCH and query == t) or
                (matchkind == REGEXP_MATCH and re.search(query, t, re.I)) or ### search unanchored
                (matchkind == CONTAINS_MATCH and query in t)):
                    return True
        except re.error:
            pass
    return False

class ResultCache(SearchQueryParser):

    '''
    Stores sorted and filtered metadata in memory.
    '''
    def __init__(self, FIELD_MAP, field_metadata):
        self.FIELD_MAP = FIELD_MAP
        self._map = self._data = self._map_filtered = []
        self.first_sort = True
        self.search_restriction = ''
        self.field_metadata = field_metadata
        self.all_search_locations = field_metadata.get_search_terms()
        SearchQueryParser.__init__(self, self.all_search_locations)
        self.build_date_relop_dict()
        self.build_numeric_relop_dict()

    def __getitem__(self, row):
        return self._data[self._map_filtered[row]]

    def __len__(self):
        return len(self._map_filtered)

    def __iter__(self):
        for id in self._map_filtered:
            yield self._data[id]

    def iterall(self):
        for x in self._data:
            if x is not None:
                yield x

    def iterallids(self):
        idx = self.FIELD_MAP['id']
        for x in self.iterall():
            yield x[idx]

    # Search functions {{{

    def universal_set(self):
        return set([i[0] for i in self._data if i is not None])

    def build_date_relop_dict(self):
        '''
        Because the database dates have time in them, we can't use direct
        comparisons even when field_count == 3. The query has time = 0, but
        the database object has time == something. As such, a complete compare
        will almost never be correct.
        '''
        def relop_eq(db, query, field_count):
            if db.year == query.year:
                if field_count == 1:
                    return True
                if db.month == query.month:
                    if field_count == 2:
                        return True
                    return db.day == query.day
            return False

        def relop_gt(db, query, field_count):
            if db.year > query.year:
                return True
            if field_count > 1 and db.year == query.year:
                if db.month > query.month:
                    return True
                return field_count == 3 and db.month == query.month and db.day > query.day
            return False

        def relop_lt(db, query, field_count):
            if db.year < query.year:
                return True
            if field_count > 1 and db.year == query.year:
                if db.month < query.month:
                    return True
                return field_count == 3 and db.month == query.month and db.day < query.day
            return False

        def relop_ne(db, query, field_count):
            return not relop_eq(db, query, field_count)

        def relop_ge(db, query, field_count):
            return not relop_lt(db, query, field_count)

        def relop_le(db, query, field_count):
            return not relop_gt(db, query, field_count)

        self.date_search_relops = {
                            '=' :[1, relop_eq],
                            '>' :[1, relop_gt],
                            '<' :[1, relop_lt],
                            '!=':[2, relop_ne],
                            '>=':[2, relop_ge],
                            '<=':[2, relop_le]
                        }

    def get_dates_matches(self, location, query):
        matches = set([])
        if len(query) < 2:
            return matches

        if location == 'date':
            location = 'timestamp'
        loc = self.field_metadata[location]['rec_index']

        if query == 'false':
            for item in self._data:
                if item is None: continue
                if item[loc] is None or item[loc] <= UNDEFINED_DATE:
                    matches.add(item[0])
            return matches
        if query == 'true':
            for item in self._data:
                if item is None: continue
                if item[loc] is not None and item[loc] > UNDEFINED_DATE:
                    matches.add(item[0])
            return matches

        relop = None
        for k in self.date_search_relops.keys():
            if query.startswith(k):
                (p, relop) = self.date_search_relops[k]
                query = query[p:]
        if relop is None:
                (p, relop) = self.date_search_relops['=']

        if query == _('today'):
            qd = now()
            field_count = 3
        elif query == _('yesterday'):
            qd = now() - timedelta(1)
            field_count = 3
        elif query == _('thismonth'):
            qd = now()
            field_count = 2
        elif query.endswith(_('daysago')):
            num = query[0:-len(_('daysago'))]
            try:
                qd = now() - timedelta(int(num))
            except:
                raise ParseException(query, len(query), 'Number conversion error', self)
            field_count = 3
        else:
            try:
                qd = parse_date(query)
            except:
                raise ParseException(query, len(query), 'Date conversion error', self)
            if '-' in query:
                field_count = query.count('-') + 1
            else:
                field_count = query.count('/') + 1
        for item in self._data:
            if item is None or item[loc] is None: continue
            if relop(item[loc], qd, field_count):
                matches.add(item[0])
        return matches

    def build_numeric_relop_dict(self):
        self.numeric_search_relops = {
                        '=':[1, lambda r, q: r == q],
                        '>':[1, lambda r, q: r > q],
                        '<':[1, lambda r, q: r < q],
                        '!=':[2, lambda r, q: r != q],
                        '>=':[2, lambda r, q: r >= q],
                        '<=':[2, lambda r, q: r <= q]
                    }

    def get_numeric_matches(self, location, query):
        matches = set([])
        if len(query) == 0:
            return matches
        if query == 'false':
            query = '0'
        elif query == 'true':
            query = '!=0'
        relop = None
        for k in self.numeric_search_relops.keys():
            if query.startswith(k):
                (p, relop) = self.numeric_search_relops[k]
                query = query[p:]
        if relop is None:
                (p, relop) = self.numeric_search_relops['=']

        loc = self.field_metadata[location]['rec_index']
        dt = self.field_metadata[location]['datatype']
        if dt == 'int':
            cast = (lambda x: int (x))
            adjust = lambda x: x
        elif  dt == 'rating':
            cast = (lambda x: int (x))
            adjust = lambda x: x/2
        elif dt == 'float':
            cast = lambda x : float (x)
            adjust = lambda x: x

        if len(query) > 1:
            mult = query[-1:].lower()
            mult = {'k':1024.,'m': 1024.**2, 'g': 1024.**3}.get(mult, 1.0)
            if mult != 1.0:
                query = query[:-1]
        else:
            mult = 1.0
        try:
            q = cast(query) * mult
        except:
            return matches

        for item in self._data:
            if item is None:
                continue
            if not item[loc]:
                i = 0
            else:
                i = adjust(item[loc])
            if relop(i, q):
                matches.add(item[0])
        return matches

    def get_matches(self, location, query, allow_recursion=True):
        matches = set([])
        if query and query.strip():
            # get metadata key associated with the search term. Eliminates
            # dealing with plurals and other aliases
            location = self.field_metadata.search_term_to_key(location.lower().strip())
            if isinstance(location, list):
                if allow_recursion:
                    for loc in location:
                        matches |= self.get_matches(loc, query, allow_recursion=False)
                    return matches
                raise ParseException(query, len(query), 'Recursive query group detected', self)

            # take care of dates special case
            if location in self.field_metadata and \
                     self.field_metadata[location]['datatype'] == 'datetime':
                return self.get_dates_matches(location, query.lower())

            # take care of numbers special case
            if location in self.field_metadata and \
                    self.field_metadata[location]['datatype'] in ('rating', 'int', 'float'):
                return self.get_numeric_matches(location, query.lower())

            # everything else, or 'all' matches
            matchkind = CONTAINS_MATCH
            if (len(query) > 1):
                if query.startswith('\\'):
                    query = query[1:]
                elif query.startswith('='):
                    matchkind = EQUALS_MATCH
                    query = query[1:]
                elif query.startswith('~'):
                    matchkind = REGEXP_MATCH
                    query = query[1:]
            if matchkind != REGEXP_MATCH:
                # leave case in regexps because it can be significant e.g. \S \W \D
                query = query.lower()

            if not isinstance(query, unicode):
                query = query.decode('utf-8')

            db_col = {}
            exclude_fields = [] # fields to not check when matching against text.
            col_datatype = []
            is_multiple_cols = {}
            for x in range(len(self.FIELD_MAP)):
                col_datatype.append('')
            for x in self.field_metadata:
                if len(self.field_metadata[x]['search_terms']):
                    db_col[x] = self.field_metadata[x]['rec_index']
                    if self.field_metadata[x]['datatype'] not in \
                                                ['text', 'comments', 'series']:
                        exclude_fields.append(db_col[x])
                    col_datatype[db_col[x]] = self.field_metadata[x]['datatype']
                    is_multiple_cols[db_col[x]] = self.field_metadata[x]['is_multiple']

            try:
                rating_query = int(query) * 2
            except:
                rating_query = None

            location = [location] if location != 'all' else list(db_col.keys())
            for i, loc in enumerate(location):
                location[i] = db_col[loc]

            # get the tweak here so that the string lookup and compare aren't in the loop
            bools_are_tristate = tweaks['bool_custom_columns_are_tristate'] == 'yes'

            for loc in location: # location is now an array of field indices
                if loc == db_col['authors']:
                    ### DB stores authors with commas changed to bars, so change query
                    q = query.replace(',', '|');
                else:
                    q = query

                for item in self._data:
                    if item is None: continue

                    if col_datatype[loc] == 'bool': # complexity caused by the two-/three-value tweak
                        v = item[loc]
                        if not bools_are_tristate:
                            if v is None or not v: # item is None or set to false
                                if q in [_('no'), _('unchecked'), 'false']:
                                    matches.add(item[0])
                            else: # item is explicitly set to true
                                if q in [_('yes'), _('checked'), 'true']:
                                    matches.add(item[0])
                        else:
                            if v is None:
                                if q in [_('empty'), _('blank'), 'false']:
                                    matches.add(item[0])
                            elif not v: # is not None and false
                                if q in [_('no'), _('unchecked'), 'true']:
                                    matches.add(item[0])
                            else: # item is not None and true
                                if q in [_('yes'), _('checked'), 'true']:
                                    matches.add(item[0])
                        continue

                    if not item[loc]:
                        if q == 'false':
                            matches.add(item[0])
                        continue     # item is empty. No possible matches below
                    if q == 'false': # Field has something in it, so a false query does not match
                        continue

                    if q == 'true':
                        if isinstance(item[loc], basestring):
                            if item[loc].strip() == '':
                                continue
                        matches.add(item[0])
                        continue

                    if col_datatype[loc] == 'rating': # get here if 'all' query
                        if rating_query and rating_query == int(item[loc]):
                            matches.add(item[0])
                        continue

                    try: # a conversion below might fail
                        # relationals are not supported in 'all' queries
                        if col_datatype[loc] == 'float':
                            if float(query) == item[loc]:
                                matches.add(item[0])
                            continue
                        if col_datatype[loc] == 'int':
                            if int(query) == item[loc]:
                                matches.add(item[0])
                            continue
                    except:
                        # A conversion threw an exception. Because of the type,
                        # no further match is possible
                        continue

                    if loc not in exclude_fields: # time for text matching
                        if is_multiple_cols[loc] is not None:
                            vals = item[loc].split(is_multiple_cols[loc])
                        else:
                            vals = [item[loc]] ### make into list to make _match happy
                        if _match(q, vals, matchkind):
                            matches.add(item[0])
                            continue
        return matches

    def search(self, query, return_matches=False):
        ans = self.search_getting_ids(query, self.search_restriction)
        if return_matches:
            return ans
        self._map_filtered = ans

    def search_getting_ids(self, query, search_restriction):
        q = ''
        if not query or not query.strip():
            q = search_restriction
        else:
            q = query
            if search_restriction:
                q = u'%s (%s)' % (search_restriction, query)
        if not q:
            return list(self._map)
        matches = self.parse(q)
        tmap = list(itertools.repeat(False, len(self._data)))
        for x in matches:
            tmap[x] = True
        return [x for x in self._map if tmap[x]]

    def set_search_restriction(self, s):
        self.search_restriction = s

    # }}}

    def remove(self, id):
        self._data[id] = None
        try:
            self._map.remove(id)
        except ValueError:
            pass
        try:
            self._map_filtered.remove(id)
        except ValueError:
            pass

    def set(self, row, col, val, row_is_id=False):
        id = row if row_is_id else self._map_filtered[row]
        self._data[id][col] = val

    def get(self, row, col, row_is_id=False):
        id = row if row_is_id else self._map_filtered[row]
        return self._data[id][col]

    def index(self, id, cache=False):
        x = self._map if cache else self._map_filtered
        return x.index(id)

    def row(self, id):
        return self.index(id)

    def has_id(self, id):
        try:
            return self._data[id] is not None
        except IndexError:
            pass
        return False

    def refresh_ids(self, db, ids):
        '''
        Refresh the data in the cache for books identified by ids.
        Returns a list of affected rows or None if the rows are filtered.
        '''
        for id in ids:
            try:
                self._data[id] = db.conn.get('SELECT * from meta2 WHERE id=?', (id,))[0]
                self._data[id].append(db.has_cover(id, index_is_id=True))
                self._data[id].append(db.book_on_device_string(id))
            except IndexError:
                return None
        try:
            return map(self.row, ids)
        except ValueError:
            pass
        return None

    def books_added(self, ids, db):
        if not ids:
            return
        self._data.extend(repeat(None, max(ids)-len(self._data)+2))
        for id in ids:
            self._data[id] = db.conn.get('SELECT * from meta2 WHERE id=?', (id,))[0]
            self._data[id].append(db.has_cover(id, index_is_id=True))
            self._data[id].append(db.book_on_device_string(id))
        self._map[0:0] = ids
        self._map_filtered[0:0] = ids

    def books_deleted(self, ids):
        for id in ids:
            self.remove(id)

    def count(self):
        return len(self._map)

    def refresh_ondevice(self, db):
        ondevice_col = self.FIELD_MAP['ondevice']
        for item in self._data:
            if item is not None:
                item[ondevice_col] = db.book_on_device_string(item[0])

    def refresh(self, db, field=None, ascending=True):
        temp = db.conn.get('SELECT * FROM meta2')
        self._data = list(itertools.repeat(None, temp[-1][0]+2)) if temp else []
        for r in temp:
            self._data[r[0]] = r
        for item in self._data:
            if item is not None:
                item.append(db.has_cover(item[0], index_is_id=True))
                item.append(db.book_on_device_string(item[0]))
        self._map = [i[0] for i in self._data if i is not None]
        if field is not None:
            self.sort(field, ascending)
        self._map_filtered = list(self._map)
        if self.search_restriction:
            self.search('', return_matches=False)

    # Sorting functions {{{

    def sanitize_sort_field_name(self, field):
        field = field.lower().strip()
        if field not in self.field_metadata.iterkeys():
            if field in ('author', 'tag', 'comment'):
                field += 's'
        if   field == 'date': field = 'timestamp'
        elif field == 'title': field = 'sort'
        elif field == 'authors': field = 'author_sort'
        return field

    def sort(self, field, ascending, subsort=False):
        self.multisort([(field, ascending)])

    def multisort(self, fields=[], subsort=False):
        fields = [(self.sanitize_sort_field_name(x), bool(y)) for x, y in fields]
        keys = self.field_metadata.field_keys()
        fields = [x for x in fields if x[0] in keys]
        if subsort and 'sort' not in [x[0] for x in fields]:
            fields += [('sort', True)]
        if not fields:
            fields = [('timestamp', False)]

        keyg = SortKeyGenerator(fields, self.field_metadata, self._data)
        if len(fields) == 1:
            self._map.sort(key=keyg, reverse=not fields[0][1])
        else:
            self._map.sort(key=keyg)

        tmap = list(itertools.repeat(False, len(self._data)))
        for x in self._map_filtered:
            tmap[x] = True
        self._map_filtered = [x for x in self._map if tmap[x]]


class SortKey(object):

    def __init__(self, orders, values):
        self.orders, self.values = orders, values

    def __cmp__(self, other):
        for i, ascending in enumerate(self.orders):
            ans = cmp(self.values[i], other.values[i])
            if ans != 0:
                return ans * ascending
        return 0

class SortKeyGenerator(object):

    def __init__(self, fields, field_metadata, data):
        self.field_metadata = field_metadata
        self.orders = [-1 if x[1] else 1 for x in fields]
        self.entries = [(x[0], field_metadata[x[0]]) for x in fields]
        self.library_order = tweaks['title_series_sorting'] == 'library_order'
        self.data = data

    def __call__(self, record):
        values = tuple(self.itervals(self.data[record]))
        if len(values) == 1:
            return values[0]
        return SortKey(self.orders, values)

    def itervals(self, record):
        for name, fm in self.entries:
            dt = fm['datatype']
            val = record[fm['rec_index']]

            if dt == 'datetime':
                if val is None:
                    val = UNDEFINED_DATE

            elif dt == 'series':
                if val is None:
                    val = ('', 1)
                else:
                    val = val.lower()
                    if self.library_order:
                        val = title_sort(val)
                    sidx_fm = self.field_metadata[name + '_index']
                    sidx = record[sidx_fm['rec_index']]
                    val = (val, sidx)

            elif dt in ('text', 'comments'):
                if val is None:
                    val = ''
                val = val.lower()
            yield val

    # }}}


