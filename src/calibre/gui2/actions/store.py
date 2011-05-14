# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import QMenu

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.confirm_delete import confirm

class StoreAction(InterfaceAction):

    name = 'Store'
    action_spec = (_('Get books'), 'store.png', None, None)

    def genesis(self):
        self.qaction.triggered.connect(self.do_search)
        self.store_menu = QMenu()
        self.load_menu()

    def load_menu(self):
        self.store_menu.clear()
        self.store_menu.addAction(_('Search for ebooks'), self.search)
        self.store_menu.addAction(_('Search for this author'), self.search_author)
        self.store_menu.addAction(_('Search for this title'), self.search_title)
        self.store_menu.addAction(_('Search for this book'), self.search_author_title)
        self.store_menu.addSeparator()
        self.store_list_menu = self.store_menu.addMenu(_('Stores'))
        for n, p in sorted(self.gui.istores.items(), key=lambda x: x[0].lower()):
            self.store_list_menu.addAction(n, partial(self.open_store, p))
        self.qaction.setMenu(self.store_menu)

    def do_search(self):
        return self.search()

    def search(self, query=''):
        self.show_disclaimer()
        from calibre.gui2.store.search.search import SearchDialog
        sd = SearchDialog(self.gui.istores, self.gui, query)
        sd.exec_()

    def _get_selected_row(self):
        rows = self.gui.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return None
        return rows[0].row()

    def _get_author(self, row):
        authors = []

        if self.gui.current_view() is self.gui.library_view:
            a = self.gui.library_view.model().authors(row)
            authors = a.split(',')
        else:
            mi = self.gui.current_view().model().get_book_display_info(row)
            authors = mi.authors

        corrected_authors = []
        for x in authors:
            a = x.split('|')
            a.reverse()
            a = ' '.join(a)
            corrected_authors.append(a)

        return ' & '.join(corrected_authors)

    def search_author(self):
        row = self._get_selected_row()
        if row == None:
            error_dialog(self.gui, _('Cannot search'), _('No book selected'), show=True)
            return

        query = 'author:"%s"' % self._get_author(row)
        self.search(query)

    def _get_title(self, row):
        title = ''
        if self.gui.current_view() is self.gui.library_view:
            title = self.gui.library_view.model().title(row)
        else:
            mi = self.gui.current_view().model().get_book_display_info(row)
            title = mi.title

        return title

    def search_title(self):
        row = self._get_selected_row()
        if row == None:
            error_dialog(self.gui, _('Cannot search'), _('No book selected'), show=True)
            return

        query = 'title:"%s"' % self._get_title(row)
        self.search(query)

    def search_author_title(self):
        row = self._get_selected_row()
        if row == None:
            error_dialog(self.gui, _('Cannot search'), _('No book selected'), show=True)
            return

        query = 'author:"%s" title:"%s"' % (self._get_author(row), self._get_title(row))
        self.search(query)

    def open_store(self, store_plugin):
        self.show_disclaimer()
        store_plugin.open(self.gui)

    def show_disclaimer(self):
        confirm(('<p>' +
            _('Calibre helps you find the ebooks you want by searching '
            'the websites of various commercial and public domain '
            'book sources for you.') +
            '<p>' +
            _('Using the integrated search you can easily find which '
            'store has the book you are looking for, at the best price. '
            'You also get DRM status and other useful information.')
            + '<p>' +
            _('All transactions (paid or otherwise) are handled between '
            'you and the book seller. '
            'Calibre is not part of this process and any issues related '
            'to a purchase should be directed to the website you are '
            'buying from. Be sure to double check that any books you get '
            'will work with your e-book reader, especially if the book you '
            'are buying has '
            '<a href="http://drmfree.calibre-ebook.com/about#drm">DRM</a>.'
            )), 'about_get_books_msg',
            parent=self.gui, show_cancel_button=False,
            confirm_msg=_('Show this message again'),
            pixmap='dialog_information.png', title=_('About Get Books'))

