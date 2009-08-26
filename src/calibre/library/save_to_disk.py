#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, traceback, cStringIO, re

from calibre.utils.config import Config, StringConfig
from calibre.utils.filenames import shorten_components_to, supports_long_names, \
                                    ascii_filename, sanitize_file_name
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ebooks.metadata.meta import set_metadata
from calibre.constants import preferred_encoding, filesystem_encoding

from calibre import strftime

DEFAULT_TEMPLATE = '{author_sort}/{title}/{title} - {authors}'
FORMAT_ARG_DESCS = dict(
        title=_('The title'),
        authors=_('The authors'),
        author_sort=_('The author sort string'),
        tags=_('The tags'),
        series=_('The series'),
        series_index=_('The series number'),
        rating=_('The rating'),
        isbn=_('The ISBN'),
        publisher=_('The publisher'),
        timestamp=_('The date'),
        pubdate=_('The published date'),
        id=_('The calibre internal id')
        )

FORMAT_ARGS = {}
for x in FORMAT_ARG_DESCS:
    FORMAT_ARGS[x] = ''


def config(defaults=None):
    if defaults is None:
        c = Config('save_to_disk', _('Options to control saving to disk'))
    else:
        c = StringConfig(defaults)

    x = c.add_opt
    x('update_metadata', default=True,
            help=_('Normally, calibre will update the metadata in the saved files from what is'
            ' in the calibre library. Makes saving to disk slower.'))
    x('write_opf', default=True,
            help=_('Normally, calibre will write the metadata into a separate OPF file along with the'
                ' actual e-book files.'))
    x('save_cover', default=True,
            help=_('Normally, calibre will save the cover in a separate file along with the '
                'actual e-book file(s).'))
    x('formats', default='all',
            help=_('Comma separated list of formats to save for each book.'
                ' By default all available books are saved.'))
    x('template', default=DEFAULT_TEMPLATE,
            help=_('The template to control the filename and directory structure of the saved files. '
                'Default is "%s" which will save books into a per-author '
                'subdirectory with filenames containing title and author. '
                'Available controls are: {%s}')%(DEFAULT_TEMPLATE, ', '.join(FORMAT_ARGS)))
    x('asciiize', default=True,
            help=_('Normally, calibre will convert all non English characters into English equivalents '
                'for the file names. '
                'WARNING: If you turn this off, you may experience errors when '
                'saving, depending on how well the filesystem you are saving '
                'to supports unicode.'))
    x('timefmt', default='%b, %Y',
            help=_('The format in which to display dates. %d - day, %b - month, '
                '%Y - year. Default is: %b, %Y'))
    x('to_lowercase', default=False,
            help=_('Convert paths to lowercase.'))
    x('replace_whitespace', default=False,
            help=_('Replace whitespace with underscores.'))
    return c

def preprocess_template(template):
    template = template.replace('//', '/')
    template = template.replace('{author}', '{authors}')
    template = template.replace('{tag}', '{tags}')
    if not isinstance(template, unicode):
        template = template.decode(preferred_encoding, 'replace')
    return template

def get_components(template, mi, id, timefmt='%b %Y', length=250,
        sanitize_func=ascii_filename, replace_whitespace=False,
        to_lowercase=False):
    format_args = dict(**FORMAT_ARGS)
    if mi.title:
        format_args['title'] = mi.title
    if mi.authors:
        format_args['authors'] = mi.format_authors()
    if mi.author_sort:
        format_args['author_sort'] = mi.author_sort
    if mi.tags:
        format_args['tags'] = mi.format_tags()
    if mi.series:
        format_args['series'] = mi.series
        if mi.series_index is not None:
            format_args['series_index'] = mi.format_series_index()
    if mi.rating is not None:
        format_args['rating'] = mi.format_rating()
    if mi.isbn:
        format_args['isbn'] = mi.isbn
    if mi.publisher:
        format_args['publisher'] = mi.publisher
    if hasattr(mi.timestamp, 'timetuple'):
        format_args['timestamp'] = strftime(timefmt, mi.timestamp.timetuple())
    if hasattr(mi.pubdate, 'timetuple'):
        format_args['timestamp'] = strftime(timefmt, mi.pubdate.timetuple())
    format_args['id'] = str(id)
    components = [x.strip() for x in template.split('/') if x.strip()]
    components = [x.format(**format_args).strip() for x in components]
    components = [sanitize_func(x) for x in components if x]
    if not components:
        components = [str(id)]
    components = [x.encode(filesystem_encoding, 'replace') if isinstance(x,
        unicode) else x for x in components]
    if to_lowercase:
        components = [x.lower() for x in components]
    if replace_whitespace:
        components = [re.sub(r'\s', '_', x) for x in components]

    return shorten_components_to(length, components)


