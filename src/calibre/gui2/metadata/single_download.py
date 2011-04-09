#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from threading import Thread, Event
from operator import attrgetter
from Queue import Queue, Empty

from PyQt4.Qt import (QStyledItemDelegate, QTextDocument, QRectF, QIcon, Qt,
        QStyle, QApplication, QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
        QStackedWidget, QWidget, QTableView, QGridLayout, QFontInfo, QPalette,
        QTimer, pyqtSignal, QAbstractTableModel, QVariant, QSize, QListView,
        QPixmap, QAbstractListModel, QColor, QRect)
from PyQt4.QtWebKit import QWebView

from calibre.customize.ui import metadata_plugins
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.logging import GUILog as Log
from calibre.ebooks.metadata.sources.identify import identify
from calibre.ebooks.metadata.book.base import Metadata
from calibre.gui2 import error_dialog, NONE
from calibre.utils.date import utcnow, fromordinal, format_date
from calibre.library.comments import comments_to_html
from calibre import force_unicode

DEVELOP_DIALOG = False

class RichTextDelegate(QStyledItemDelegate): # {{{

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def to_doc(self, index):
        doc = QTextDocument()
        doc.setHtml(index.data().toString())
        return doc

    def sizeHint(self, option, index):
        ans = self.to_doc(index).size().toSize()
        ans.setHeight(ans.height()+10)
        return ans

    def paint(self, painter, option, index):
        painter.save()
        painter.setClipRect(QRectF(option.rect))
        if hasattr(QStyle, 'CE_ItemViewItem'):
            QApplication.style().drawControl(QStyle.CE_ItemViewItem, option, painter)
        elif option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        painter.translate(option.rect.topLeft())
        self.to_doc(index).drawContents(painter)
        painter.restore()
# }}}

