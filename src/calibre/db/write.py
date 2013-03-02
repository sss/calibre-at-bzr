#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from functools import partial
from datetime import datetime

from calibre.constants import preferred_encoding, ispy3
from calibre.utils.date import (parse_only_date, parse_date, UNDEFINED_DATE,
                                isoformat)
if ispy3:
    unicode = str

# Convert data into values suitable for the db {{{

def sqlite_datetime(x):
    return isoformat(x, sep=' ') if isinstance(x, datetime) else x

def single_text(x):
    if x is None:
        return x
    if not isinstance(x, unicode):
        x = x.decode(preferred_encoding, 'replace')
    x = x.strip()
    return x if x else None

series_index_pat = re.compile(r'(.*)\s+\[([.0-9]+)\]$')

def get_series_values(val):
    if not val:
        return (val, None)
    match = series_index_pat.match(val.strip())
    if match is not None:
        idx = match.group(2)
        try:
            idx = float(idx)
            return (match.group(1).strip(), idx)
        except:
            pass
    return (val, None)

def multiple_text(sep, x):
    if x is None:
        return ()
    if isinstance(x, bytes):
        x = x.decode(preferred_encoding, 'replce')
    if isinstance(x, unicode):
        x = x.split(sep)
    x = (y.strip() for y in x if y.strip())
    return tuple(' '.join(y.split()) for y in x if y)

def adapt_datetime(x):
    if isinstance(x, (unicode, bytes)):
        x = parse_date(x, assume_utc=False, as_utc=False)
    return x

def adapt_date(x):
    if isinstance(x, (unicode, bytes)):
        x = parse_only_date(x)
    if x is None:
        x = UNDEFINED_DATE
    return x

def adapt_number(typ, x):
    if x is None:
        return None
    if isinstance(x, (unicode, bytes)):
        if x.lower() == 'none':
            return None
    return typ(x)

def adapt_bool(x):
    if isinstance(x, (unicode, bytes)):
        x = x.lower()
        if x == 'true':
            x = True
        elif x == 'false':
            x = False
        elif x == 'none':
            x = None
        else:
            x = bool(int(x))
    return x if x is None else bool(x)

def get_adapter(name, metadata):
    dt = metadata['datatype']
    if dt == 'text':
        if metadata['is_multiple']:
            ans = partial(multiple_text, metadata['is_multiple']['ui_to_list'])
        else:
            ans = single_text
    elif dt == 'series':
        ans = single_text
    elif dt == 'datetime':
        ans = adapt_date if name == 'pubdate' else adapt_datetime
    elif dt == 'int':
        ans = partial(adapt_number, int)
    elif dt == 'float':
        ans = partial(adapt_number, float)
    elif dt == 'bool':
        ans = adapt_bool
    elif dt == 'comments':
        ans = single_text
    elif dt == 'rating':
        ans = lambda x: None if x in {None, 0} else min(10., max(0., adapt_number(float, x)))
    elif dt == 'enumeration':
        ans = single_text
    elif dt == 'composite':
        ans = lambda x: x

    if name == 'title':
        return lambda x: ans(x) or _('Unknown')
    if name == 'author_sort':
        return lambda x: ans(x) or ''
    if name == 'authors':
        return lambda x: ans(x) or (_('Unknown'),)
    if name in {'timestamp', 'last_modified'}:
        return lambda x: ans(x) or UNDEFINED_DATE
    if name == 'series_index':
        return lambda x: 1.0 if ans(x) is None else ans(x)

    return ans
# }}}

# One-One fields {{{
def one_one_in_books(book_id_val_map, db, field, *args):
    'Set a one-one field in the books table'
    if book_id_val_map:
        sequence = tuple((sqlite_datetime(v), k) for k, v in book_id_val_map.iteritems())
        db.conn.executemany(
            'UPDATE books SET %s=? WHERE id=?'%field.metadata['column'], sequence)
        field.table.book_col_map.update(book_id_val_map)
    return set(book_id_val_map)

def one_one_in_other(book_id_val_map, db, field, *args):
    'Set a one-one field in the non-books table, like comments'
    deleted = tuple((k,) for k, v in book_id_val_map.iteritems() if v is None)
    if deleted:
        db.conn.executemany('DELETE FROM %s WHERE book=?'%field.metadata['table'],
                        deleted)
        for book_id in deleted:
            field.table.book_col_map.pop(book_id[0], None)
    updated = {k:v for k, v in book_id_val_map.iteritems() if v is not None}
    if updated:
        db.conn.executemany('INSERT OR REPLACE INTO %s(book,%s) VALUES (?,?)'%(
            field.metadata['table'], field.metadata['column']),
            tuple((k, sqlite_datetime(v)) for k, v in updated.iteritems()))
        field.table.book_col_map.update(updated)
    return set(book_id_val_map)