def save_book_to_disk(id, db, root, opts, length):
    mi = db.get_metadata(id, index_is_id=True)

    available_formats = db.formats(id, index_is_id=True)
    if not available_formats:
        available_formats = []
    else:
        available_formats = [x.lower().strip() for x in
                available_formats.split(',')]
    if opts.formats == 'all':
        asked_formats = available_formats
    else:
        asked_formats = [x.lower().strip() for x in opts.formats.split(',')]
    formats = set(available_formats).intersection(set(asked_formats))
    if not formats:
        return True, id, mi.title

    components = get_components(opts.template, mi, id, opts.timefmt, length,
            ascii_filename if opts.asciiize else sanitize_file_name,
            to_lowercase=opts.to_lowercase,
            replace_whitespace=opts.replace_whitespace)
    base_path = os.path.join(root, *components)
    base_name = os.path.basename(base_path)
    dirpath = os.path.dirname(base_path)
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)

    cdata = db.cover(id, index_is_id=True)
    if opts.save_cover:
        if cdata is not None:
            with open(base_path+'.jpg', 'wb') as f:
                f.write(cdata)
            mi.cover = base_name+'.jpg'
        else:
            mi.cover = None

    if opts.write_opf:
        opf = metadata_to_opf(mi)
        with open(base_path+'.opf', 'wb') as f:
            f.write(opf)

    if cdata is not None:
        mi.cover_data = ('jpg', cdata)
    mi.cover = None

    written = False
    for fmt in formats:
        data = db.format(id, fmt, index_is_id=True)
        if data is None:
            continue
        else:
            written = True
        if opts.update_metadata:
            stream = cStringIO.StringIO()
            stream.write(data)
            stream.seek(0)
            try:
                set_metadata(stream, mi, fmt)
            except:
                traceback.print_exc()
            stream.seek(0)
            data = stream.read()
        fmt_path = base_path+'.'+str(fmt)
        with open(fmt_path, 'wb') as f:
            f.write(data)

    return not written, id, mi.title



def save_to_disk(db, ids, root, opts=None, callback=None):
    '''
    Save books from the database ``db`` to the path specified by ``root``.

    :param:`ids` iterable of book ids to save from the database.
    :param:`callback` is an optional callable that is called on after each
    book is processed with the arguments: id, title, failed, traceback.
    If the callback returns False, further processing is terminated and
    the function returns.
    :return: A list of failures. Each element of the list is a tuple
    (id, title, traceback)
    '''
    if opts is None:
        opts = config().parse()
    if isinstance(root, unicode):
        root = root.encode(filesystem_encoding)
    root = os.path.abspath(root)

    opts.template = preprocess_template(opts.template)
    length = 1000 if supports_long_names(root) else 250
    length -= len(root)
    if length < 5:
        raise ValueError('%r is too long.'%root)
    failures = []
    for x in ids:
        tb = ''
        try:
            failed, id, title = save_book_to_disk(x, db, root, opts, length)
            tb = _('Requested formats not available')
        except:
            failed, id, title = True, x, db.title(x, index_is_id=True)
            tb = traceback.format_exc()
        if failed:
            failures.append((id, title, tb))
        if callable(callback):
            if not callback(int(id), title, failed, tb):
                break
    return failures


