##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
Backend that implements storage of ebooks in an sqlite database.
"""
import sqlite3 as sqlite
import os, datetime
from zlib import compress, decompress
from stat import ST_SIZE

class Concatenate(object):
    '''String concatenation aggregator for sqlite'''
    def __init__(self, sep=','):
        self.sep = sep
        self.ans = ''
        
    def step(self, value):
        self.ans += value + self.sep
    
    def finalize(self):
        if not self.ans:
            return None
        if self.sep:
            return self.ans[:-len(self.sep)]
        return self.ans

def _connect(path):
    conn =  sqlite.connect(path, detect_types=sqlite.PARSE_DECLTYPES|sqlite.PARSE_COLNAMES)
    conn.row_factory = sqlite.Row
    conn.create_aggregate('concat', 1, Concatenate)
    return conn

class LibraryDatabase(object):
    
    @staticmethod
    def books_in_old_database(path):
        '''
        Iterator over the books in the old pre 0.4.0 database.
        '''
        conn = sqlite.connect(path)
        cur = conn.execute('select * from books_meta;')
        book = cur.fetchone()
        while book:
            id = book[0]
            meta = { 'title':book[1], 'authors':book[2], 'publisher':book[3],
                     'tags':book[5], 'comments':book[7], 'rating':book[8],
                     'timestamp':datetime.datetime.strptime(book[6], '%Y-%m-%d %H:%M:%S'), 
                    }
            cover = {}
            query = conn.execute('select uncompressed_size, data from books_cover where id=?', (id,)).fetchone()
            if query:
                cover = {'uncompressed_size': query[0], 'data': query[1]}
            query = conn.execute('select extension, uncompressed_size, data from books_data where id=?', (id,)).fetchall()
            formats = {}
            for row in query:
                formats[row[0]] = {'uncompressed_size':row[1], 'data':row[2]}
            yield meta, cover, formats
            book = cur.fetchone()
            
    @staticmethod
    def import_old_database(path, conn):
        for book, cover, formats in LibraryDatabase.books_in_old_database(path):
            obj = conn.execute('INSERT INTO books(title, timestamp) VALUES (?,?)', 
                               (book['title'], book['timestamp']))
            id = obj.lastrowid
            authors = book['authors'].split('&')
            for a in authors:
                author = conn.execute('SELECT id from authors WHERE name=?', (a,)).fetchone()
                if author:
                    aid = author[0]
                else:
                    aid = conn.execute('INSERT INTO authors(name) VALUES (?)', (a,)).lastrowid
                conn.execute('INSERT INTO books_authors_link(book, author) VALUES (?,?)', (id, aid))
            candidate = conn.execute('SELECT id from publishers WHERE name=?', (book['publisher'],)).fetchone()
            if candidate:
                pid = candidate[0] if candidate else conn.execute('INSERT INTO publishers(name) VALUES (?)', 
                                                              (book['publisher'],)).lastrowid
                conn.execute('INSERT INTO books_publishers_link(book, publisher) VALUES (?,?)', (id, pid))
            candidate = conn.execute('SELECT id from ratings WHERE rating=?', (book['rating'],)).fetchone()
            if candidate:
                rid = candidate[0] if candidate else conn.execute('INSERT INTO ratings(rating) VALUES (?)', 
                                                              (book['rating'],)).lastrowid
                conn.execute('INSERT INTO books_ratings_link(book, rating) VALUES (?,?)', (id, rid))
            tags = book['tags']
            if tags:
                tags = tags.split(',')
            else:
                tags = []
            for a in tags:
                a = a.strip()
                if not a: continue
                tag = conn.execute('SELECT id from tags WHERE name=?', (a,)).fetchone()
                if tag:
                    tid = tag[0]
                else:
                    tid = conn.execute('INSERT INTO tags(name) VALUES (?)', (a,)).lastrowid
                conn.execute('INSERT INTO books_tags_link(book, tag) VALUES (?,?)', (id, tid))
            comments = book['comments']
            if comments:
                conn.execute('INSERT INTO comments(book, text) VALUES (?, ?)',
                             (id, comments))
            if cover:
                conn.execute('INSERT INTO covers(book, uncompressed_size, data) VALUES (?, ?, ?)',
                             (id, cover['uncompressed_size'], cover['data']))
            for format in formats.keys():
                conn.execute('INSERT INTO data(book, format, uncompressed_size, data) VALUES (?, ?, ?, ?)',
                             (id, format, formats[format]['uncompressed_size'], 
                              formats[format]['data']))
            conn.commit()
            
    
    @staticmethod
    def create_version1(conn):
        conn.executescript(\
        '''
        /**** books table *****/
        CREATE TABLE books ( id        INTEGER PRIMARY KEY AUTOINCREMENT,
                             title     TEXT NOT NULL DEFAULT 'Unknown' COLLATE NOCASE,
                             sort      TEXT COLLATE NOCASE,
                             timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                             uri       TEXT,
                             series_index INTEGER
                           );
        CREATE INDEX books_idx ON books (sort COLLATE NOCASE);
        CREATE TRIGGER books_insert_trg 
        AFTER INSERT ON books
        BEGIN
          UPDATE books SET sort=NEW.title WHERE id=NEW.id;
        END;
        CREATE TRIGGER books_update_trg
        AFTER UPDATE ON books
        BEGIN
          UPDATE books SET sort=NEW.title WHERE id=NEW.id;
        END;
        
        
        /***** authors table *****/
        CREATE TABLE authors ( id   INTEGER PRIMARY KEY,
                              name TEXT NOT NULL COLLATE NOCASE,
                              sort TEXT COLLATE NOCASE,
                              UNIQUE(name)
                             );
        CREATE INDEX authors_idx ON authors (sort COLLATE NOCASE);
        CREATE TRIGGER authors_insert_trg 
        AFTER INSERT ON authors
        BEGIN
          UPDATE authors SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TRIGGER authors_update_trg
        AFTER UPDATE ON authors
        BEGIN
          UPDATE authors SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TABLE books_authors_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          author INTEGER NOT NULL,
                                          UNIQUE(book, author)
                                        );
        CREATE INDEX books_authors_link_bidx ON books_authors_link (book);
        CREATE INDEX books_authors_link_aidx ON books_authors_link (author);
        
        CREATE TRIGGER fkc_insert_books_authors_link
        BEFORE INSERT ON books_authors_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: book not in books') 
              WHEN (SELECT id from authors WHERE id=NEW.author) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: author not in authors')
          END;
        END;
        CREATE TRIGGER fkc_update_books_authors_link_a
        BEFORE UPDATE OF book ON books_authors_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')              
            END;
        END;
        CREATE TRIGGER fkc_update_books_authors_link_b
        BEFORE UPDATE OF author ON books_authors_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from authors WHERE id=NEW.author) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: author not in authors')
            END;
        END;
        CREATE TRIGGER fkc_delete_books_authors_link
        BEFORE DELETE ON authors
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_authors_link WHERE book=OLD.book) > 0
                THEN RAISE(ABORT, 'Foreign key violation: author is still referenced')
            END;
        END;
        
        /***** publishers table *****/
        CREATE TABLE publishers ( id   INTEGER PRIMARY KEY,
                                  name TEXT NOT NULL COLLATE NOCASE,
                                  sort TEXT COLLATE NOCASE,
                                  UNIQUE(name)
                             );
        CREATE INDEX publishers_idx ON publishers (sort COLLATE NOCASE);
        CREATE TRIGGER publishers_insert_trg 
        AFTER INSERT ON publishers
        BEGIN
          UPDATE publishers SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TRIGGER publishers_update_trg
        AFTER UPDATE ON publishers
        BEGIN
          UPDATE publishers SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TABLE books_publishers_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          publisher INTEGER NOT NULL,
                                          UNIQUE(book, publisher)
                                        );
        CREATE INDEX books_publishers_link_bidx ON books_publishers_link (book);
        CREATE INDEX books_publishers_link_aidx ON books_publishers_link (publisher);
        
        CREATE TRIGGER fkc_insert_books_publishers_link
        BEFORE INSERT ON books_publishers_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: book not in books') 
              WHEN (SELECT id from publishers WHERE id=NEW.publisher) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: publisher not in publishers')
          END;
        END;
        CREATE TRIGGER fkc_update_books_publishers_link_a
        BEFORE UPDATE OF book ON books_publishers_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')              
            END;
        END;
        CREATE TRIGGER fkc_update_books_publishers_link_b
        BEFORE UPDATE OF publisher ON books_publishers_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from publishers WHERE id=NEW.publisher) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: publisher not in publishers')
            END;
        END;
        CREATE TRIGGER fkc_delete_books_publishers_link
        BEFORE DELETE ON publishers
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_publishers_link WHERE book=OLD.book) > 0
                THEN RAISE(ABORT, 'Foreign key violation: publisher is still referenced')
            END;
        END;
        
        /***** tags table *****/
        CREATE TABLE tags ( id   INTEGER PRIMARY KEY,
                            name TEXT NOT NULL COLLATE NOCASE,
                            UNIQUE (name)
                             );
        CREATE INDEX tags_idx ON tags (name COLLATE NOCASE);
        
        CREATE TABLE books_tags_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          tag INTEGER NOT NULL,
                                          UNIQUE(book, tag)
                                        );
        CREATE INDEX books_tags_link_bidx ON books_tags_link (book);
        CREATE INDEX books_tags_link_aidx ON books_tags_link (tag);
        
        CREATE TRIGGER fkc_insert_books_tags_link
        BEFORE INSERT ON books_tags_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: book not in books') 
              WHEN (SELECT id from tags WHERE id=NEW.tag) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: tag not in tags')
          END;
        END;
        CREATE TRIGGER fkc_update_books_tags_link_a
        BEFORE UPDATE OF book ON books_tags_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')              
            END;
        END;
        CREATE TRIGGER fkc_update_books_tags_link_b
        BEFORE UPDATE OF tag ON books_tags_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from tags WHERE id=NEW.tag) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: tag not in tags')
            END;
        END;
        CREATE TRIGGER fkc_delete_books_tags_link
        BEFORE DELETE ON tags
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_tags_link WHERE book=OLD.book) > 0
                THEN RAISE(ABORT, 'Foreign key violation: tag is still referenced')
            END;
        END;
        
        /***** series table *****/
        CREATE TABLE series ( id   INTEGER PRIMARY KEY,
                              name TEXT NOT NULL COLLATE NOCASE,
                              sort TEXT COLLATE NOCASE,
                              UNIQUE (name)
                             );
        CREATE INDEX series_idx ON series (sort COLLATE NOCASE);
        CREATE TRIGGER series_insert_trg 
        AFTER INSERT ON series
        BEGIN
          UPDATE series SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TRIGGER series_update_trg
        AFTER UPDATE ON series
        BEGIN
          UPDATE series SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TABLE books_series_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          series INTEGER NOT NULL,
                                          UNIQUE(book, series)
                                        );
        CREATE INDEX books_series_link_bidx ON books_series_link (book);
        CREATE INDEX books_series_link_aidx ON books_series_link (series);
        
        CREATE TRIGGER fkc_insert_books_series_link
        BEFORE INSERT ON books_series_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: book not in books') 
              WHEN (SELECT id from series WHERE id=NEW.series) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: series not in series')
          END;
        END;
        CREATE TRIGGER fkc_update_books_series_link_a
        BEFORE UPDATE OF book ON books_series_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')              
            END;
        END;
        CREATE TRIGGER fkc_update_books_series_link_b
        BEFORE UPDATE OF serie ON books_series_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from series WHERE id=NEW.series) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: series not in series')
            END;
        END;
        CREATE TRIGGER fkc_delete_books_series_link
        BEFORE DELETE ON series
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_series_link WHERE book=OLD.book) > 0
                THEN RAISE(ABORT, 'Foreign key violation: series is still referenced')
            END;
        END;
        
        /**** ratings table ****/
        
        CREATE TABLE ratings ( id   INTEGER PRIMARY KEY,
                               rating INTEGER CHECK(rating > -1 AND rating < 11),
                               UNIQUE (rating)                              
                             );
        INSERT INTO ratings (rating) VALUES (0);
        INSERT INTO ratings (rating) VALUES (1);
        INSERT INTO ratings (rating) VALUES (2);
        INSERT INTO ratings (rating) VALUES (3);
        INSERT INTO ratings (rating) VALUES (4);
        INSERT INTO ratings (rating) VALUES (5);
        INSERT INTO ratings (rating) VALUES (6);
        INSERT INTO ratings (rating) VALUES (7);
        INSERT INTO ratings (rating) VALUES (8);
        INSERT INTO ratings (rating) VALUES (9);
        INSERT INTO ratings (rating) VALUES (10);
        
        CREATE TABLE books_ratings_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          rating INTEGER NOT NULL,
                                          UNIQUE(book, rating)
                                        );
        CREATE INDEX books_ratings_link_bidx ON books_ratings_link (book);
        CREATE INDEX books_ratings_link_aidx ON books_ratings_link (rating);
        
        CREATE TRIGGER fkc_insert_books_ratings_link
        BEFORE INSERT ON books_ratings_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: book not in books') 
              WHEN (SELECT id from ratings WHERE id=NEW.rating) IS NULL 
              THEN RAISE(ABORT, 'Foreign key violation: rating not in ratings')
          END;
        END;
        CREATE TRIGGER fkc_update_books_ratings_link_a
        BEFORE UPDATE OF book ON books_ratings_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')              
            END;
        END;
        CREATE TRIGGER fkc_update_books_ratings_link_b
        BEFORE UPDATE OF rating ON books_ratings_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from ratings WHERE id=NEW.rating) IS NULL 
                THEN RAISE(ABORT, 'Foreign key violation: rating not in ratings')
            END;
        END;
        
        /**** data table ****/
        CREATE TABLE data ( id     INTEGER PRIMARY KEY,
                            book   INTEGER NON NULL,
                            format TEXT NON NULL COLLATE NOCASE,
                            uncompressed_size INTEGER NON NULL,
                            data   BLOB NON NULL,
                            UNIQUE(book, format)
                          );
        CREATE INDEX data_idx ON data (book);
        CREATE TRIGGER fkc_data_insert
        BEFORE INSERT ON data
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_data_update
        BEFORE UPDATE OF book ON data
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        
        /**** covers table ****/
        CREATE TABLE covers ( id INTEGER PRIMARY KEY,
                              book INTEGER NON NULL,
                              type TEXT NON NULL COLLATE NOCASE,
                              uncompressed_size INTEGER NON NULL,
                              data BLOB NON NULL,
                              UNIQUE(book)
                            );
        CREATE INDEX covers_idx ON covers (book);
        CREATE TRIGGER fkc_covers_insert
        BEFORE INSERT ON covers
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_covers_update
        BEFORE UPDATE OF book ON covers
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        
        /**** comments table ****/
        CREATE TABLE comments ( id INTEGER PRIMARY KEY,
                              book INTEGER NON NULL,
                              text TEXT NON NULL COLLATE NOCASE,
                              UNIQUE(book, text)
                            );
        CREATE INDEX comments_idx ON covers (book);
        CREATE TRIGGER fkc_comments_insert
        BEFORE INSERT ON comments
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_comments_update
        BEFORE UPDATE OF book ON comments
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        
        /**** Handle deletion of book ****/
        CREATE TRIGGER books_delete_trg
        AFTER DELETE ON books
        BEGIN
            DELETE FROM books_authors_link WHERE book=OLD.id;
            DELETE FROM books_publishers_link WHERE book=OLD.id;
            DELETE FROM books_ratings_link WHERE book=OLD.id;
            DELETE FROM books_series_link WHERE book=OLD.id;
            DELETE FROM books_tags_link WHERE book=OLD.id;
            DELETE FROM data WHERE book=OLD.id;
            DELETE FROM covers WHERE book=OLD.id;
            DELETE FROM comments WHERE book=OLD.id;
        END;
        
        /**** Views ****/
        CREATE VIEW meta AS
        SELECT id, title,
               (SELECT concat(name) FROM authors WHERE authors.id IN (SELECT author from books_authors_link WHERE book=books.id)) authors,
               (SELECT concat(name) FROM publishers WHERE publishers.id IN (SELECT publisher from books_publishers_link WHERE book=books.id)) publisher,
               (SELECT rating FROM ratings WHERE ratings.id IN (SELECT rating from books_ratings_link WHERE book=books.id)) rating,
               timestamp,
               (SELECT MAX(uncompressed_size) FROM data WHERE book=books.id) size
        FROM books;
        '''\
        )
        conn.commit()
    
    def __init__(self, dbpath):
        self.conn = _connect(dbpath)
        self.user_version = self.conn.execute('pragma user_version;').next()[0]
        if self.user_version == 0:
            LibraryDatabase.create_version1(self.conn)
            
if __name__ == '__main__':
    if os.path.exists('/tmp/test.sqlite'):
        os.remove('/tmp/test.sqlite')
    conn = _connect('/tmp/test.sqlite')
    from IPython.Shell import IPShellEmbed
    ipshell = IPShellEmbed([],
                       banner = 'Dropping into IPython',
                       exit_msg = 'Leaving Interpreter, back to program.')
    LibraryDatabase.create_version1(conn)
    LibraryDatabase.import_old_database('/home/kovid/library.db', conn)
    ipshell()
