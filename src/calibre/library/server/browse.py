#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import operator, os, json
from binascii import hexlify, unhexlify
from urllib import quote, unquote

import cherrypy

from calibre.constants import filesystem_encoding
from calibre import isbytestring, force_unicode, fit_image, \
        prepare_string_for_xml as xml
from calibre.utils.ordered_dict import OrderedDict
from calibre.utils.filenames import ascii_filename
from calibre.utils.config import prefs
from calibre.utils.magick import Image
from calibre.library.comments import comments_to_html
from calibre.library.server import custom_fields_to_display
from calibre.library.field_metadata import category_icon_map

def render_book_list(ids, prefix, suffix=''): # {{{
    pages = []
    num = len(ids)
    pos = 0
    delta = 25
    while ids:
        page = list(ids[:delta])
        pages.append((page, pos))
        ids = ids[delta:]
        pos += len(page)
    page_template = u'''\
            <div class="page" id="page{0}">
                <div class="load_data" title="{1}">
                    <span class="url" title="{prefix}/browse/booklist_page"></span>
                    <span class="start" title="{start}"></span>
                    <span class="end" title="{end}"></span>
                </div>
                <div class="loading"><img src="{prefix}/static/loading.gif" /> {2}</div>
                <div class="loaded"></div>
            </div>
            '''
    rpages = []
    for i, x in enumerate(pages):
        pg, pos = x
        ld = xml(json.dumps(pg), True)
        rpages.append(page_template.format(i, ld,
            xml(_('Loading, please wait')) + '&hellip;',
            start=pos+1, end=pos+len(pg), prefix=prefix))
    rpages = u'\n\n'.join(rpages)

    templ = u'''\
            <h3>{0} {suffix}</h3>
            <div id="booklist">
                <div class="listnav topnav">
                {navbar}
                </div>
                {pages}
                <div class="listnav bottomnav">
                {navbar}
                </div>
            </div>
            '''

    navbar = u'''\
        <div class="navleft">
            <a href="#" onclick="first_page(); return false;">{first}</a>
            <a href="#" onclick="previous_page(); return false;">{previous}</a>
        </div>
        <div class="navmiddle">
            <span class="start">0</span> to <span class="end">0</span> of {num}
        </div>
        <div class="navright">
            <a href="#" onclick="next_page(); return false;">{next}</a>
            <a href="#" onclick="last_page(); return false;">{last}</a>
        </div>
    '''.format(first=_('First'), last=_('Last'), previous=_('Previous'),
            next=_('Next'), num=num)

    return templ.format(_('Browsing %d books')%num, suffix=suffix,
            pages=rpages, navbar=navbar)

# }}}

def utf8(x): # {{{
    if isinstance(x, unicode):
        x = x.encode('utf-8')
    return x
# }}}

def render_rating(rating, url_prefix, container='span', prefix=None): # {{{
    if rating < 0.1:
        return '', ''
    added = 0
    if prefix is None:
        prefix = _('Average rating')
    rstring = xml(_('%s: %.1f stars')% (prefix, rating if rating else 0.0),
            True)
    ans = ['<%s class="rating">' % (container)]
    for i in range(5):
        n = rating - added
        x = 'half'
        if n <= 0.1:
            x = 'off'
        elif n >= 0.9:
            x = 'on'
        ans.append(
            u'<img alt="{0}" title="{0}" src="{2}/static/star-{1}.png" />'.format(
                rstring, x, url_prefix))
        added += 1
    ans.append('</%s>'%container)
    return u''.join(ans), rstring

# }}}

def get_category_items(category, items, restriction, datatype, prefix): # {{{

    if category == 'search':
        items = [x for x in items if x.name != restriction]

    def item(i):
        templ = (u'<div title="{4}" class="category-item">'
                '<div class="category-name">'
                '<a href="{5}{3}" title="{4}">{0}</a></div>'
                '<div>{1}</div>'
                '<div>{2}</div></div>')
        rating, rstring = render_rating(i.avg_rating, prefix)
        name = xml(i.name)
        if datatype == 'rating':
            name = xml(_('%d stars')%int(i.avg_rating))
        id_ = i.id
        if id_ is None:
            id_ = hexlify(force_unicode(name).encode('utf-8'))
        id_ = xml(str(id_))
        desc = ''
        if i.count > 0:
            desc += '[' + _('%d books')%i.count + ']'
        q = i.category
        if not q:
            q = category
        href = '/browse/matches/%s/%s'%(quote(q), quote(id_))
        return templ.format(xml(name), rating,
                xml(desc), xml(href, True), rstring, prefix)

    items = list(map(item, items))
    return '\n'.join(['<div class="category-container">'] + items + ['</div>'])

