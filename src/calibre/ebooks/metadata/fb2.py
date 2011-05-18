#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Anatoly Shipitsin <norguhtar at gmail.com>'

'''Read meta information from fb2 files'''

import os
from base64 import b64decode
from lxml import etree
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.chardet import xml_to_unicode
from calibre import guess_all_extensions

XLINK_NS     = 'http://www.w3.org/1999/xlink'
def XLINK(name):
    return '{%s}%s' % (XLINK_NS, name)


def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    XPath = lambda x : etree.XPath(x,
            namespaces={'fb2':'http://www.gribuser.ru/xml/fictionbook/2.0',
                'xlink':XLINK_NS})
    tostring = lambda x : etree.tostring(x, method='text',
            encoding=unicode).strip()
    parser = etree.XMLParser(recover=True, no_network=True)
    raw = stream.read()
    raw = xml_to_unicode(raw, strip_encoding_pats=True,
            assume_utf8=True)[0]
    root = etree.fromstring(raw, parser=parser)
    authors, author_sort = [], None
    for au in XPath('//fb2:author')(root):
        fname = lname = author = None
        fe = XPath('descendant::fb2:first-name')(au)
        if fe:
            fname = tostring(fe[0])
            author = fname
        le = XPath('descendant::fb2:last-name')(au)
        if le:
            lname = tostring(le[0])
            if author:
                author += ' '+lname
            else:
                author = lname
        if author:
            authors.append(author)
        if len(authors) == 1 and author is not None:
            if lname:
                author_sort = lname
            if fname:
                if author_sort: author_sort += ', '+fname
                else: author_sort = fname
    title = os.path.splitext(os.path.basename(getattr(stream, 'name',
        _('Unknown'))))[0]
    for x in XPath('//fb2:book-title')(root):
        title = tostring(x)
        break
    comments = ''
    for x in XPath('//fb2:annotation')(root):
        comments += tostring(x)
    if not comments:
        comments = None
    tags = list(map(tostring, XPath('//fb2:genre')(root)))

    cp = XPath('//fb2:coverpage')(root)
    cdata = None
    if cp:
        cimage = XPath('descendant::fb2:image[@xlink:href]')(cp[0])
        if cimage:
            id = cimage[0].get(XLINK('href')).replace('#', '')
            binary = XPath('//fb2:binary[@id="%s"]'%id)(root)
            if binary:
                mt = binary[0].get('content-type', 'image/jpeg')
                exts = guess_all_extensions(mt)
                if not exts:
                    exts = ['.jpg']
                cdata = (exts[0][1:], b64decode(tostring(binary[0])))

    series = None
    series_index = 1.0
    for x in XPath('//fb2:sequence')(root):
        series = x.get('name', None)
        if series is not None:
            series_index = x.get('number', 1.0)
            break
    mi = MetaInformation(title, authors)
    mi.comments = comments
    mi.author_sort = author_sort
    if tags:
        mi.tags = tags
    mi.series = series
    mi.series_index = series_index
    if cdata:
        mi.cover_data = cdata
    return mi
