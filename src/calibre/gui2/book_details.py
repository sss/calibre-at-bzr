#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, collections

from PyQt4.Qt import QLabel, QPixmap, QSize, QWidget, Qt, pyqtSignal, \
    QVBoxLayout, QScrollArea

from calibre import fit_image, prepare_string_for_xml
from calibre.gui2.widgets import IMAGE_EXTENSIONS
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.constants import preferred_encoding

class CoverView(QLabel):

    def __init__(self, parent=None):
        QLabel.__init__(self, parent)
        self.default_pixmap = QPixmap(I('book.svg'))
        self.max_width, self.max_height = 120, 120
        self.setScaledContents(True)
        self.setPixmap(self.default_pixmap)

        def do_layout(self):
            pixmap = self.pixmap()
            pwidth, pheight = pixmap.width(), pixmap.height()
            width, height = fit_image(pwidth, pheight,
                                              self.max_width, self.max_height)[1:]
            self.setMaximumWidth(width)
            try:
                aspect_ratio = pwidth/float(pheight)
            except ZeroDivisionError:
                aspect_ratio = 1
            mh = min(self.max_height, int(width/aspect_ratio))
            self.setMaximumHeight(mh)

        def setPixmap(self, pixmap):
            QLabel.setPixmap(self, pixmap)
            self.do_layout()


        def sizeHint(self):
            return QSize(self.maximumWidth(), self.maximumHeight())

        def relayout(self, parent_size):
            self.max_height = int(parent_size.height()/3.)
            self.max_width = parent_size.width()
            self.do_layout()

        def show_data(self, data):
            if data.has_key('cover'):
                self.setPixmap(QPixmap.fromImage(data.pop('cover')))
            else:
                self.setPixmap(self.default_pixmap)

class BookInfo(QScrollArea):

    def __init__(self, parent=None):
        QScrollArea.__init__(self, parent)
        self.setWidgetResizable(True)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.setWidget(self.label)

    def show_data(self, data):
        self.label.setText('')
        self.data = data.copy()
        rows = render_rows(self.data)
        rows = u'\n'.join([u'<tr><td valign="top"><b>%s:</b></td><td valign="top">%s</td></tr>'%(k,t) for
            k, t in rows])
        self.label.setText(u'<table>%s</table>'%rows)

WEIGHTS = collections.defaultdict(lambda : 100)
WEIGHTS[_('Path')] = 0
WEIGHTS[_('Formats')] = 1
WEIGHTS[_('Collections')] = 2
WEIGHTS[_('Series')] = 3
WEIGHTS[_('Tags')] = 4

def render_rows(data):
    keys = data.keys()
    keys.sort(cmp=lambda x, y: cmp(WEIGHTS[x], WEIGHTS[y]))
    rows = []
    for key in keys:
        txt = data[key]
        if key in ('id', _('Comments')) or not txt or not txt.strip() or \
                txt == 'None':
            continue
        if isinstance(key, str):
            key = key.decode(preferred_encoding, 'replace')
        if isinstance(txt, str):
            txt = txt.decode(preferred_encoding, 'replace')
        if '</font>' not in txt:
            txt = prepare_string_for_xml(txt)
        if key == _('Path'):
            txt = '...'+os.sep+os.sep.join(txt.split(os.sep)[-2:])
            txt = u'<a href="path:%s">%s</a>'%(data['id'], txt)
        if key == _('Formats') and txt and txt != _('None'):
            fmts = [x.strip() for x in txt.split(',')]
            fmts = [u'<a href="format:%s:%s">%s</a>' % (data['id'], x, x) for x
                    in fmts]
            txt = ', '.join(fmts)
        rows.append((key, txt))
    return rows

class BookDetails(QWidget):

    resized = pyqtSignal(object)
    show_book_info = pyqtSignal()

    # Drag 'n drop {{{
    DROPABBLE_EXTENSIONS = IMAGE_EXTENSIONS+BOOK_EXTENSIONS
    files_dropped = pyqtSignal(object, object)

    @classmethod
    def paths_from_event(cls, event):
        '''
        Accept a drop event and return a list of paths that can be read from
        and represent files with extensions.
        '''
        if event.mimeData().hasFormat('text/uri-list'):
            urls = [unicode(u.toLocalFile()) for u in event.mimeData().urls()]
            urls = [u for u in urls if os.path.splitext(u)[1] and os.access(u, os.R_OK)]
            return [u for u in urls if os.path.splitext(u)[1][1:].lower() in cls.DROPABBLE_EXTENSIONS]

    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        paths = self.paths_from_event(event)
        if paths:
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self.paths_from_event(event)
        event.setDropAction(Qt.CopyAction)
        self.files_dropped.emit(event, paths)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    # }}}

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._layout = QVBoxLayout()

        self.setLayout(self._layout)
        self.cover_view = CoverView(self)
        self.cover_view.relayout()
        self.resized.connect(self.cover_view.relayout, type=Qt.QueuedConnection)
        self._layout.addWidget(self.cover_view)


    def resizeEvent(self, ev):
        self.resized.emit(self.size())

    def show_data(self, data):
        self.cover_view.show_data(data)

    def reset_info(self):
        self.show_data({})

    def mouseReleaseEvent(self, ev):
        self.show_book_info.emit()