def custom_series_index(book_id_val_map, db, field, *args):
    series_field = field.series_field
    sequence = []
    for book_id, sidx in book_id_val_map.iteritems():
        if sidx is None:
            sidx = 1.0
        ids = series_field.ids_for_book(book_id)
        if ids:
            sequence.append((sidx, book_id, ids[0]))
            field.table.book_col_map[book_id] = sidx
    if sequence:
        db.conn.executemany('UPDATE %s SET %s=? WHERE book=? AND value=?'%(
                field.metadata['table'], field.metadata['column']), sequence)
    return {s[1] for s in sequence}
# }}}

# Many-One fields {{{

def safe_lower(x):
    try:
        return icu_lower(x)
    except (TypeError, ValueError, KeyError, AttributeError):
        return x

def get_db_id(val, db, m, table, kmap, rid_map, allow_case_changes,
              case_changes, val_map, sql_val_map=lambda x:x):
    ''' Get the db id for the value val. If val does not exist in the db it is
    inserted into the db. '''
    kval = kmap(val)
    item_id = rid_map.get(kval, None)
    if item_id is None:
        db.conn.execute('INSERT INTO %s(%s) VALUES (?)'%(
            m['table'], m['column']), (sql_val_map(val),))
        item_id = rid_map[kval] = db.conn.last_insert_rowid()
        table.id_map[item_id] = val
        table.col_book_map[item_id] = set()
    elif allow_case_changes and val != table.id_map[item_id]:
        case_changes[item_id] = val
    val_map[val] = item_id

def change_case(case_changes, dirtied, db, table, m, sql_val_map=lambda x:x):
    db.conn.executemany(
        'UPDATE %s SET %s=? WHERE id=?'%(m['table'], m['column']),
        tuple((sql_val_map(val), item_id) for item_id, val in case_changes.iteritems()))
    for item_id, val in case_changes.iteritems():
        table.id_map[item_id] = val
        dirtied.update(table.col_book_map[item_id])

def many_one(book_id_val_map, db, field, allow_case_change, *args):
    dirtied = set()
    m = field.metadata
    table = field.table
    dt = m['datatype']
    is_custom_series = dt == 'series' and table.name.startswith('#')

    # Map values to db ids, including any new values
    kmap = safe_lower if dt in {'text', 'series'} else lambda x:x
    rid_map = {kmap(item):item_id for item_id, item in table.id_map.iteritems()}
    val_map = {None:None}
    case_changes = {}
    for val in book_id_val_map.itervalues():
        if val is not None:
            get_db_id(val, db, m, table, kmap, rid_map, allow_case_change,
                    case_changes, val_map)

    if case_changes:
        change_case(case_changes, dirtied, db, table, m)

    book_id_item_id_map = {k:val_map[v] for k, v in book_id_val_map.iteritems()}

    # Ignore those items whose value is the same as the current value
    book_id_item_id_map = {k:v for k, v in book_id_item_id_map.iteritems()
        if v != table.book_col_map.get(k, None)}
    dirtied |= set(book_id_item_id_map)

    # Update the book->col and col->book maps
    deleted = set()
    updated = {}
    for book_id, item_id in book_id_item_id_map.iteritems():
        old_item_id = table.book_col_map.get(book_id, None)
        if old_item_id is not None:
            table.col_book_map[old_item_id].discard(book_id)
        if item_id is None:
            table.book_col_map.pop(book_id, None)
            deleted.add(book_id)
        else:
            table.book_col_map[book_id] = item_id
            table.col_book_map[item_id].add(book_id)
            updated[book_id] = item_id

    # Update the db link table
    if deleted:
        db.conn.executemany('DELETE FROM %s WHERE book=?'%table.link_table,
                            tuple((k,) for k in deleted))
    if updated:
        sql = (
            'DELETE FROM {0} WHERE book=?; INSERT INTO {0}(book,{1},extra) VALUES(?, ?, 1.0)'
            if is_custom_series else
            'DELETE FROM {0} WHERE book=?; INSERT INTO {0}(book,{1}) VALUES(?, ?)'
        )
        db.conn.executemany(sql.format(table.link_table, m['link_column']),
            tuple((book_id, book_id, item_id) for book_id, item_id in
                    updated.iteritems()))

    # Remove no longer used items
    remove = {item_id for item_id in table.id_map if not
              table.col_book_map.get(item_id, False)}
    if remove:
        db.conn.executemany('DELETE FROM %s WHERE id=?'%m['table'],
            tuple((item_id,) for item_id in remove))
        for item_id in remove:
            del table.id_map[item_id]
            table.col_book_map.pop(item_id, None)

    return dirtied
