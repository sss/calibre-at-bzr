__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, re, collections

from PyQt4.QtGui import QStatusBar, QLabel, QWidget, QHBoxLayout, QPixmap, \
                        QVBoxLayout, QSizePolicy, QToolButton, QIcon, QScrollArea, QFrame
from PyQt4.QtCore import Qt, QSize, SIGNAL, QCoreApplication, pyqtSignal

from calibre import fit_image, preferred_encoding, isosx
from calibre.gui2 import config
from calibre.gui2.widgets import IMAGE_EXTENSIONS
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.notify import get_notifier
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.library.comments import comments_to_html

class BookInfoDisplay(QWidget):

    DROPABBLE_EXTENSIONS = IMAGE_EXTENSIONS+BOOK_EXTENSIONS

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
        self.emit(SIGNAL('files_dropped(PyQt_PyObject, PyQt_PyObject)'), event,
            paths)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()


    class BookCoverDisplay(QLabel):

        def __init__(self, coverpath=I('book.svg')):
            QLabel.__init__(self)
            self.setMaximumWidth(81)
            self.setMaximumHeight(108)
            self.default_pixmap = QPixmap(coverpath).scaled(self.maximumWidth(),
                                                            self.maximumHeight(),
                                                            Qt.IgnoreAspectRatio,
                                                            Qt.SmoothTransformation)
            self.setScaledContents(True)
            self.statusbar_height = 120
            self.setPixmap(self.default_pixmap)

        def do_layout(self):
            pixmap = self.pixmap()
            pwidth, pheight = pixmap.width(), pixmap.height()
            width, height = fit_image(pwidth, pheight,
                                              pwidth, self.statusbar_height-12)[1:]
            self.setMaximumHeight(height)
            try:
                aspect_ratio = pwidth/float(pheight)
            except ZeroDivisionError:
                aspect_ratio = 1
            self.setMaximumWidth(int(aspect_ratio*self.maximumHeight()))

        def setPixmap(self, pixmap):
            QLabel.setPixmap(self, pixmap)
            self.do_layout()


        def sizeHint(self):
            return QSize(self.maximumWidth(), self.maximumHeight())

        def relayout(self, statusbar_size):
            self.statusbar_height = statusbar_size.height()
            self.do_layout()


    class BookDataDisplay(QLabel):
        def __init__(self):
            QLabel.__init__(self)
            self.setText('')
            self.setWordWrap(True)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

        def mouseReleaseEvent(self, ev):
            self.emit(SIGNAL('mr(int)'), 1)

    WEIGHTS = collections.defaultdict(lambda : 100)
    WEIGHTS[_('Path')] = 0
    WEIGHTS[_('Formats')] = 1
    WEIGHTS[_('Comments')] = 4
    WEIGHTS[_('Series')] = 2
    WEIGHTS[_('Tags')] = 3

    def __init__(self, clear_message):
        QWidget.__init__(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self.clear_message = clear_message
        self.cover_display = BookInfoDisplay.BookCoverDisplay()
        self._layout.addWidget(self.cover_display)
        self.book_data = BookInfoDisplay.BookDataDisplay()
        self.connect(self.book_data, SIGNAL('mr(int)'), self.mouseReleaseEvent)
        self._layout.addWidget(self.book_data)
        self.data = {}
        self.setVisible(False)
        self._layout.setAlignment(self.cover_display, Qt.AlignTop|Qt.AlignLeft)

    def mouseReleaseEvent(self, ev):
        self.emit(SIGNAL('show_book_info()'))

    def show_data(self, data):
        if data.has_key('cover'):
            self.cover_display.setPixmap(QPixmap.fromImage(data.pop('cover')))
        else:
            self.cover_display.setPixmap(self.cover_display.default_pixmap)

        rows = u''
        self.book_data.setText('')
        self.data = data.copy()
        keys = data.keys()
        keys.sort(cmp=lambda x, y: cmp(self.WEIGHTS[x], self.WEIGHTS[y]))
        for key in keys:
            txt = data[key]
            if not txt or not txt.strip() or txt == 'None':
                continue
            if isinstance(key, str):
                key = key.decode(preferred_encoding, 'replace')
            if isinstance(txt, str):
                txt = txt.decode(preferred_encoding, 'replace')
            if key == _('Comments'):
                txt = comments_to_html(txt)
            rows += u'<tr><td><b>%s:</b></td><td>%s</td></tr>'%(key, txt)
        self.book_data.setText(u'<table>'+rows+u'</table>')

        self.clear_message()
        self.book_data.updateGeometry()
        self.updateGeometry()
        self.setVisible(True)

class MovieButton(QFrame):

    def __init__(self, jobs_dialog):
        QFrame.__init__(self)
        self.setLayout(QVBoxLayout())
        self.pi = ProgressIndicator(self)
        self.layout().addWidget(self.pi)
        self.jobs = QLabel('<b>'+_('Jobs:')+' 0')
        self.jobs.setAlignment(Qt.AlignHCenter|Qt.AlignBottom)
        self.layout().addWidget(self.jobs)
        self.layout().setAlignment(self.jobs, Qt.AlignHCenter)
        self.jobs.setMargin(0)
        self.layout().setMargin(0)
        self.jobs.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.jobs_dialog = jobs_dialog
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(_('Click to see list of active jobs.'))
        self.jobs_dialog.jobs_view.restore_column_widths()

    def mouseReleaseEvent(self, event):
        if self.jobs_dialog.isVisible():
            self.jobs_dialog.jobs_view.write_settings()
            self.jobs_dialog.hide()
        else:
            self.jobs_dialog.jobs_view.read_settings()
            self.jobs_dialog.show()
            self.jobs_dialog.jobs_view.restore_column_widths()

    @property
    def is_running(self):
        return self.pi.isAnimated()

    def start(self):
        self.pi.startAnimation()

    def stop(self):
        self.pi.stopAnimation()


class CoverFlowButton(QToolButton):

    def __init__(self, parent=None):
        QToolButton.__init__(self, parent)
        self.setIconSize(QSize(80, 80))
        self.setIcon(QIcon(I('cover_flow.svg')))
        self.setCheckable(True)
        self.setChecked(False)
        self.setAutoRaise(True)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding))
        self.connect(self, SIGNAL('toggled(bool)'), self.adjust_tooltip)
        self.adjust_tooltip(False)
        self.setCursor(Qt.PointingHandCursor)

    def adjust_tooltip(self, on):
        tt = _('Click to turn off Cover Browsing') if on else _('Click to browse books by their covers')
        self.setToolTip(tt)

    def disable(self, reason):
        self.setDisabled(True)
        self.setToolTip(_('<p>Browsing books by their covers is disabled.<br>Import of pictureflow module failed:<br>')+reason)


