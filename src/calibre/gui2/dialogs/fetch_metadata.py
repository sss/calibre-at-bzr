__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
GUI for fetching metadata from servers.
'''

import time
from threading import Thread

from PyQt4.QtCore import Qt, QObject, SIGNAL, QVariant, pyqtSignal, \
                         QAbstractTableModel, QCoreApplication, QTimer
from PyQt4.QtGui import QDialog, QItemSelectionModel, QIcon

from calibre.gui2.dialogs.fetch_metadata_ui import Ui_FetchMetadata
from calibre.gui2 import error_dialog, NONE, info_dialog, config
from calibre.gui2.widgets import ProgressIndicator
from calibre import strftime, force_unicode
from calibre.customize.ui import get_isbndb_key, set_isbndb_key
from calibre.utils.icu import sort_key
from calibre import force_unicode

_hung_fetchers = set([])

class Fetcher(Thread):

    def __init__(self, title, author, publisher, isbn, key):
        Thread.__init__(self)
        self.daemon = True
        self.title = title
        self.author = author
        self.publisher = publisher
        self.isbn = isbn
        self.key = key
        self.results, self.exceptions = [], []

    def run(self):
        from calibre.ebooks.metadata.fetch import search
        self.results, self.exceptions = search(self.title, self.author,
                                               self.publisher, self.isbn,
                                               self.key if self.key else None)


class Matches(QAbstractTableModel):

    def __init__(self, matches):
        self.matches = matches
        self.yes_icon = QVariant(QIcon(I('ok.png')))
        QAbstractTableModel.__init__(self)

    def rowCount(self, *args):
        return len(self.matches)

    def columnCount(self, *args):
        return 8

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        text = ""
        if orientation == Qt.Horizontal:
            if   section == 0: text = _("Title")
            elif section == 1: text = _("Author(s)")
            elif section == 2: text = _("Author Sort")
            elif section == 3: text = _("Publisher")
            elif section == 4: text = _("ISBN")
            elif section == 5: text = _("Published")
            elif section == 6: text = _("Has Cover")
            elif section == 7: text = _("Has Summary")

            return QVariant(text)
        else:
            return QVariant(section+1)

    def summary(self, row):
        return self.matches[row].comments

    def data_as_text(self, book, col):
        if col == 0 and book.title is not None:
            return book.title
        elif col == 1:
            return ', '.join(book.authors)
        elif col == 2 and book.author_sort is not None:
            return book.author_sort
        elif col == 3 and book.publisher is not None:
            return book.publisher
        elif col == 4 and book.isbn is not None:
            return book.isbn
        elif col == 5 and hasattr(book.pubdate, 'timetuple'):
                return strftime('%b %Y', book.pubdate.timetuple())
        elif col == 6 and book.has_cover:
            return 'has_cover'
        elif col == 7 and book.comments is not None:
            return book.comments
        else:
            return ''

    def data(self, index, role):
        row, col = index.row(), index.column()
        book = self.matches[row]
        if role == Qt.DisplayRole:
            res = self.data_as_text(book, col)
            if not (col <= 5 and res):
                return NONE
            return QVariant(res)
        elif role == Qt.DecorationRole:
            if col == 6 and book.has_cover:
                return self.yes_icon
            if col == 7 and book.comments:
                return self.yes_icon
        return NONE

    def sort(self, col, order, reset=True):
        if not self.matches:
            return
        descending = order == Qt.DescendingOrder
        self.matches.sort(None,
            lambda x: sort_key(unicode(force_unicode(self.data_as_text(x, col)))),
            descending)
        if reset:
            self.reset()

class FetchMetadata(QDialog, Ui_FetchMetadata):

    HANG_TIME = 75 #seconds

    queue_reject = pyqtSignal()

    def __init__(self, parent, isbn, title, author, publisher, timeout):
        QDialog.__init__(self, parent)
        Ui_FetchMetadata.__init__(self)
        self.setupUi(self)

        for fetcher in list(_hung_fetchers):
            if not fetcher.is_alive():
                _hung_fetchers.remove(fetcher)

        self.pi = ProgressIndicator(self)
        self.timeout = timeout
        QObject.connect(self.fetch, SIGNAL('clicked()'), self.fetch_metadata)
        self.queue_reject.connect(self.reject, Qt.QueuedConnection)

        isbndb_key = get_isbndb_key()
        if not isbndb_key:
            isbndb_key = ''
        self.key.setText(isbndb_key)

        self.setWindowTitle(title if title else _('Unknown'))
        self.isbn = isbn
        self.title = title
        self.author = author.strip()
        self.publisher = publisher
        self.previous_row = None
        self.warning.setVisible(False)
        self.connect(self.matches, SIGNAL('activated(QModelIndex)'), self.chosen)
        self.connect(self.matches, SIGNAL('entered(QModelIndex)'),
                     self.show_summary)
        self.matches.setMouseTracking(True)
        # Enabling sorting and setting a sort column will not change the initial
        # order of the results, as they are filled in later
        self.matches.setSortingEnabled(True)
        QObject.connect(self.matches.horizontalHeader(), SIGNAL('sectionClicked(int)'), self.show_sort_indicator)
        self.matches.horizontalHeader().setSortIndicatorShown(False)
        self.fetch_metadata()
        self.opt_get_social_metadata.setChecked(config['get_social_metadata'])
        self.opt_overwrite_author_title_metadata.setChecked(config['overwrite_author_title_metadata'])
        self.opt_auto_download_cover.setChecked(config['auto_download_cover'])

    def show_summary(self, current, *args):
        row  = current.row()
        if row != self.previous_row:
            summ =  self.model.summary(row)
            self.summary.setText(summ if summ else '')
            self.previous_row = row

    def fetch_metadata(self):
        self.warning.setVisible(False)
        key = str(self.key.text())
        if key:
            set_isbndb_key(key)
        else:
            key = None
        title = author = publisher = isbn = None
        if self.isbn:
            isbn = self.isbn
        if self.title:
            title = self.title
        if self.author and not self.author == _('Unknown'):
            author = self.author
        self.fetch.setEnabled(False)
        self.setCursor(Qt.WaitCursor)
        QCoreApplication.instance().processEvents()
        self.fetcher = Fetcher(title, author, publisher, isbn, key)
        self.fetcher.start()
        self.pi.start(_('Finding metadata...'))
        self._hangcheck = QTimer(self)
        self.connect(self._hangcheck, SIGNAL('timeout()'), self.hangcheck,
                Qt.QueuedConnection)
        self.start_time = time.time()
        self._hangcheck.start(100)

    def hangcheck(self):
        if self.fetcher.is_alive() and \
                time.time() - self.start_time < self.HANG_TIME:
            return
        self._hangcheck.stop()
        try:
            if self.fetcher.is_alive():
                error_dialog(self, _('Could not find metadata'),
                             _('The metadata download seems to have stalled. '
                               'Try again later.')).exec_()
                self.terminate()
                return self.queue_reject.emit()
            self.model = Matches(self.fetcher.results)
            warnings = [(x[0], force_unicode(x[1])) for x in \
                            self.fetcher.exceptions if x[1] is not None]
            if warnings:
                warnings='<br>'.join(['<b>%s</b>: %s'%(name, exc) for name,exc in warnings])
                self.warning.setText('<p><b>'+ _('Warning')+':</b>'+\
                               _('Could not fetch metadata from:')+\
                               '<br>'+warnings+'</p>')
                self.warning.setVisible(True)
            if self.model.rowCount() < 1:
                info_dialog(self, _('No metadata found'),
                     _('No metadata found, try adjusting the title and author '
                       'and/or removing the ISBN.')).exec_()
                self.reject()
                return

            self.matches.setModel(self.model)
            QObject.connect(self.matches.selectionModel(),
                        SIGNAL('currentRowChanged(QModelIndex, QModelIndex)'),
                        self.show_summary)
            self.model.reset()
            self.matches.selectionModel().select(self.model.index(0, 0),
                                  QItemSelectionModel.Select | QItemSelectionModel.Rows)
            self.matches.setCurrentIndex(self.model.index(0, 0))
        finally:
            self.fetch.setEnabled(True)
            self.unsetCursor()
            self.matches.resizeColumnsToContents()
            self.pi.stop()

    def terminate(self):
        if hasattr(self, 'fetcher') and self.fetcher.is_alive():
            _hung_fetchers.add(self.fetcher)
        if hasattr(self, '_hangcheck') and self._hangcheck.isActive():
            self._hangcheck.stop()
        # Save value of auto_download_cover, since this is the only place it can
        # be set. The values of the other options can be set in
        # Preferences->Behavior and should not be set here as they affect bulk
        # downloading as well.
        if self.opt_auto_download_cover.isChecked() != config['auto_download_cover']:
           config.set('auto_download_cover', self.opt_auto_download_cover.isChecked())

    def __enter__(self, *args):
        return self

    def __exit__(self, *args):
        self.terminate()

    def selected_book(self):
        try:
            return self.matches.model().matches[self.matches.currentIndex().row()]
        except:
            return None

    def chosen(self, index):
        self.matches.setCurrentIndex(index)
        self.accept()
    
    def show_sort_indicator(self):
        self.matches.horizontalHeader().setSortIndicatorShown(True)
