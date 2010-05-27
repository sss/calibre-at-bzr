'''
Created on 25 May 2010

@author: charles
'''

from calibre.utils.ordered_dict import OrderedDict

class TagsIcons(dict):
    '''
    If the client wants icons to be in the tag structure, this class must be
    instantiated and filled in with real icons. If this class is instantiated
    and passed to get_categories, All items must be given a value not None
    '''

    category_icons = ['authors', 'series', 'formats', 'publisher', 'rating',
                      'news',    'tags',   ':custom', ':user',     'search',]
    def __init__(self, icon_dict):
        for a in self.category_icons:
            if a not in icon_dict:
                raise ValueError('Missing category icon [%s]'%a)
            self[a] = icon_dict[a]

class FieldMetadata(dict):

    # kind == standard: is tag category. May be a search label. Is db col
    #                   or is specially handled (e.g., news)
    # kind == not_cat: Is not a tag category. May be a search label. Is db col
    # kind == user: user-defined tag category
    # kind == search: saved-searches category
    # For 'standard', the order below is the order that the categories will
    # appear in the tags pane.
    #
    # label is the column label. key is either the label or in the case of
    # custom fields, the label prefixed with 'x'. Because of the prefixing,
    # there cannot be a name clash between standard and custom fields, so key
    # can be used as the metadata dictionary key.

    category_items_ = [
            ('authors',   {'table':'authors', 'column':'name',
                           'datatype':'text', 'is_multiple':False,
                           'kind':'standard', 'name':_('Authors'),
                           'search_keys':['authors', 'author'],
                           'is_custom':False, 'is_category':True}),
            ('series',    {'table':'series', 'column':'name',
                           'datatype':'text', 'is_multiple':False,
                           'kind':'standard', 'name':_('Series'),
                           'search_keys':['series'],
                           'is_custom':False, 'is_category':True}),
            ('formats',   {'table':None, 'column':None,
                           'datatype':'text', 'is_multiple':False, # must think what type this is!
                           'kind':'standard', 'name':_('Formats'),
                           'search_keys':['formats', 'format'],
                           'is_custom':False, 'is_category':True}),
            ('publisher', {'table':'publishers', 'column':'name',
                           'datatype':'text', 'is_multiple':False,
                           'kind':'standard', 'name':_('Publishers'),
                           'search_keys':['publisher'],
                           'is_custom':False, 'is_category':True}),
            ('rating',    {'table':'ratings', 'column':'rating',
                           'datatype':'rating', 'is_multiple':False,
                           'kind':'standard', 'name':_('Ratings'),
                           'search_keys':['rating'],
                           'is_custom':False, 'is_category':True}),
            ('news',      {'table':'news', 'column':'name',
                           'datatype':None, 'is_multiple':False,
                           'kind':'standard', 'name':_('News'),
                           'search_keys':[],
                           'is_custom':False, 'is_category':True}),
            ('tags',      {'table':'tags', 'column':'name',
                           'datatype':'text', 'is_multiple':True,
                           'kind':'standard', 'name':_('Tags'),
                           'search_keys':['tags', 'tag'],
                           'is_custom':False, 'is_category':True}),
            ('author_sort',{'table':None, 'column':None, 'datatype':'text',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ('comments',  {'table':None, 'column':None, 'datatype':'text',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':['comments', 'comment'], 'is_custom':False, 'is_category':False}),
            ('cover',     {'table':None, 'column':None, 'datatype':None,
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':['cover'], 'is_custom':False, 'is_category':False}),
            ('flags',     {'table':None, 'column':None, 'datatype':'text',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ('id',        {'table':None, 'column':None, 'datatype':'int',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ('isbn',      {'table':None, 'column':None, 'datatype':'text',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':['isbn'], 'is_custom':False, 'is_category':False}),
            ('lccn',      {'table':None, 'column':None, 'datatype':'text',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ('ondevice',  {'table':None, 'column':None, 'datatype':'bool',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ('path',      {'table':None, 'column':None, 'datatype':'text',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ('pubdate',   {'table':None, 'column':None, 'datatype':'datetime',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':['pubdate'], 'is_custom':False, 'is_category':False}),
            ('series_index',{'table':None, 'column':None, 'datatype':'float',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ('sort',      {'table':None, 'column':None, 'datatype':'text',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ('size',      {'table':None, 'column':None, 'datatype':'float',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ('timestamp', {'table':None, 'column':None, 'datatype':'datetime',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':['date'], 'is_custom':False, 'is_category':False}),
            ('title',     {'table':None, 'column':None, 'datatype':'text',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':['title'], 'is_custom':False, 'is_category':False}),
            ('uuid',      {'table':None, 'column':None, 'datatype':'text',
                           'is_multiple':False, 'kind':'standard', 'name':None,
                           'search_keys':[], 'is_custom':False, 'is_category':False}),
            ]

    # search labels that are not db columns
    search_items = [    'all',
#                        'date',
                        'search',
                    ]

    def __init__(self):
        self._tb_cats = OrderedDict()
        for k,v in self.category_items_:
            self._tb_cats[k] = v
        self.custom_field_prefix = '#'

        self.get = self._tb_cats.get

    def __getitem__(self, key):
        return self._tb_cats[key]

    def __setitem__(self, key, val):
        raise AttributeError('Assigning to this object is forbidden')

    def __delitem__(self, key):
        del self._tb_cats[key]

    def __iter__(self):
        for key in self._tb_cats:
            yield key

    def has_key(self, key):
        return key in self._tb_cats

    def __contains__(self, key):
        return self.has_key(key)

    def keys(self):
        return self._tb_cats.keys()

    def iterkeys(self):
        for key in self._tb_cats:
            yield key

    def iteritems(self):
        for key in self._tb_cats:
            yield (key, self._tb_cats[key])

    def is_custom_field(self, key):
        return key.startswith(self.custom_field_prefix)

    def key_to_label(self, key):
        if 'label' not in self._tb_cats[key]:
            return key
        return self._tb_cats[key]['label']

    def label_to_key(self, label, prefer_custom=False):
        if 'label' in self._tb_cats:
            return label
        if self.is_custom_field(label):
            return self.custom_field_prefix+label
        raise ValueError('Unknown key [%s]'%(label))

    def get_custom_fields(self):
        return [l for l in self._tb_cats if self._tb_cats[l]['is_custom']]

    def add_custom_field(self, label, table, column, datatype, colnum,
                               name, is_multiple, is_category):
        fn = self.custom_field_prefix + label
        if fn in self._tb_cats:
            raise ValueError('Duplicate custom field [%s]'%(label))
        self._tb_cats[fn] = {'table':table,       'column':column,
                             'datatype':datatype, 'is_multiple':is_multiple,
                             'kind':'standard',   'name':name,
                             'search_keys':[fn],  'label':label,
                             'colnum':colnum,     'is_custom':True,
                             'is_category':is_category}

    def set_field_record_index(self, label, index, prefer_custom=False):
        if prefer_custom:
            key = self.custom_field_prefix+label
            if key not in self._tb_cats:
                key = label
        else:
            if label in self._tb_cats:
                key = label
            else:
                key = self.custom_field_prefix+label
        self._tb_cats[key]['rec_index'] = index  # let the exception fly ...

    def add_user_category(self, label, name):
        if label in self._tb_cats:
            raise ValueError('Duplicate user field [%s]'%(label))
        self._tb_cats[label] = {'table':None,        'column':None,
                                'datatype':None,     'is_multiple':False,
                                'kind':'user',       'name':name,
                                'search_keys':[],    'is_custom':False,
                                'is_category':True}

    def add_search_category(self, label, name):
        if label in self._tb_cats:
            raise ValueError('Duplicate user field [%s]'%(label))
        self._tb_cats[label] = {'table':None,        'column':None,
                                'datatype':None,     'is_multiple':False,
                                'kind':'search',     'name':name,
                                'search_keys':[],    'is_custom':False,
                                'is_category':True}

#    DEFAULT_LOCATIONS = frozenset([
#        'all',
#        'author',       # compatibility
#        'authors',
#        'comment',      # compatibility
#        'comments',
#        'cover',
#        'date',
#        'format',       # compatibility
#        'formats',
#        'isbn',
#        'ondevice',
#        'pubdate',
#        'publisher',
#        'search',
#        'series',
#        'rating',
#        'tag',          # compatibility
#        'tags',
#        'title',
#                 ])


    def get_search_keys(self):
        s_keys = []
        for v in self._tb_cats.itervalues():
            map((lambda x:s_keys.append(x)), v['search_keys'])
        for v in self.search_items:
            s_keys.append(v)
#        if set(s_keys) != self.DEFAULT_LOCATIONS:
#            print 'search labels and default_locations do not match:'
#            print set(s_keys) ^ self.DEFAULT_LOCATIONS
        return s_keys
