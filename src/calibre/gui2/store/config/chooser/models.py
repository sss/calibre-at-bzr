# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (Qt, QAbstractItemModel, QIcon, QVariant, QModelIndex)

from calibre.gui2 import NONE
from calibre.customize.ui import is_disabled, disable_plugin, enable_plugin
from calibre.library.caches import _match, CONTAINS_MATCH, EQUALS_MATCH, \
    REGEXP_MATCH
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import SearchQueryParser


class Matches(QAbstractItemModel):

    HEADERS = [_('Enabled'), _('Name'), _('No DRM'), _('Headquarters'), _('Formats')]
    HTML_COLS = [1]

    def __init__(self, plugins):
        QAbstractItemModel.__init__(self)

        self.NO_DRM_ICON = QIcon(I('ok.png'))

        self.all_matches = plugins
        self.matches = plugins
        self.filter = ''
        self.search_filter = SearchFilter(self.all_matches)

        self.sort_col = 1
        self.sort_order = Qt.AscendingOrder
        
    def get_plugin(self, index):
        row = index.row()
        if row < len(self.matches):
            return self.matches[row]
        else:
            return None
    
    def search(self, filter):        
        self.filter = filter.strip()
        if not self.filter:
            self.matches = self.all_matches
        else:
            try:
                self.matches = list(self.search_filter.parse(self.filter))
            except:
                self.matches = self.all_matches
        self.layoutChanged.emit()
        self.sort(self.sort_col, self.sort_order)

    def toggle_plugin(self, index):
        new_index = self.createIndex(index.row(), 0)
        data = QVariant(is_disabled(self.get_plugin(index)))
        self.setData(new_index, data, Qt.CheckStateRole)

    def index(self, row, column, parent=QModelIndex()):
        return self.createIndex(row, column)

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(0, 0)

    def rowCount(self, *args):
        return len(self.matches)

    def columnCount(self, *args):
        return len(self.HEADERS)
    
    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        text = ''
        if orientation == Qt.Horizontal:
            if section < len(self.HEADERS):
                text = self.HEADERS[section]
            return QVariant(text)
        else:
            return QVariant(section+1)

    def data(self, index, role):
        row, col = index.row(), index.column()
        result = self.matches[row]
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == 1:
                return QVariant('<b>%s</b><br><i>%s</i>' % (result.name, result.description))
            elif col == 3:
                return QVariant(result.headquarters)
            elif col == 4:
                return QVariant(', '.join(result.formats).upper())
        elif role == Qt.DecorationRole:
            if col == 2:
                if result.drm_free_only:
                    return QVariant(self.NO_DRM_ICON)
        elif role == Qt.CheckStateRole:
            if col == 0:
                if is_disabled(result):
                    return Qt.Unchecked
                return Qt.Checked
        elif role == Qt.ToolTipRole:
            return QVariant('<p>%s</p>' % result.description)
        return NONE

    def setData(self, index, data, role):
        if not index.isValid():
            return False
        row, col = index.row(), index.column()
        if col == 0:
            if data.toBool():
                enable_plugin(self.get_plugin(index))
            else:
                disable_plugin(self.get_plugin(index)) 
        self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), self.columnCount() - 1))
        return True

    def flags(self, index):
        if index.column() == 0:
            return QAbstractItemModel.flags(self, index) | Qt.ItemIsUserCheckable
        return QAbstractItemModel.flags(self, index)

    def data_as_text(self, match, col):
        text = ''
        if col == 0:
            text = 'b' if is_disabled(match) else 'a'
        elif col == 1:
            text = match.name
        elif col == 2:
            text = 'b' if match.drm else 'a'
        elif col == 3:
            text = match.headquarters
        return text

    def sort(self, col, order, reset=True):
        self.sort_col = col
        self.sort_order = order
        if not self.matches:
            return
        descending = order == Qt.DescendingOrder
        self.matches.sort(None,
            lambda x: sort_key(unicode(self.data_as_text(x, col))),
            descending)
        if reset:
            self.reset()


class SearchFilter(SearchQueryParser):
    
    USABLE_LOCATIONS = [
        'all',
        'description',
        'drm',
        'enabled',
        'format',
        'formats',
        'headquarters',
        'name',
    ]

    def __init__(self, all_plugins=[]):
        SearchQueryParser.__init__(self, locations=self.USABLE_LOCATIONS)
        self.srs = set(all_plugins)

    def universal_set(self):
        return self.srs

    def get_matches(self, location, query):
        location = location.lower().strip()
        if location == 'formats':
            location = 'format'

        matchkind = CONTAINS_MATCH
        if len(query) > 1:
            if query.startswith('\\'):
                query = query[1:]
            elif query.startswith('='):
                matchkind = EQUALS_MATCH
                query = query[1:]
            elif query.startswith('~'):
                matchkind = REGEXP_MATCH
                query = query[1:]
        if matchkind != REGEXP_MATCH: ### leave case in regexps because it can be significant e.g. \S \W \D
            query = query.lower()

        if location not in self.USABLE_LOCATIONS:
            return set([])
        matches = set([])
        all_locs = set(self.USABLE_LOCATIONS) - set(['all'])
        locations = all_locs if location == 'all' else [location]
        q = {
             'description': lambda x: x.description.lower(),
             'drm': lambda x: not x.drm_free_only,
             'enabled': lambda x: not is_disabled(x),
             'format': lambda x: ','.join(x.formats).lower(),
             'headquarters': lambda x: x.headquarters.lower(),
             'name': lambda x : x.name.lower(),
        }
        q['formats'] = q['format']
        for sr in self.srs:
            for locvalue in locations:
                accessor = q[locvalue] 
                if query == 'true':
                    if locvalue in ('drm', 'enabled'):
                        if accessor(sr) == True:
                            matches.add(sr)
                    elif accessor(sr) is not None:
                        matches.add(sr)
                    continue
                if query == 'false':
                    if locvalue in ('drm', 'enabled'):
                        if accessor(sr) == False:
                            matches.add(sr)
                    elif accessor(sr) is None:
                        matches.add(sr)
                    continue
                # this is bool, so can't match below
                if locvalue in ('drm', 'enabled'):
                    continue
                try:
                    ### Can't separate authors because comma is used for name sep and author sep
                    ### Exact match might not get what you want. For that reason, turn author
                    ### exactmatch searches into contains searches.
                    if locvalue == 'name' and matchkind == EQUALS_MATCH:
                        m = CONTAINS_MATCH
                    else:
                        m = matchkind

                    if locvalue == 'format':
                        vals = accessor(sr).split(',')
                    else:
                        vals = [accessor(sr)]
                    if _match(query, vals, m):
                        matches.add(sr)
                        break
                except ValueError: # Unicode errors
                    import traceback
                    traceback.print_exc()
        return matches

        
