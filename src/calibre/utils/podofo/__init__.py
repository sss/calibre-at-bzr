#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.constants import plugins, preferred_encoding
from calibre.ebooks.metadata import MetaInformation, string_to_authors, \
    authors_to_string

podofo, podofo_err = plugins['podofo']

class Unavailable(Exception): pass

def get_metadata(stream):
    if not podofo:
        raise Unavailable(podofo_err)
    raw = stream.read()
    stream.seek(0)
    p = podofo.PDFDoc()
    p.load(raw)
    title = p.title
    if not title:
        title = getattr(stream, 'name', _('Unknown'))
        title = os.path.splitext(os.path.basename(title))[0]
    author = p.author
    authors = string_to_authors(author) if author else  [_('Unknown')]
    mi = MetaInformation(title, authors)
    creator = p.creator
    if creator:
        mi.book_producer = creator
    return mi

def prep(val):
    if not val:
        return u''
    if not isinstance(val, unicode):
        val = val.decode(preferred_encoding, 'replace')
    return val.strip()

def set_metadata(stream, mi):
    if not podofo:
        raise Unavailable(podofo_err)
    raw = stream.read()
    p = podofo.PDFDoc()
    p.load(raw)
    title = prep(mi.title)
    touched = False
    if title:
        p.title = title
        touched = True

    author = prep(authors_to_string(mi.authors))
    if author:
        p.author = author
        touched = True

    bkp = prep(mi.book_producer)
    if bkp:
        p.creator = bkp
        touched = True

    if touched:
        from calibre.ptempfile import TemporaryFile
        with TemporaryFile('_pdf_set_metadata.pdf') as f:
            p.save(f)
            raw = open(f, 'rb').read()
            stream.seek(0)
            stream.truncate()
            stream.write(raw)
            stream.flush()
            stream.seek(0)

if __name__ == '__main__':
    f = '/tmp/t.pdf'
    import StringIO
    stream = StringIO.StringIO(open(f).read())
    mi = get_metadata(open(f))
    print
    print 'Original metadata:'
    print mi
    mi.title = 'Test title'
    mi.authors = ['Test author', 'author2']
    mi.book_producer = 'calibre'
    set_metadata(stream, mi)
    open('/tmp/x.pdf', 'wb').write(stream.getvalue())
    print
    print 'New pdf written to /tmp/x.pdf'