class StatusBar(QStatusBar):

    resized = pyqtSignal(object)

    def initialize(self, jobs_dialog, systray=None):
        self.systray = systray
        self.notifier = get_notifier(systray)
        self.movie_button = MovieButton(jobs_dialog)
        self.cover_flow_button = CoverFlowButton()
        self.addPermanentWidget(self.cover_flow_button)
        self.addPermanentWidget(self.movie_button)
        self.book_info = BookInfoDisplay(self.clearMessage)
        self.book_info.setAcceptDrops(True)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.book_info)
        self.scroll_area.setWidgetResizable(True)
        self.connect(self.book_info, SIGNAL('show_book_info()'), self.show_book_info)
        self.connect(self.book_info,
                SIGNAL('files_dropped(PyQt_PyObject,PyQt_PyObject)'),
                    self.files_dropped, Qt.QueuedConnection)
        self.addWidget(self.scroll_area, 100)
        self.setMinimumHeight(120)
        self.resized.connect(self.book_info.cover_display.relayout)
        self.book_info.cover_display.relayout(self.size())

    def resizeEvent(self, ev):
        self.resized.emit(self.size())

    def files_dropped(self, event, paths):
        self.emit(SIGNAL('files_dropped(PyQt_PyObject, PyQt_PyObject)'), event,
            paths)

    def reset_info(self):
        self.book_info.show_data({})

    def showMessage(self, msg, timeout=0):
        ret = QStatusBar.showMessage(self, msg, timeout)
        if self.notifier is not None and not config['disable_tray_notification']:
            if isosx and isinstance(msg, unicode):
                try:
                    msg = msg.encode(preferred_encoding)
                except UnicodeEncodeError:
                    msg = msg.encode('utf-8')
            self.notifier(msg)
        return ret

    def jobs(self):
        src = unicode(self.movie_button.jobs.text())
        return int(re.search(r'\d+', src).group())

    def show_book_info(self):
        self.emit(SIGNAL('show_book_info()'))

    def job_added(self, nnum):
        jobs = self.movie_button.jobs
        src = unicode(jobs.text())
        num = self.jobs()
        text = src.replace(str(num), str(nnum))
        jobs.setText(text)
        self.movie_button.start()

    def job_done(self, nnum):
        jobs = self.movie_button.jobs
        src = unicode(jobs.text())
        num = self.jobs()
        text = src.replace(str(num), str(nnum))
        jobs.setText(text)
        if nnum == 0:
            self.no_more_jobs()

    def no_more_jobs(self):
        if self.movie_button.is_running:
            self.movie_button.stop()
            QCoreApplication.instance().alert(self, 5000)


