##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import sys, logging, os, traceback, time, cPickle

from PyQt4.QtGui import QApplication, QKeySequence, QPainter, QDialog
from PyQt4.QtCore import Qt, QObject, SIGNAL, QCoreApplication, QThread, \
                         QSettings, QVariant

from libprs500 import __appname__, __version__, __author__, setup_cli_handlers, islinux
from libprs500.ebooks.lrf.parser import LRFDocument

from libprs500.gui2 import ORG_NAME, APP_UID, error_dialog, choose_files
from libprs500.gui2.dialogs.conversion_error import ConversionErrorDialog
from libprs500.gui2.lrf_renderer.main_ui import Ui_MainWindow
from libprs500.gui2.lrf_renderer.config_ui import Ui_ViewerConfig
from libprs500.gui2.main_window import MainWindow
from libprs500.gui2.lrf_renderer.document import Document

class RenderWorker(QThread):
    
    def __init__(self, parent, lrf_stream, logger, opts):
        QThread.__init__(self, parent)
        self.stream, self.logger, self.opts = lrf_stream, logger, opts
        self.aborted = False
        self.lrf = None
        self.document = None
        self.exception = None
        
    def run(self):
        try:
            self.lrf = LRFDocument(self.stream)
            self.lrf.parse()
            self.stream.close()
            self.stream = None
            if self.aborted:
                self.lrf = None            
        except Exception, err:
            self.lrf, self.stream = None, None
            self.exception = err
            self.formatted_traceback = traceback.format_exc()
            
    def abort(self):
        if self.lrf is not None:
            self.aborted = True
            self.lrf.keep_parsing = False
        
class Config(QDialog, Ui_ViewerConfig):
    
    def __init__(self, parent, opts):
        QDialog.__init__(self, parent)
        Ui_ViewerConfig.__init__(self)
        self.setupUi(self)
        self.white_background.setChecked(opts.white_background)
        self.hyphenate.setChecked(opts.hyphenate)
        