# }}}

class Endpoint(object): # {{{
    'Manage encoding, mime-type, last modified, cookies, etc.'

    def __init__(self, mimetype='text/html; charset=utf-8', sort_type='category'):
        self.mimetype = mimetype
        self.sort_type = sort_type
        self.sort_kwarg = sort_type + '_sort'
        self.sort_cookie_name = 'calibre_browse_server_sort_'+self.sort_type

    def __call__(eself, func):

        def do(self, *args, **kwargs):
            if 'json' not in eself.mimetype:
                sort_val = None
                cookie = cherrypy.request.cookie
                if cookie.has_key(eself.sort_cookie_name):
                    sort_val = cookie[eself.sort_cookie_name].value
                kwargs[eself.sort_kwarg] = sort_val

            # Remove AJAX caching disabling jquery workaround arg
            kwargs.pop('_', None)

            ans = func(self, *args, **kwargs)
            cherrypy.response.headers['Content-Type'] = eself.mimetype
            updated = self.db.last_modified()
            cherrypy.response.headers['Last-Modified'] = \
                self.last_modified(max(updated, self.build_time))
            ans = utf8(ans)
            return ans

        do.__name__ = func.__name__

        return do
# }}}

class BrowseServer(object):

    def add_routes(self, connect):
        base_href = '/browse'
        connect('browse', base_href, self.browse_catalog)
        connect('browse_catalog', base_href+'/category/{category}',
                self.browse_catalog)
        connect('browse_category_group',
                base_href+'/category_group/{category}/{group}',
                self.browse_category_group)
        connect('browse_matches',
                base_href+'/matches/{category}/{cid}',
                self.browse_matches)
        connect('browse_booklist_page',
                base_href+'/booklist_page',
                self.browse_booklist_page)
        connect('browse_search', base_href+'/search',
                self.browse_search)
        connect('browse_details', base_href+'/details/{id}',
                self.browse_details)
        connect('browse_book', base_href+'/book/{id}',
                self.browse_book)
        connect('browse_category_icon', base_href+'/icon/{name}',
                self.browse_icon)

    # Templates {{{
    def browse_template(self, sort, category=True, initial_search=''):

        if not hasattr(self, '__browse_template__') or \
                self.opts.develop:
            self.__browse_template__ = \
                P('content_server/browse/browse.html', data=True).decode('utf-8')

        ans = self.__browse_template__
        scn = 'calibre_browse_server_sort_'

        if category:
            sort_opts = [('rating', _('Average rating')), ('name',
                _('Name')), ('popularity', _('Popularity'))]
            scn += 'category'
        else:
            scn += 'list'
            fm = self.db.field_metadata
            sort_opts, added = [], set([])
            displayed_custom_fields = custom_fields_to_display(self.db)
            for x in fm.sortable_field_keys():
                if x in ('ondevice', 'formats', 'sort'):
                    continue
                if fm[x]['is_custom'] and x not in displayed_custom_fields:
                    continue
                if x == 'comments' or fm[x]['datatype'] == 'comments':
                    continue
                n = fm[x]['name']
                if n not in added:
                    added.add(n)
                    sort_opts.append((x, n))

        ans = ans.replace('{sort_select_label}', xml(_('Sort by')+':'))
        ans = ans.replace('{sort_cookie_name}', scn)
        ans = ans.replace('{prefix}', self.opts.url_prefix)
        opts = ['<option %svalue="%s">%s</option>' % (
            'selected="selected" ' if k==sort else '',
            xml(k), xml(n), ) for k, n in
                sorted(sort_opts, key=operator.itemgetter(1)) if k and n]
        ans = ans.replace('{sort_select_options}', ('\n'+' '*20).join(opts))
        lp = self.db.library_path
        if isbytestring(lp):
            lp = force_unicode(lp, filesystem_encoding)
        ans = ans.replace('{library_name}', xml(os.path.basename(lp)))
        ans = ans.replace('{library_path}', xml(lp, True))
        ans = ans.replace('{initial_search}', initial_search)
        return ans

    @property
    def browse_summary_template(self):
        if not hasattr(self, '__browse_summary_template__') or \
                self.opts.develop:
            self.__browse_summary_template__ = \
                P('content_server/browse/summary.html', data=True).decode('utf-8')
        return self.__browse_summary_template__.replace('{prefix}',
                self.opts.url_prefix)

    @property
    def browse_details_template(self):
        if not hasattr(self, '__browse_details_template__') or \
                self.opts.develop:
            self.__browse_details_template__ = \
                P('content_server/browse/details.html', data=True).decode('utf-8')
        return self.__browse_details_template__.replace('{prefix}',
                self.opts.url_prefix)

    # }}}

    # Catalogs {{{
    def browse_icon(self, name='blank.png'):
        cherrypy.response.headers['Content-Type'] = 'image/png'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(self.build_time)

        if not hasattr(self, '__browse_icon_cache__'):
            self.__browse_icon_cache__ = {}
        if name not in self.__browse_icon_cache__:
            try:
                data = I(name, data=True)
            except:
                raise cherrypy.HTTPError(404, 'no icon named: %r'%name)
            img = Image()
            img.load(data)
            width, height = img.size
            scaled, width, height = fit_image(width, height, 48, 48)
            if scaled:
                img.size = (width, height)

            self.__browse_icon_cache__[name] = img.export('png')
        return self.__browse_icon_cache__[name]

    def browse_toplevel(self):
        categories = self.categories_cache()
        category_meta = self.db.field_metadata
        cats = [
                (_('Newest'), 'newest', 'forward.png'),
                (_('All books'), 'allbooks', 'book.png'),
                ]

        def getter(x):
            return category_meta[x]['name'].lower()

        displayed_custom_fields = custom_fields_to_display(self.db)
        for category in sorted(categories,
                    cmp=lambda x,y: cmp(getter(x), getter(y))):
            if len(categories[category]) == 0:
                continue
            if category == 'formats':
                continue
            meta = category_meta.get(category, None)
            if meta is None:
                continue
            if meta['is_custom'] and category not in displayed_custom_fields:
                continue
            # get the icon files
            if category in category_icon_map:
                icon = category_icon_map[category]
            elif meta['is_custom']:
                icon = category_icon_map[':custom']
            elif meta['kind'] == 'user':
                icon = category_icon_map[':user']
            else:
                icon = 'blank.png'
            cats.append((meta['name'], category, icon))

        cats = [('<li><a title="{2} {0}" href="/browse/category/{1}">&nbsp;</a>'
                 '<img src="{3}{src}" alt="{0}" />'
                 '<span class="label">{0}</span>'
                 '</li>')
                .format(xml(x, True), xml(quote(y)), xml(_('Browse books by')),
                    self.opts.url_prefix, src='/browse/icon/'+z)
                for x, y, z in cats]

        main = '<div class="toplevel"><h3>{0}</h3><ul>{1}</ul></div>'\
                .format(_('Choose a category to browse by:'), '\n\n'.join(cats))
        return self.browse_template('name').format(title='',
                    script='toplevel();', main=main)

    def browse_sort_categories(self, items, sort):
        if sort not in ('rating', 'name', 'popularity'):
            sort = 'name'
        def sorter(x):
            ans = getattr(x, 'sort', x.name)
            if hasattr(ans, 'upper'):
                ans = ans.upper()
            return ans
        items.sort(key=sorter)
        if sort == 'popularity':
            items.sort(key=operator.attrgetter('count'), reverse=True)
        elif sort == 'rating':
            items.sort(key=operator.attrgetter('avg_rating'), reverse=True)
        return sort

    def browse_category(self, category, sort):
        categories = self.categories_cache()
        if category not in categories:
            raise cherrypy.HTTPError(404, 'category not found')
        category_meta = self.db.field_metadata
        category_name = category_meta[category]['name']
        datatype = category_meta[category]['datatype']


        items = categories[category]
        sort = self.browse_sort_categories(items, sort)

        script = 'true'

        if len(items) <= self.opts.max_opds_ungrouped_items:
            script = 'false'
            items = get_category_items(category, items,
                    self.search_restriction_name, datatype,
                    self.opts.url_prefix)
        else:
            getter = lambda x: unicode(getattr(x, 'sort', x.name))
            starts = set([])
            for x in items:
                val = getter(x)
                if not val:
                    val = u'A'
                starts.add(val[0].upper())
            category_groups = OrderedDict()
            for x in sorted(starts):
                category_groups[x] = len([y for y in items if
                    getter(y).upper().startswith(x)])
            items = [(u'<h3 title="{0}"><a class="load_href" title="{0}"'
                      u' href="{4}{3}"><strong>{0}</strong> [{2}]</a></h3><div>'
                      u'<div class="loaded" style="display:none"></div>'
                      u'<div class="loading"><img alt="{1}" src="{4}/static/loading.gif" /><em>{1}</em></div>'
                      u'</div>').format(
                        xml(s, True),
                        xml(_('Loading, please wait'))+'&hellip;',
                        unicode(c),
                        xml(u'/browse/category_group/%s/%s'%(category, s), True),
                        self.opts.url_prefix)
                    for s, c in category_groups.items()]
            items = '\n\n'.join(items)
            items = u'<div id="groups">\n{0}</div>'.format(items)



        script = 'category(%s);'%script

        main = u'''
            <div class="category">
                <h3>{0}</h3>
                    <a class="navlink" href="{3}/browse"
                        title="{2}">{2}&nbsp;&uarr;</a>
                {1}
            </div>
        '''.format(
                xml(_('Browsing by')+': ' + category_name), items,
                xml(_('Up'), True), self.opts.url_prefix)

        return self.browse_template(sort).format(title=category_name,
                script=script, main=main)

    @Endpoint(mimetype='application/json; charset=utf-8')
    def browse_category_group(self, category=None, group=None, sort=None):
        if sort == 'null':
            sort = None
        if sort not in ('rating', 'name', 'popularity'):
            sort = 'name'
        categories = self.categories_cache()
        if category not in categories:
            raise cherrypy.HTTPError(404, 'category not found')

        category_meta = self.db.field_metadata
        datatype = category_meta[category]['datatype']

        if not group:
            raise cherrypy.HTTPError(404, 'invalid group')

        items = categories[category]
        entries = []
        getter = lambda x: unicode(getattr(x, 'sort', x.name))
        for x in items:
            val = getter(x)
            if not val:
                val = u'A'
            if val.upper().startswith(group):
                entries.append(x)

        sort = self.browse_sort_categories(entries, sort)
        entries = get_category_items(category, entries,
                self.search_restriction_name, datatype,
                self.opts.url_prefix)
        return json.dumps(entries, ensure_ascii=False)


    @Endpoint()
    def browse_catalog(self, category=None, category_sort=None):
        'Entry point for top-level, categories and sub-categories'
        prefix = '' if self.is_wsgi else self.opts.url_prefix
        if category == None:
            ans = self.browse_toplevel()
        elif category == 'newest':
            raise cherrypy.InternalRedirect(prefix +
                    '/browse/matches/newest/dummy')
        elif category == 'allbooks':
            raise cherrypy.InternalRedirect(prefix +
                    '/browse/matches/allbooks/dummy')
        else:
            ans = self.browse_category(category, category_sort)

        return ans

    # }}}

    # Book Lists {{{

    def browse_sort_book_list(self, items, sort):
        fm = self.db.field_metadata
        keys = frozenset(fm.sortable_field_keys())
        if sort not in keys:
            sort = 'title'
        self.sort(items, 'title', True)
        if sort != 'title':
            ascending = fm[sort]['datatype'] not in ('rating', 'datetime',
                    'series')
            self.sort(items, sort, ascending)
        return sort

    @Endpoint(sort_type='list')
    def browse_matches(self, category=None, cid=None, list_sort=None):
        if list_sort:
            list_sort = unquote(list_sort)
        if not cid:
            raise cherrypy.HTTPError(404, 'invalid category id: %r'%cid)
        categories = self.categories_cache()

        if category not in categories and \
                category not in ('newest', 'allbooks'):
            raise cherrypy.HTTPError(404, 'category not found')
        fm = self.db.field_metadata
        try:
            category_name = fm[category]['name']
            dt = fm[category]['datatype']
        except:
            if category not in ('newest', 'allbooks'):
                raise
            category_name = {
                    'newest' : _('Newest'),
                    'allbooks' : _('All books'),
            }[category]
            dt = None

        hide_sort = 'true' if dt == 'series' else 'false'
        if category == 'search':
            which = unhexlify(cid).decode('utf-8')
            try:
                ids = self.search_cache('search:"%s"'%which)
            except:
                raise cherrypy.HTTPError(404, 'Search: %r not understood'%which)
        elif category == 'newest':
            ids = self.search_cache('')
            hide_sort = 'true'
        elif category == 'allbooks':
            ids = self.search_cache('')
        else:
            q = category
            if q == 'news':
                q = 'tags'
            ids = self.db.get_books_for_category(q, cid)

        items = [self.db.data._data[x] for x in ids]
        if category == 'newest':
            list_sort = 'timestamp'
        if dt == 'series':
            list_sort = category
        sort = self.browse_sort_book_list(items, list_sort)
        ids = [x[0] for x in items]
        html = render_book_list(ids, self.opts.url_prefix,
                suffix=_('in') + ' ' + category_name)

        return self.browse_template(sort, category=False).format(
                title=_('Books in') + " " +category_name,
                script='booklist(%s);'%hide_sort, main=html)

    def browse_get_book_args(self, mi, id_):
        fmts = self.db.formats(id_, index_is_id=True)
        if not fmts:
            fmts = ''
        fmts = [x.lower() for x in fmts.split(',') if x]
        pf = prefs['output_format'].lower()
        try:
            fmt = pf if pf in fmts else fmts[0]
        except:
            fmt = None
        args = {'id':id_, 'mi':mi,
                }
        for key in mi.all_field_keys():
            val = mi.format_field(key)[1]
            if not val:
                val = ''
            args[key] = xml(val, True)
        fname = quote(ascii_filename(args['title']) + ' - ' +
                ascii_filename(args['authors']))
        return args, fmt, fmts, fname

    @Endpoint(mimetype='application/json; charset=utf-8')
    def browse_booklist_page(self, ids=None, sort=None):
        if sort == 'null':
            sort = None
        if ids is None:
            ids = json.dumps('[]')
        try:
            ids = json.loads(ids)
        except:
            raise cherrypy.HTTPError(404, 'invalid ids')
        summs = []
        for id_ in ids:
            try:
                id_ = int(id_)
                mi = self.db.get_metadata(id_, index_is_id=True)
            except:
                continue
            args, fmt, fmts, fname = self.browse_get_book_args(mi, id_)
            args['other_formats'] = ''
            if fmts and fmt:
                other_fmts = [x for x in fmts if x.lower() != fmt.lower()]
                if other_fmts:
                    ofmts = [u'<a href="{4}/get/{0}/{1}_{2}.{0}" title="{3}">{3}</a>'\
                            .format(f, fname, id_, f.upper(),
                                self.opts.url_prefix) for f in
                            other_fmts]
                    ofmts = ', '.join(ofmts)
                    args['other_formats'] = u'<strong>%s: </strong>' % \
                            _('Other formats') + ofmts

            args['details_href'] = self.opts.url_prefix + '/browse/details/'+str(id_)

            if fmt:
                href = self.opts.url_prefix + '/get/%s/%s_%d.%s'%(
                        fmt, fname, id_, fmt)
                rt = xml(_('Read %s in the %s format')%(args['title'],
                        fmt.upper()), True)

                args['get_button'] = \
                        '<a href="%s" class="read" title="%s">%s</a>' % \
                        (xml(href, True), rt, xml(_('Get')))
            else:
                args['get_button'] = ''
            args['comments'] = comments_to_html(mi.comments)
            args['stars'] = ''
            if mi.rating:
                args['stars'] = render_rating(mi.rating/2.0,
                        self.opts.url_prefix, prefix=_('Rating'))[0]
            if args['tags']:
                args['tags'] = u'<strong>%s: </strong>'%xml(_('Tags')) + \
                    args['tags']
            if args['series']:
                args['series'] = args['series']
            args['details'] = xml(_('Details'), True)
            args['details_tt'] = xml(_('Show book details'), True)
            args['permalink'] = xml(_('Permalink'), True)
            args['permalink_tt'] = xml(_('A permanent link to this book'), True)

            summs.append(self.browse_summary_template.format(**args))


        return json.dumps('\n'.join(summs), ensure_ascii=False)

    def browse_render_details(self, id_):
        try:
            mi = self.db.get_metadata(id_, index_is_id=True)
        except:
            return _('This book has been deleted')
        else:
            args, fmt, fmts, fname = self.browse_get_book_args(mi, id_)
            args['formats'] = ''
            if fmts:
                ofmts = [u'<a href="{4}/get/{0}/{1}_{2}.{0}" title="{3}">{3}</a>'\
                        .format(fmt, fname, id_, fmt.upper(),
                            self.opts.url_prefix) for fmt in
                        fmts]
                ofmts = ', '.join(ofmts)
                args['formats'] = ofmts
            fields, comments = [], []
            displayed_custom_fields = custom_fields_to_display(self.db)
            for field, m in list(mi.get_all_standard_metadata(False).items()) + \
                    list(mi.get_all_user_metadata(False).items()):
                if m['is_custom'] and field not in displayed_custom_fields:
                    continue
                if m['datatype'] == 'comments' or field == 'comments':
                    comments.append((m['name'], comments_to_html(mi.get(field,
                        ''))))
                    continue
                if field in ('title', 'formats') or not args.get(field, False) \
                        or not m['name']:
                    continue
                if m['datatype'] == 'rating':
                    r = u'<strong>%s: </strong>'%xml(m['name']) + \
                            render_rating(mi.rating/2.0, self.opts.url_prefix,
                                    prefix=m['name'])[0]
                else:
                    r = u'<strong>%s: </strong>'%xml(m['name']) + \
                                args[field]
                fields.append((m['name'], r))

            fields.sort(key=lambda x: x[0].lower())
            fields = [u'<div class="field">{0}</div>'.format(f[1]) for f in
                    fields]
            fields = u'<div class="fields">%s</div>'%('\n\n'.join(fields))

            comments.sort(key=lambda x: x[0].lower())
            comments = [(u'<div class="field"><strong>%s: </strong>'
                         u'<div class="comment">%s</div></div>') % (xml(c[0]),
                             c[1]) for c in comments]
            comments = u'<div class="comments">%s</div>'%('\n\n'.join(comments))

            return self.browse_details_template.format(id=id_,
                    title=xml(mi.title, True), fields=fields,
                    formats=args['formats'], comments=comments)

    @Endpoint(mimetype='application/json; charset=utf-8')
    def browse_details(self, id=None):
        try:
            id_ = int(id)
        except:
            raise cherrypy.HTTPError(404, 'invalid id: %r'%id)

        ans = self.browse_render_details(id_)

        return json.dumps(ans, ensure_ascii=False)


    @Endpoint()
    def browse_book(self, id=None, category_sort=None):
        try:
            id_ = int(id)
        except:
            raise cherrypy.HTTPError(404, 'invalid id: %r'%id)

        ans = self.browse_render_details(id_)
        return self.browse_template('').format(
                title='', script='book();', main=ans)


    # }}}

    # Search {{{
    @Endpoint(sort_type='list')
    def browse_search(self, query='', list_sort=None):
        if isbytestring(query):
            query = query.decode('UTF-8')
        ids = self.db.search_getting_ids(query.strip(), self.search_restriction)
        items = [self.db.data._data[x] for x in ids]
        sort = self.browse_sort_book_list(items, list_sort)
        ids = [x[0] for x in items]
        html = render_book_list(ids, self.opts.url_prefix,
                suffix=_('in search')+': '+query)
        return self.browse_template(sort, category=False, initial_search=query).format(
                title=_('Matching books'),
                script='booklist();', main=html)

    # }}}