# }}}

# Many-Many fields {{{
def many_many(book_id_val_map, db, field, allow_case_change, *args):
    dirtied = set()
    m = field.metadata
    table = field.table
    dt = m['datatype']
    is_authors = field.name == 'authors'

    # Map values to db ids, including any new values
    kmap = safe_lower if dt == 'text' else lambda x:x
    rid_map = {kmap(item):item_id for item_id, item in table.id_map.iteritems()}
    sql_val_map = lambda x:x.replace(',', '|') if is_authors else lambda x:x
    val_map = {}
    case_changes = {}
    for vals in book_id_val_map.itervalues():
        for val in vals:
            get_db_id(val, db, m, table, kmap, rid_map, allow_case_change,
                      case_changes, val_map, sql_val_map=sql_val_map)

    if case_changes:
        change_case(case_changes, dirtied, db, table, m,
                    sql_val_map=sql_val_map)

    book_id_item_id_map = {k:tuple(val_map[v] for v in vals)
                           for k, vals in book_id_val_map.iteritems()}

    # Ignore those items whose value is the same as the current value
    book_id_item_id_map = {k:v for k, v in book_id_item_id_map.iteritems()
        if v != table.book_col_map.get(k, None)}
    dirtied |= set(book_id_item_id_map)

    # Update the book->col and col->book maps
    deleted = set()
    updated = {}
    for book_id, item_ids in book_id_item_id_map.iteritems():
        old_item_ids = table.book_col_map.get(book_id, None)
        if old_item_ids:
            for old_item_id in old_item_ids:
                table.col_book_map[old_item_id].discard(book_id)
        if item_ids:
            table.book_col_map[book_id] = item_ids
            for item_id in item_ids:
                table.col_book_map[item_id].add(book_id)
            updated[book_id] = item_ids
        else:
            table.book_col_map.pop(book_id, None)
            deleted.add(book_id)

    # Update the db link table
    if deleted:
        db.conn.executemany('DELETE FROM %s WHERE book=?'%table.link_table,
                            tuple((k,) for k in deleted))
    if updated:
        vals = tuple(
            (book_id, book_id, val) for book_id, vals in updated.iteritems()
            for val in vals
        )
        sql = (
            'DELETE FROM {0} WHERE book=?; INSERT INTO {0}(book,{1}) VALUES(?, ?)'
        )
        db.conn.executemany(sql.format(table.link_table, m['link_column']), vals)

    # Remove no longer used items
    remove = {item_id for item_id in table.id_map if not
              table.col_book_map.get(item_id, False)}
    if remove:
        db.conn.executemany('DELETE FROM %s WHERE id=?'%m['table'],
            tuple((item_id,) for item_id in remove))
        for item_id in remove:
            del table.id_map[item_id]
            table.col_book_map.pop(item_id, None)

    return dirtied


# }}}

def dummy(book_id_val_map, *args):
    return set()

class Writer(object):

    def __init__(self, field):
        self.adapter = get_adapter(field.name, field.metadata)
        self.name = field.name
        self.field = field
        dt = field.metadata['datatype']
        self.accept_vals = lambda x: True
        if dt == 'composite' or field.name in {
            'id', 'cover', 'size', 'path', 'formats', 'news'}:
            self.set_books_func = dummy
        elif self.name[0] == '#' and self.name.endswith('_index'):
            self.set_books_func = custom_series_index
        elif field.is_many_many:
            self.set_books_func = many_many
        elif field.is_many:
            self.set_books_func = (self.set_books_for_enum if dt ==
                                   'enumeration' else many_one)
        else:
            self.set_books_func = (one_one_in_books if field.metadata['table']
                                   == 'books' else one_one_in_other)
            if self.name in {'timestamp', 'uuid', 'sort'}:
                self.accept_vals = bool

    def set_books(self, book_id_val_map, db, allow_case_change=True):
        book_id_val_map = {k:self.adapter(v) for k, v in
                           book_id_val_map.iteritems() if self.accept_vals(v)}
        if not book_id_val_map:
            return set()
        dirtied = self.set_books_func(book_id_val_map, db, self.field,
                                      allow_case_change)
        return dirtied

    def set_books_for_enum(self, book_id_val_map, db, field,
                           allow_case_change):
        allowed = set(field.metadata['display']['enum_values'])
        book_id_val_map = {k:v for k, v in book_id_val_map.iteritems() if v is
                           None or v in allowed}
        if not book_id_val_map:
            return set()
        return many_one(book_id_val_map, db, field, False)