class Main(MainWindow, Ui_MainWindow):
    
    def __init__(self, logger, opts, parent=None):
        MainWindow.__init__(self, parent)
        Ui_MainWindow.__init__(self)        
        self.setupUi(self)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(__appname__ + ' - LRF Viewer')
    
        self.logger = logger
        self.opts = opts
        self.document = None
        self.document = Document(self.logger, self.opts)
        QObject.connect(self.document, SIGNAL('chapter_rendered(int)'), self.chapter_rendered)
        QObject.connect(self.document, SIGNAL('page_changed(PyQt_PyObject)'), self.page_changed)
        
        QObject.connect(self.search, SIGNAL('search(PyQt_PyObject, PyQt_PyObject)'), self.find)
        
        self.action_next_page.setShortcuts(QKeySequence.MoveToNextPage)
        self.action_previous_page.setShortcuts(QKeySequence.MoveToPreviousPage)
        self.action_next_match.setShortcuts(QKeySequence.FindNext)
        self.addAction(self.action_next_match)
        QObject.connect(self.action_next_page, SIGNAL('triggered(bool)'), self.next) 
        QObject.connect(self.action_previous_page, SIGNAL('triggered(bool)'), self.previous)
        QObject.connect(self.action_back, SIGNAL('triggered(bool)'), self.back)
        QObject.connect(self.action_forward, SIGNAL('triggered(bool)'), self.forward)
        QObject.connect(self.action_next_match, SIGNAL('triggered(bool)'), self.next_match)
        QObject.connect(self.action_open_ebook, SIGNAL('triggered(bool)'), self.open_ebook)
        QObject.connect(self.action_configure, SIGNAL('triggered(bool)'), self.configure)
        QObject.connect(self.spin_box, SIGNAL('valueChanged(int)'), self.go_to_page)
        QObject.connect(self.slider, SIGNAL('valueChanged(int)'), self.go_to_page)
        
        self.next_button.setDefaultAction(self.action_next_page)
        self.previous_button.setDefaultAction(self.action_previous_page)
        self.back_button.setDefaultAction(self.action_back)
        self.forward_button.setDefaultAction(self.action_forward)
        self.open_button.setDefaultAction(self.action_open_ebook)
        self.configure_button.setDefaultAction(self.action_configure)
        
        self.graphics_view.setRenderHint(QPainter.Antialiasing, True)
        self.graphics_view.setRenderHint(QPainter.TextAntialiasing, True)
        self.graphics_view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        self.closed = False
        
    def configure(self, triggered):
        opts = cPickle.loads(str(QSettings().value('ebook viewer options', QVariant(cPickle.dumps(self.opts))).toString()))
        d = Config(self, opts)
        d.exec_()
        if d.result() == QDialog.Accepted:
            opts.white_background = bool(d.white_background.isChecked())
            opts.hyphenate = bool(d.hyphenate.isChecked())
            QSettings().setValue('ebook viewer options', QVariant(cPickle.dumps(opts)))
    
    def set_ebook(self, stream):
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setValue(0)
            
        if stream is not None:
            self.file_name = os.path.basename(stream.name) if hasattr(stream, 'name') else ''
            self.progress_label.setText('Parsing '+ self.file_name)
            self.renderer = RenderWorker(self, stream, self.logger, self.opts)
            QObject.connect(self.renderer, SIGNAL('finished()'), self.parsed, Qt.QueuedConnection)
            self.search.help_text = 'Search'
            self.search.clear_to_help()
            self.last_search = None
        else:
            self.stack.setCurrentIndex(0)
            self.renderer = None
        
    def open_ebook(self, triggered):
        files = choose_files(self, 'open ebook dialog', 'Choose ebook', 
                             [('Ebooks', ['lrf'])], all_files=False, 
                             select_only_single_file=True)
        if files:
            file = files[0]
            self.set_ebook(open(file, 'rb'))
            self.render()
            
    
    def page_changed(self, num):
        self.slider.setValue(num)
        self.spin_box.setValue(num)
    
    def render(self):
        if self.renderer is not None:
            self.stack.setCurrentIndex(1)
            self.renderer.start()
    
    def find(self, search, refinement):
        self.last_search = search
        try:
            self.document.search(search)
        except StopIteration:
            error_dialog(self, 'No matches found', '<b>No matches</b> for the search phrase <i>%s</i> were found.'%(search,)).exec_()
    
    def parsed(self):
        if not self.renderer.aborted and self.renderer.lrf is not None:
            width, height =  self.renderer.lrf.device_info.width, \
                                            self.renderer.lrf.device_info.height
            self.graphics_view.resize_for(width, height)
            desktop = QCoreApplication.instance().desktop()
            screen_height = desktop.availableGeometry().height()
            height = min(screen_height, height+50)
            self.resize(self.size().width(), height) 
            self.setWindowTitle(self.renderer.lrf.metadata.title + ' - ' + __appname__)
            self.document_title = self.renderer.lrf.metadata.title
            if self.opts.profile:
                import cProfile
                lrf = self.renderer.lrf
                cProfile.runctx('self.document.render(lrf)', globals(), locals(), lrf.metadata.title+'.stats')
                print 'Stats written to', self.renderer.lrf.metadata.title+'.stats'
            else:
                start = time.time()
                self.document.render(self.renderer.lrf)
                print 'Layout time:', time.time()-start, 'seconds'
            self.renderer.lrf = None
            self.graphics_view.setScene(self.document)
            self.graphics_view.show()
            self.spin_box.setRange(1, self.document.num_of_pages)
            self.slider.setRange(1, self.document.num_of_pages)
            self.spin_box.setSuffix(' of %d'%(self.document.num_of_pages,))
            self.spin_box.updateGeometry()
            self.stack.setCurrentIndex(0)
        elif self.renderer.exception is not None:
            exception = self.renderer.exception
            print >>sys.stderr, 'Error rendering document'
            print >>sys.stderr, exception
            print >>sys.stderr, self.renderer.formatted_traceback
            msg =  u'<p><b>%s</b>: '%(exception.__class__.__name__,) + unicode(str(exception), 'utf8', 'replace') + u'</p>'
            msg += u'<p>Failed to render document</p>'
            msg += u'<p>Detailed <b>traceback</b>:<pre>'
            msg += self.renderer.formatted_traceback + '</pre>'            
            d = ConversionErrorDialog(self, 'Error while rendering file', msg)
            d.exec_()
            
    def chapter_rendered(self, num):
        if num > 0:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(num)
            self.progress_bar.setValue(0)
            self.progress_label.setText('Laying out '+ self.document_title)
        else:
            self.progress_bar.setValue(self.progress_bar.value()+1)
        QCoreApplication.processEvents()
    
    def next(self, triggered):
        self.document.next()

    def next_match(self, triggered):
        try:
            self.document.next_match()
        except StopIteration:
            pass
        
    def previous(self, triggered):
        self.document.previous()
        
    def go_to_page(self, num):
        self.document.show_page(num)
        
    def forward(self, triggered):
        self.document.forward()
    
    def back(self, triggered):
        self.document.back()
        
    def closeEvent(self, event):
        if self.renderer is not None and self.renderer.isRunning():
            self.renderer.abort()
            self.renderer.wait()
        self.emit(SIGNAL('viewer_closed(PyQt_PyObject)'), self)
        event.accept()