class ResultsModel(QAbstractTableModel): # {{{

    COLUMNS = (
            '#', _('Title'), _('Published'), _('Has cover'), _('Has summary')
            )
    HTML_COLS = (1, 2)
    ICON_COLS = (3, 4)

    def __init__(self, results, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.results = results
        self.yes_icon = QVariant(QIcon(I('ok.png')))

    def rowCount(self, parent=None):
        return len(self.results)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            try:
                return QVariant(self.COLUMNS[section])
            except:
                return NONE
        return NONE

    def data_as_text(self, book, col):
        if col == 0:
            return unicode(book.gui_rank+1)
        if col == 1:
            t = book.title if book.title else _('Unknown')
            a = authors_to_string(book.authors) if book.authors else ''
            return '<b>%s</b><br><i>%s</i>' % (t, a)
        if col == 2:
            d = format_date(book.pubdate, 'yyyy') if book.pubdate else _('Unknown')
            p = book.publisher if book.publisher else ''
            return '<b>%s</b><br><i>%s</i>' % (d, p)


    def data(self, index, role):
        row, col = index.row(), index.column()
        try:
            book = self.results[row]
        except:
            return NONE
        if role == Qt.DisplayRole and col not in self.ICON_COLS:
            res = self.data_as_text(book, col)
            if res:
                return QVariant(res)
            return NONE
        elif role == Qt.DecorationRole and col in self.ICON_COLS:
            if col == 3 and getattr(book, 'has_cached_cover_url', False):
                return self.yes_icon
            if col == 4 and book.comments:
                return self.yes_icon
        elif role == Qt.UserRole:
            return book
        return NONE

    def sort(self, col, order=Qt.AscendingOrder):
        key = lambda x: x
        if col == 0:
            key = attrgetter('gui_rank')
        elif col == 1:
            key = attrgetter('title')
        elif col == 2:
            key = attrgetter('authors')
        elif col == 3:
            key = attrgetter('has_cached_cover_url')
        elif key == 4:
            key = lambda x: bool(x.comments)

        self.results.sort(key=key, reverse=order==Qt.AscendingOrder)
        self.reset()

# }}}

class ResultsView(QTableView): # {{{

    show_details_signal = pyqtSignal(object)
    book_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self.rt_delegate = RichTextDelegate(self)
        self.setSelectionMode(self.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(self.SelectRows)
        self.setIconSize(QSize(24, 24))
        self.clicked.connect(self.show_details)
        self.doubleClicked.connect(self.select_index)
        self.setSortingEnabled(True)

    def show_results(self, results):
        self._model = ResultsModel(results, self)
        self.setModel(self._model)
        for i in self._model.HTML_COLS:
            self.setItemDelegateForColumn(i, self.rt_delegate)
        self.resizeRowsToContents()
        self.resizeColumnsToContents()
        self.setFocus(Qt.OtherFocusReason)

    def currentChanged(self, current, previous):
        ret = QTableView.currentChanged(self, current, previous)
        self.show_details(current)
        return ret

    def show_details(self, index):
        book = self.model().data(index, Qt.UserRole)
        parts = [
            '<center>',
            '<h2>%s</h2>'%book.title,
            '<div><i>%s</i></div>'%authors_to_string(book.authors),
        ]
        if not book.is_null('rating'):
            parts.append('<div>%s</div>'%('\u2605'*int(book.rating)))
        parts.append('</center>')
        if book.tags:
            parts.append('<div>%s</div><div>\u00a0</div>'%', '.join(book.tags))
        if book.comments:
            parts.append(comments_to_html(book.comments))

        self.show_details_signal.emit(''.join(parts))

    def select_index(self, index):
        if not index.isValid():
            index = self.model().index(0, 0)
        book = self.model().data(index, Qt.UserRole)
        self.book_selected.emit(book)

    def get_result(self):
        self.select_index(self.currentIndex())

# }}}

class Comments(QWebView): # {{{

    def __init__(self, parent=None):
        QWebView.__init__(self, parent)
        self.setAcceptDrops(False)
        self.setMaximumWidth(300)
        self.setMinimumWidth(300)

        palette = self.palette()
        palette.setBrush(QPalette.Base, Qt.transparent)
        self.page().setPalette(palette)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

    def turnoff_scrollbar(self, *args):
        self.page().mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)

    def show_data(self, html):
        def color_to_string(col):
            ans = '#000000'
            if col.isValid():
                col = col.toRgb()
                if col.isValid():
                    ans = unicode(col.name())
            return ans

        f = QFontInfo(QApplication.font(self.parent())).pixelSize()
        c = color_to_string(QApplication.palette().color(QPalette.Normal,
                        QPalette.WindowText))
        templ = '''\
        <html>
            <head>
            <style type="text/css">
                body, td {background-color: transparent; font-size: %dpx; color: %s }
                a { text-decoration: none; color: blue }
                div.description { margin-top: 0; padding-top: 0; text-indent: 0 }
                table { margin-bottom: 0; padding-bottom: 0; }
            </style>
            </head>
            <body>
            <div class="description">
            %%s
            </div>
            </body>
        <html>
        '''%(f, c)
        self.setHtml(templ%html)
# }}}

class IdentifyWorker(Thread): # {{{

    def __init__(self, log, abort, title, authors, identifiers):
        Thread.__init__(self)
        self.daemon = True

        self.log, self.abort = log, abort
        self.title, self.authors, self.identifiers = (title, authors,
                identifiers)

        self.results = []
        self.error = None

    def sample_results(self):
        m1 = Metadata('The Great Gatsby', ['Francis Scott Fitzgerald'])
        m2 = Metadata('The Great Gatsby', ['F. Scott Fitzgerald'])
        m1.has_cached_cover_url = True
        m2.has_cached_cover_url = False
        m1.comments  = 'Some comments '*10
        m1.tags = ['tag%d'%i for i in range(20)]
        m1.rating = 4.4
        m1.language = 'en'
        m2.language = 'fr'
        m1.pubdate = utcnow()
        m2.pubdate = fromordinal(1000000)
        m1.publisher = 'Publisher 1'
        m2.publisher = 'Publisher 2'

        return [m1, m2]

    def run(self):
        try:
            if DEVELOP_DIALOG:
                self.results = self.sample_results()
            else:
                self.results = identify(self.log, self.abort, title=self.title,
                        authors=self.authors, identifiers=self.identifiers)
            for i, result in enumerate(self.results):
                result.gui_rank = i
        except:
            import traceback
            self.error = force_unicode(traceback.format_exc())
# }}}

class IdentifyWidget(QWidget): # {{{

    rejected = pyqtSignal()
    results_found = pyqtSignal()
    book_selected = pyqtSignal(object)

    def __init__(self, log, parent=None):
        QWidget.__init__(self, parent)
        self.log = log
        self.abort = Event()

        self.l = l = QGridLayout()
        self.setLayout(l)

        names = ['<b>'+p.name+'</b>' for p in metadata_plugins(['identify']) if
                p.is_configured()]
        self.top = QLabel('<p>'+_('calibre is downloading metadata from: ') +
            ', '.join(names))
        self.top.setWordWrap(True)
        l.addWidget(self.top, 0, 0)

        self.results_view = ResultsView(self)
        self.results_view.book_selected.connect(self.book_selected.emit)
        self.get_result = self.results_view.get_result
        l.addWidget(self.results_view, 1, 0)

        self.comments_view = Comments(self)
        l.addWidget(self.comments_view, 1, 1)

        self.results_view.show_details_signal.connect(self.comments_view.show_data)

        self.query = QLabel('download starting...')
        f = self.query.font()
        f.setPointSize(f.pointSize()-2)
        self.query.setFont(f)
        self.query.setWordWrap(True)
        l.addWidget(self.query, 2, 0, 1, 2)

        self.comments_view.show_data('<h2>'+_('Downloading')+
                '<br><span id="dots">.</span></h2>'+
                '''
                <script type="text/javascript">
                window.onload=function(){
                    var dotspan = document.getElementById('dots');
                    window.setInterval(function(){
                        if(dotspan.textContent == '............'){
                        dotspan.textContent = '.';
                        }
                        else{
                        dotspan.textContent += '.';
                        }
                    }, 400);
                }
                </script>
                ''')

    def start(self, title=None, authors=None, identifiers={}):
        self.log.clear()
        self.log('Starting download')
        parts = []
        if title:
            parts.append('title:'+title)
        if authors:
            parts.append('authors:'+authors_to_string(authors))
        if identifiers:
            x = ', '.join('%s:%s'%(k, v) for k, v in identifiers)
            parts.append(x)
        self.query.setText(_('Query: ')+'; '.join(parts))
        self.log(unicode(self.query.text()))

        self.worker = IdentifyWorker(self.log, self.abort, title,
                authors, identifiers)

        self.worker.start()

        QTimer.singleShot(50, self.update)

    def update(self):
        if self.worker.is_alive():
            QTimer.singleShot(50, self.update)
        else:
            self.process_results()

    def process_results(self):
        if self.worker.error is not None:
            error_dialog(self, _('Download failed'),
                    _('Failed to download metadata. Click '
                        'Show Details to see details'),
                    show=True, det_msg=self.worker.error)
            self.rejected.emit()
            return

        if not self.worker.results:
            log = ''.join(self.log.plain_text)
            error_dialog(self, _('No matches found'), '<p>' +
                    _('Failed to find any books that '
                        'match your search. Try making the search <b>less '
                        'specific</b>. For example, use only the author\'s '
                        'last name and a single distinctive word from '
                        'the title.<p>To see the full log, click Show Details.'),
                    show=True, det_msg=log)
            self.rejected.emit()
            return

        self.results_view.show_results(self.worker.results)

        self.comments_view.show_data('''
            <div style="margin-bottom:2ex">Found <b>%d</b> results</div>
            <div>To see <b>details</b>, click on any result</div>''' %
                len(self.worker.results))

        self.results_found.emit()


    def cancel(self):
        self.abort.set()
# }}}

class CoverWorker(Thread): # {{{

    def __init__(self, log, abort, title, authors, identifiers):
        Thread.__init__(self)
        self.daemon = True

        self.log, self.abort = log, abort
        self.title, self.authors, self.identifiers = (title, authors,
                identifiers)

        self.rq = Queue()
        self.error = None

    def fake_run(self):
        import time
        time.sleep(2)

    def run(self):
        try:
            if DEVELOP_DIALOG:
                self.fake_run()
            else:
                from calibre.ebooks.metadata.sources.covers import run_download
                run_download(self.log, self.rq, self.abort, title=self.title,
                        authors=self.authors, identifiers=self.identifiers)
        except:
            import traceback
            self.error = force_unicode(traceback.format_exc())
# }}}

class CoversModel(QAbstractListModel): # {{{

    def __init__(self, current_cover, parent=None):
        QAbstractListModel.__init__(self, parent)

        if current_cover is None:
            current_cover = QPixmap(I('default_cover.png'))

        self.blank = QPixmap(I('blank.png')).scaled(150, 200)

        self.covers = [self.get_item(_('Current cover'), current_cover)]
        self.plugin_map = {}
        for i, plugin in enumerate(metadata_plugins(['cover'])):
            self.covers.append((plugin.name+'\n'+_('Searching...'),
                QVariant(self.blank), None, True))
            self.plugin_map[plugin] = i+1

    def get_item(self, src, pmap, waiting=False):
        sz = '%dx%d'%(pmap.width(), pmap.height())
        text = QVariant(src + '\n' + sz)
        scaled = pmap.scaled(150, 200, Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation)
        return (text, QVariant(scaled), pmap, waiting)

    def rowCount(self, parent=None):
        return len(self.covers)

    def data(self, index, role):
        try:
            text, pmap, cover, waiting = self.covers[index.row()]
        except:
            return NONE
        if role == Qt.DecorationRole:
            return pmap
        if role == Qt.DisplayRole:
            return text
        if role == Qt.UserRole:
            return waiting
        return NONE

    def plugin_for_index(self, index):
        row = index.row() if hasattr(index, 'row') else index
        for k, v in self.plugin_map.iteritems():
            if v == row:
                return k

    def clear_failed(self):
        good = []
        pmap = {}
        for i, x in enumerate(self.covers):
            if not x[-1]:
                good.append(x)
                if i > 0:
                    plugin = self.plugin_for_index(i)
                    pmap[plugin] = len(good) - 1
        good = [x for x in self.covers if not x[-1]]
        self.covers = good
        self.plugin_map = pmap
        self.reset()

    def index_for_plugin(self, plugin):
        idx = self.plugin_map.get(plugin, 0)
        return self.index(idx)

    def update_result(self, plugin, width, height, data):
        try:
            idx = self.plugin_map[plugin]
        except:
            return
        pmap = QPixmap()
        pmap.loadFromData(data)
        if pmap.isNull():
            return
        self.covers[idx] = self.get_item(plugin.name, pmap, waiting=False)
        self.dataChanged.emit(self.index(idx), self.index(idx))

    def cover_pmap(self, index):
        row = index.row()
        if row > 0 and row < len(self.covers):
            pmap = self.books[row][2]
            if pmap is not None and not pmap.isNull():
                return pmap

# }}}

class CoverDelegate(QStyledItemDelegate): # {{{

    needs_redraw = pyqtSignal()

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)

        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.frame_changed)
        self.color = parent.palette().color(QPalette.WindowText)
        self.spinner_width = 64

    def frame_changed(self, *args):
        self.angle = (self.angle+30)%360
        self.needs_redraw.emit()

    def start_animation(self):
        self.angle = 0
        self.timer.start(200)

    def stop_animation(self):
        self.timer.stop()

    def draw_spinner(self, painter, rect):
        width = rect.width()

        outer_radius = (width-1)*0.5
        inner_radius = (width-1)*0.5*0.38

        capsule_height = outer_radius - inner_radius
        capsule_width  = int(capsule_height * (0.23 if width > 32 else 0.35))
        capsule_radius = capsule_width//2

        painter.save()
        painter.setRenderHint(painter.Antialiasing)

        for i in xrange(12):
            color = QColor(self.color)
            color.setAlphaF(1.0 - (i/12.0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.save()
            painter.translate(rect.center())
            painter.rotate(self.angle - i*30.0)
            painter.drawRoundedRect(-capsule_width*0.5,
                    -(inner_radius+capsule_height), capsule_width,
                    capsule_height, capsule_radius, capsule_radius)
            painter.restore()
        painter.restore()

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        if self.timer.isActive() and index.data(Qt.UserRole).toBool():
            rect = QRect(0, 0, self.spinner_width, self.spinner_width)
            rect.moveCenter(option.rect.center())
            self.draw_spinner(painter, rect)
# }}}

class CoversView(QListView): # {{{

    chosen = pyqtSignal()

    def __init__(self, current_cover, parent=None):
        QListView.__init__(self, parent)
        self.m = CoversModel(current_cover, self)
        self.setModel(self.m)

        self.setFlow(self.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(self.Adjust)
        self.setGridSize(QSize(190, 260))
        self.setIconSize(QSize(150, 200))
        self.setSelectionMode(self.SingleSelection)
        self.setViewMode(self.IconMode)

        self.delegate = CoverDelegate(self)
        self.setItemDelegate(self.delegate)
        self.delegate.needs_redraw.connect(self.viewport().update,
                type=Qt.QueuedConnection)

        self.doubleClicked.connect(self.chosen, type=Qt.QueuedConnection)

    def select(self, num):
        current = self.model().index(num)
        sm = self.selectionModel()
        sm.select(current, sm.SelectCurrent)

    def start(self):
        self.select(0)
        self.delegate.start_animation()

    def clear_failed(self):
        plugin = self.m.plugin_for_index(self.currentIndex())
        self.m.clear_failed()
        self.select(self.m.index_for_plugin(plugin).row())

# }}}

class CoversWidget(QWidget): # {{{

    chosen = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, log, current_cover, parent=None):
        QWidget.__init__(self, parent)
        self.log = log
        self.abort = Event()

        self.l = l = QGridLayout()
        self.setLayout(l)

        self.msg = QLabel()
        self.msg.setWordWrap(True)
        l.addWidget(self.msg, 0, 0)

        self.covers_view = CoversView(current_cover, self)
        self.covers_view.chosen.connect(self.chosen)
        l.addWidget(self.covers_view, 1, 0)
        self.continue_processing = True

    def start(self, book, current_cover, title, authors):
        self.book, self.current_cover = book, current_cover
        self.title, self.authors = title, authors
        self.log('\n\nStarting cover download for:', book.title)
        self.msg.setText('<p>'+_('Downloading covers for <b>%s</b>, please wait...')%book.title)
        self.covers_view.start()

        self.worker = CoverWorker(self.log, self.abort, self.title,
                self.authors, book.identifiers)
        self.worker.start()
        QTimer.singleShot(50, self.check)
        self.covers_view.setFocus(Qt.OtherFocusReason)

    def check(self):
        if self.worker.is_alive() and not self.abort.is_set():
            QTimer.singleShot(50, self.check)
            try:
                self.process_result(self.worker.rq.get_nowait())
            except Empty:
                pass
        else:
            self.process_results()

    def process_results(self):
        while self.continue_processing:
            try:
                self.process_result(self.worker.rq.get_nowait())
            except Empty:
                break

        self.covers_view.clear_failed()

        if self.worker.error is not None:
            error_dialog(self, _('Download failed'),
                    _('Failed to download any covers, click'
                        ' "Show details" for details.'),
                    det_msg=self.worker.error, show=True)

        num = self.covers_view.model().rowCount()
        if num < 2:
            txt = _('Could not find any covers for <b>%s</b>')%self.book.title
        else:
            txt = _('Found <b>%d</b> covers of %s. Pick the one you like'
                    ' best.')%(num, self.title)
        self.msg.setText(txt)

        self.finished.emit()

    def process_result(self, result):
        if not self.continue_processing:
            return
        plugin, width, height, fmt, data = result
        self.covers_view.model().update_result(plugin, width, height, data)

    def cleanup(self):
        self.covers_view.delegate.stop_animation()
        self.continue_processing = False

    def cancel(self):
        self.continue_processing = False
        self.abort.set()

    @property
    def cover_pmap(self):
        return self.covers_view.model().cover_pmap(
                self.covers_view.currentIndex())

# }}}

class FullFetch(QDialog): # {{{

    def __init__(self, log, current_cover=None, parent=None):
        QDialog.__init__(self, parent)
        self.log, self.current_cover = log, current_cover
        self.book = self.cover_pmap = None

        self.setWindowTitle(_('Downloading metadata...'))
        self.setWindowIcon(QIcon(I('metadata.png')))

        self.stack = QStackedWidget()
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.addWidget(self.stack)

        self.bb = QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        l.addWidget(self.bb)
        self.bb.rejected.connect(self.reject)
        self.next_button = self.bb.addButton(_('Next'), self.bb.AcceptRole)
        self.next_button.setDefault(True)
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self.next_clicked)
        self.ok_button = self.bb.button(self.bb.Ok)
        self.ok_button.setVisible(False)
        self.ok_button.clicked.connect(self.ok_clicked)

        self.identify_widget = IdentifyWidget(log, self)
        self.identify_widget.rejected.connect(self.reject)
        self.identify_widget.results_found.connect(self.identify_results_found)
        self.identify_widget.book_selected.connect(self.book_selected)
        self.stack.addWidget(self.identify_widget)

        self.covers_widget = CoversWidget(self.log, self.current_cover, parent=self)
        self.covers_widget.chosen.connect(self.ok_clicked)
        self.stack.addWidget(self.covers_widget)

        self.resize(850, 550)

        self.finished.connect(self.cleanup)

    def book_selected(self, book):
        self.next_button.setVisible(False)
        self.ok_button.setVisible(True)
        self.book = book
        self.stack.setCurrentIndex(1)
        self.covers_widget.start(book, self.current_cover,
                self.title, self.authors)

    def accept(self):
        # Prevent the usual dialog accept mechanisms from working
        pass

    def reject(self):
        self.identify_widget.cancel()
        return QDialog.reject(self)

    def cleanup(self):
        self.covers_widget.cleanup()

    def identify_results_found(self):
        self.next_button.setEnabled(True)

    def next_clicked(self, *args):
        self.identify_widget.get_result()

    def ok_clicked(self, *args):
        self.cover_pmap = self.covers_widget.cover_pmap
        QDialog.accept(self)

    def start(self, title=None, authors=None, identifiers={}):
        self.title, self.authors = title, authors
        self.identify_widget.start(title=title, authors=authors,
                identifiers=identifiers)
        self.exec_()
# }}}

if __name__ == '__main__':
    DEVELOP_DIALOG = True
    app = QApplication([])
    d = FullFetch(Log())
    d.start(title='great gatsby', authors=['Fitzgerald'])