def file_renderer(stream, opts, parent=None, logger=None):
    if logger is None:
        level = logging.DEBUG if opts.verbose else logging.INFO
        logger = logging.getLogger('lrfviewer')
        setup_cli_handlers(logger, level)
    if islinux:
        try: # Set lrfviewer as the default for LRF files for this user
            from subprocess import call
            call('xdg-mime default libprs500-lrfviewer.desktop application/lrf', shell=True)
        except:
            pass
    m = Main(logger, opts, parent=parent)
    m.set_ebook(stream)
    return m
    

def option_parser():
    from optparse import OptionParser
    parser = OptionParser(usage='%prog book.lrf', version=__appname__+' '+__version__,
                          epilog='Created by ' + __author__)
    parser.add_option('--verbose', default=False, action='store_true', dest='verbose',
                      help='Print more information about the rendering process')
    parser.add_option('--visual-debug', help='Turn on visual aids to debugging the rendering engine',
                      default=False, action='store_true', dest='visual_debug')
    parser.add_option('--disable-hyphenation', dest='hyphenate', default=True, action='store_false',
                      help='Disable hyphenation. Should significantly speed up rendering.')
    parser.add_option('--white-background', dest='white_background', default=False, action='store_true',
                      help='By default the background is off white as I find this easier on the eyes. Use this option to make the background pure white.')
    parser.add_option('--profile', dest='profile', default=False, action='store_true',
                      help='Profile the LRF renderer')
    return parser

def normalize_settings(parser, opts):
    settings = QSettings()
    saved_opts = cPickle.loads(str(settings.value('ebook viewer options', QVariant(cPickle.dumps(opts))).toString()))
    for opt in parser.option_list:
        if not opt.dest:
            continue
        if getattr(opts, opt.dest) == opt.default:
            continue
        setattr(saved_opts, opt.dest, getattr(opts, opt.dest))
    return saved_opts
    

def main(args=sys.argv, logger=None):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if hasattr(opts, 'help'):
        parser.print_help()
        return 1
    pid = os.fork() if islinux else -1
    if pid <= 0:
        app = QApplication(args)
        QCoreApplication.setOrganizationName(ORG_NAME)
        QCoreApplication.setApplicationName(APP_UID)
        opts = normalize_settings(parser, opts)
        stream = open(args[1], 'rb') if len(args) > 1 else None        
        main = file_renderer(stream, opts, logger=logger)
        sys.excepthook = main.unhandled_exception
        main.show()
        main.render()
        return app.exec_()        
    return 0

if __name__ == '__main__':
    sys.exit(main())
    
    
